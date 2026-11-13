from datetime import date, timedelta
from uuid import uuid4
from app.extensions import db
from app.models import (Assinatura, AssinaturaModulo, Cliente, Produto, Plano, PlanoModulo,
                        Modulo, Entitlement, EventoAssinatura, WebhookEntrega)
from app.models.base import now, iso, STATUSES
from .auditoria_service import snapshot, audit, actor
from .entitlement_service import effective


class BusinessError(ValueError):
    pass


def locked(identifier):
    obj = db.session.scalar(db.select(Assinatura).where(Assinatura.id == identifier)
                            .with_for_update().execution_options(populate_existing=True))
    if not obj:
        raise BusinessError('Assinatura não encontrada.')
    return obj


def record(subscription, kind, before):
    subscription.versao += 1
    db.session.flush()
    who, ip = actor()
    event_id = 'evt_' + uuid4().hex
    after = snapshot(subscription)
    after['entitlements'] = effective(subscription)
    event = EventoAssinatura(assinatura_id=subscription.id, evento_id=event_id, tipo_evento=kind,
                             dados_anteriores=before, dados_novos=after,
                             usuario_responsavel=who, ip_origem=ip)
    db.session.add(event)
    db.session.flush()
    product = subscription.produto
    if product.url_webhook:
        payload = {'evento': kind, 'evento_id': event_id, 'ocorrido_em': iso(now()),
                   'cliente_id': str(subscription.cliente_id), 'produto': product.codigo,
                   'assinatura_id': subscription.id, 'versao': subscription.versao,
                   'status_anterior': before.get('status'), 'status_novo': subscription.status,
                   'motivo': subscription.motivo_status,
                   'dados': {'bloquear_login': not after['entitlements']['acesso_produto'],
                             'bloquear_recursos': not after['entitlements']['acesso_produto']},
                   'entitlements': after['entitlements']}
        db.session.add(WebhookEntrega(evento_id=event_id, produto_id=product.id,
                                      url_destino=product.url_webhook, payload=payload,
                                      proxima_tentativa=now()))
    audit(subscription, kind, before)


def validate_modules(product_id, enabled):
    modules = list(db.session.scalars(db.select(Modulo).filter_by(produto_id=product_id, ativo=True)))
    for module in modules:
        if module.obrigatorio and module.codigo not in enabled:
            raise BusinessError(f'Módulo obrigatório: {module.codigo}.')
        if module.codigo in enabled and not set(module.depende_de or []).issubset(enabled):
            raise BusinessError(f'Dependências não atendidas: {module.codigo}.')


def apply_plan_modules(subscription):
    if not subscription.produto.permite_modulos:
        return
    included = {m.modulo_id: m for m in db.session.scalars(db.select(PlanoModulo).filter_by(
        plano_id=subscription.plano_id, liberado=True))}
    required = list(db.session.scalars(db.select(Modulo).filter_by(
        produto_id=subscription.produto_id, obrigatorio=True, ativo=True)))
    ids = set(included) | {m.id for m in required}
    modules = list(db.session.scalars(db.select(Modulo).where(Modulo.id.in_(ids)))) if ids else []
    if any(m.produto_id != subscription.produto_id or not m.ativo for m in modules):
        raise BusinessError('Módulo incompatível com o plano.')
    validate_modules(subscription.produto_id, {m.codigo for m in modules})
    entries = {m.modulo_id: m for m in db.session.scalars(db.select(AssinaturaModulo).filter_by(
        assinatura_id=subscription.id))}
    for identifier in set(entries) | ids:
        entry = entries.get(identifier)
        if not entry:
            entry = AssinaturaModulo(assinatura_id=subscription.id, modulo_id=identifier)
            db.session.add(entry)
        entry.liberado = identifier in ids
        entry.limite = included[identifier].limite if identifier in included else None
        entry.data_liberacao = now() if entry.liberado else entry.data_liberacao
        entry.data_remocao = None if entry.liberado else now()


def create(data):
    customer = db.session.get(Cliente, data['cliente_id'])
    product = db.session.scalar(db.select(Produto).where(Produto.id == data['produto_id']).with_for_update())
    plan = db.session.get(Plano, data['plano_id'])
    if not customer or customer.status != 'ATIVO' or not product or not product.ativo:
        raise BusinessError('Cliente ou produto indisponível.')
    if not plan or not plan.ativo or plan.produto_id != product.id:
        raise BusinessError('Plano inválido para o produto.')
    status = data.get('status', 'TRIAL')
    if data.get('data_fim') and data['data_fim'] < (data.get('data_inicio') or date.today()):
        raise BusinessError('Fim da assinatura deve ser posterior ou igual ao início.')
    if status not in ('TRIAL', 'ATIVA'):
        raise BusinessError('Crie a assinatura como TRIAL ou ATIVA.')
    obj = Assinatura(cliente_id=customer.id, produto_id=product.id, plano_id=plan.id,
                     status=status, data_inicio=data.get('data_inicio') or date.today(),
                     data_fim=data.get('data_fim'), data_proxima_cobranca=data.get('data_proxima_cobranca'),
                     versao=0, slot_vigente=1)
    if status == 'TRIAL':
        obj.trial_ate = data.get('data_fim') or date.today() + timedelta(days=7)
    db.session.add(obj)
    db.session.flush()
    apply_plan_modules(obj)
    record(obj, 'ASSINATURA_CRIADA', {})
    return obj


def change_status(obj, status, reason):
    if status not in STATUSES or status == obj.status or obj.status == 'EXCLUIDA':
        raise BusinessError('Transição de status inválida.')
    if not reason or not reason.strip():
        raise BusinessError('Justificativa obrigatória.')
    if status == 'TRIAL' or (obj.status in ('CANCELADA', 'EXPIRADA') and status not in ('ATIVA', 'EXCLUIDA')):
        raise BusinessError('Transição não permitida.')
    before = snapshot(obj)
    was = obj.status
    obj.status, obj.motivo_status = status, reason
    obj.suspensa_por_inadimplencia = False
    if status == 'EXCLUIDA':
        obj.excluida_em = now()
    obj.slot_vigente = None if status in ('CANCELADA', 'EXPIRADA', 'EXCLUIDA') else 1
    kinds = {'ATIVA': 'ASSINATURA_ATIVADA' if was == 'TRIAL' else 'ASSINATURA_REATIVADA',
             'SUSPENSA': 'ASSINATURA_SUSPENSA', 'BLOQUEADA': 'ASSINATURA_BLOQUEADA',
             'CANCELADA': 'ASSINATURA_CANCELADA', 'EXPIRADA': 'ASSINATURA_EXPIRADA', 'EXCLUIDA': 'ASSINATURA_EXCLUIDA'}
    record(obj, kinds[status], before)
    if status == 'EXCLUIDA':
        from .purga_service import schedule
        schedule(obj, reason)
    if obj.asaas_habilitado:
        from .asaas_service import enqueue
        enqueue(obj, 'SINCRONIZAR')


def change_plan(obj, plan_id):
    if not obj.produto.permite_multiplos_planos:
        raise BusinessError('Produto não permite upgrade ou downgrade.')
    if obj.status in ('EXCLUIDA', 'CANCELADA', 'EXPIRADA'):
        raise BusinessError('Assinatura encerrada.')
    plan = db.session.get(Plano, plan_id)
    if not plan or not plan.ativo or plan.produto_id != obj.produto_id or plan.id == obj.plano_id:
        raise BusinessError('Plano inválido.')
    before = snapshot(obj)
    obj.plano_id = plan.id
    obj.plano = plan
    apply_plan_modules(obj)
    record(obj, 'PLANO_ALTERADO', before)
    if obj.asaas_habilitado:
        from .asaas_service import enqueue
        enqueue(obj, 'SINCRONIZAR')


def grant_trial(obj, days, reason):
    if obj.status == 'EXCLUIDA' or not 1 <= days <= 365 or not reason.strip():
        raise BusinessError('Trial inválido.')
    before = snapshot(obj)
    obj.status = 'TRIAL'
    obj.slot_vigente = 1
    obj.trial_ate = date.today() + timedelta(days=days)
    obj.cortesia = False
    obj.motivo_status = reason
    record(obj, 'TRIAL_ALTERADO', before)
    if obj.asaas_habilitado:
        from .asaas_service import enqueue
        enqueue(obj, 'SINCRONIZAR')


def grant_courtesy(obj, days, enabled, reason):
    if obj.status == 'EXCLUIDA' or not reason.strip() or days < 0 or days > 3650:
        raise BusinessError('Cortesia inválida.')
    before = snapshot(obj)
    obj.cortesia = enabled
    obj.cortesia_ate = date.today() + timedelta(days=days) if enabled and days else None
    if enabled:
        obj.status, obj.slot_vigente = 'ATIVA', 1
    obj.motivo_status = reason
    record(obj, 'CORTESIA_ALTERADA', before)
    if obj.asaas_habilitado:
        from .asaas_service import enqueue
        enqueue(obj, 'SINCRONIZAR')


def change_module(obj, module_id, enabled, limit=None):
    if not obj.produto.permite_modulos:
        raise BusinessError('Produto não permite módulos individuais.')
    if obj.status in ('EXCLUIDA', 'CANCELADA', 'EXPIRADA'):
        raise BusinessError('Assinatura encerrada.')
    module = db.session.get(Modulo, module_id)
    if not module or not module.ativo or module.produto_id != obj.produto_id:
        raise BusinessError('Módulo inválido.')
    entries = list(db.session.scalars(db.select(AssinaturaModulo).filter_by(assinatura_id=obj.id)))
    codes = {entry.modulo.codigo for entry in entries if entry.liberado}
    codes.add(module.codigo) if enabled else codes.discard(module.codigo)
    validate_modules(obj.produto_id, codes)
    before = snapshot(obj)
    before['modulos'] = effective(obj)['modulos']
    entry = next((e for e in entries if e.modulo_id == module.id), None)
    if entry is None:
        entry = AssinaturaModulo(assinatura_id=obj.id, modulo_id=module.id)
        db.session.add(entry)
    entry.liberado, entry.limite = enabled, limit
    entry.data_liberacao = now() if enabled else entry.data_liberacao
    entry.data_remocao = None if enabled else now()
    record(obj, 'MODULO_LIBERADO' if enabled else 'MODULO_REMOVIDO', before)


def change_limits(obj, values):
    if obj.status == 'EXCLUIDA':
        raise BusinessError('Assinatura excluída.')
    before = snapshot(obj)
    before['limites'] = effective(obj)['limites']
    for key, value in values.items():
        entry = db.session.scalar(db.select(Entitlement).filter_by(assinatura_id=obj.id, chave=key))
        if entry is None:
            entry = Entitlement(assinatura_id=obj.id, chave=key)
            db.session.add(entry)
        entry.valor, entry.limite, entry.ativo = value, None, True
    record(obj, 'LIMITE_ALTERADO', before)