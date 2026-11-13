from app.extensions import db
from app.models import Produto, Plano, Modulo, PlanoModulo, Assinatura, Cliente, UsuarioCentral
from app.security import passwords
from .assinatura_service import BusinessError
from .auditoria_service import snapshot, audit


def save(model, schema, data, identifier=None):
    values = schema.model_validate(data).model_dump()
    obj = db.get_or_404(model, identifier) if identifier else model()
    before = snapshot(obj) if identifier else {}
    affected = []
    if model == Plano and identifier:
        if values['codigo'] != obj.codigo:
            raise BusinessError('Código de plano existente é imutável.')
        from .entitlement_service import effective
        affected = [(s, {**snapshot(s), 'entitlements': effective(s)}) for s in db.session.scalars(
            db.select(Assinatura).filter_by(plano_id=identifier, slot_vigente=1).with_for_update())]
    if model == Produto and values['codigo'] == 'PROPOSTAS' and (values['permite_multiplos_planos'] or values['permite_modulos']):
        raise BusinessError('Propostas deve permanecer com plano único e sem módulos.')
    if model == Produto and values['codigo'] == 'COMERCIAL' and values['permite_modulos']:
        raise BusinessError('Módulos do Comercial permanecem sob controle interno do produto.')
    if model == Plano:
        product_for_plan = db.session.get(Produto, values['produto_id'])
        if product_for_plan and product_for_plan.codigo == 'COMERCIAL' and values['codigo'] not in (
                'BASIC','INTERMEDIATE','PREMIUM','BASIC_ANUAL','INTERMEDIATE_ANUAL','PREMIUM_ANUAL'):
            raise BusinessError('Selecione código compatível com o Comercial: BASIC, INTERMEDIATE ou PREMIUM (opcional _ANUAL).')
    if model in (Plano, Modulo):
        product = db.session.scalar(db.select(Produto).where(Produto.id == values['produto_id']).with_for_update())
        if not product:
            raise BusinessError('Produto não encontrado.')
        if identifier and obj.produto_id != product.id:
            raise BusinessError('Não é permitido mover registros entre produtos.')
        if model == Plano and values['ativo'] and not product.permite_multiplos_planos:
            others = db.session.scalar(db.select(Plano.id).where(Plano.produto_id == product.id,
                Plano.ativo.is_(True), Plano.id != (identifier or 0)))
            if others:
                raise BusinessError('Produto permite somente um plano ativo.')
        if model == Modulo:
            if not product.permite_modulos:
                raise BusinessError('Produto não permite módulos.')
            if identifier and (values['depende_de'] != obj.depende_de or values['obrigatorio'] != obj.obrigatorio):
                raise BusinessError('Dependências/obrigatoriedade de módulo existente exigem migração comercial auditada.')
            graph = {m.codigo: list(m.depende_de or []) for m in product.modulos if m.id != identifier and m.ativo}
            if values['ativo']:
                graph[values['codigo']] = values['depende_de']
            def visit(code, path):
                if code in path or code not in graph:
                    raise BusinessError('Dependência ausente ou cíclica.')
                for dependency in graph[code]:
                    visit(dependency, path | {code})
            for code in graph:
                visit(code, set())
            if identifier and (values['codigo'] != obj.codigo or not values['ativo']):
                raise BusinessError('Código e ativação de módulo existente são imutáveis nesta versão.')
    if model == Produto and identifier:
        if values['codigo'] != obj.codigo:
            raise BusinessError('Código de produto existente é imutável.')
        if obj.codigo == 'PROPOSTAS' and (values['permite_multiplos_planos'] or values['permite_modulos']):
            raise BusinessError('Propostas deve permanecer com plano único e sem módulos.')
        if not values['permite_multiplos_planos'] and sum(p.ativo for p in obj.planos) > 1:
            raise BusinessError('Há vários planos ativos.')
        if obj.permite_modulos and not values['permite_modulos'] and any(m.ativo for m in obj.modulos):
            raise BusinessError('Existem módulos ativos.')
        if obj.ativo != values['ativo'] and db.session.scalar(db.select(Assinatura.id).filter_by(produto_id=obj.id, slot_vigente=1)):
            raise BusinessError('Encerre/suspenda as assinaturas antes de desativar o produto.')
    if model == Cliente and identifier and values['status'] != obj.status:
        if db.session.scalar(db.select(Assinatura.id).filter_by(cliente_id=obj.id, slot_vigente=1)):
            raise BusinessError('Encerre as assinaturas vigentes antes de alterar o status do cliente.')
    if model == UsuarioCentral:
        password = values.pop('senha')
        if not identifier and not password:
            raise BusinessError('Senha inicial obrigatória.')
        if password:
            obj.senha_hash = passwords.hash(password)
        if identifier and obj.perfil == 'superadmin' and (values['perfil'] != 'superadmin' or not values['ativo']):
            count = db.session.scalar(db.select(db.func.count()).select_from(UsuarioCentral).where(
                UsuarioCentral.perfil == 'superadmin', UsuarioCentral.ativo.is_(True), UsuarioCentral.id != identifier))
            if not count:
                raise BusinessError('Mantenha ao menos um superadmin ativo.')
    for key, value in values.items():
        setattr(obj, key, value)
    db.session.add(obj)
    db.session.flush()
    audit(obj, 'ATUALIZADO' if identifier else 'CRIADO', before)
    if affected:
        from .assinatura_service import record
        for subscription, old_state in affected:
            record(subscription, 'LIMITE_ALTERADO', old_state)
            if subscription.asaas_habilitado:
                from .asaas_service import enqueue
                enqueue(subscription, 'SINCRONIZAR')
    return obj


def set_plan_modules(plan, module_ids):
    if not plan.produto.permite_modulos:
        raise BusinessError('Produto sem módulos comerciais.')
    modules = list(db.session.scalars(db.select(Modulo).where(Modulo.id.in_(module_ids)))) if module_ids else []
    if len(modules) != len(set(module_ids)) or any(m.produto_id != plan.produto_id or not m.ativo for m in modules):
        raise BusinessError('Módulos incompatíveis.')
    from .assinatura_service import validate_modules
    validate_modules(plan.produto_id, {m.codigo for m in modules})
    before = {'modulos': [m.modulo_id for m in db.session.scalars(db.select(PlanoModulo).filter_by(plano_id=plan.id, liberado=True))]}
    existing = {m.modulo_id: m for m in db.session.scalars(db.select(PlanoModulo).filter_by(plano_id=plan.id))}
    for module_id in set(existing) | set(module_ids):
        entry = existing.get(module_id)
        if entry is None:
            entry = PlanoModulo(plano_id=plan.id, modulo_id=module_id)
            db.session.add(entry)
        entry.liberado = module_id in module_ids
    audit(plan, 'PLANO_MODULOS_CONFIGURADOS', before)