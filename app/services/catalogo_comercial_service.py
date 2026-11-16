"""Importação explícita do catálogo: prévia assinada, sem sobrescrever contratos."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from app.extensions import db
from app.models import Plano
from app.schemas import PlanoInput
from .assinatura_service import BusinessError
from .auditoria_service import actor, snapshot
from app.models import Auditoria
from .catalogo_service import save
from .empresas_comercial_service import fetch, product, fingerprint
from .plano_codigo import commercial_code


def validate_offer(item):
    if not isinstance(item, dict):
        raise BusinessError('Oferta do Comercial inválida.')
    try:
        for field in ('id', 'versao'):
            if type(item[field]) is not int or not 1 <= item[field] <= 2147483647:
                raise ValueError()
        if (not isinstance(item['nome'], str) or not 1 <= len(item['nome'].strip()) <= 150
                or type(item['ativo']) is not bool or type(item['contratado']) is not bool
                or (item['usuarios'] is not None and (type(item['usuarios']) is not int or item['usuarios'] < 0))):
            raise ValueError()
        if not isinstance(item['preco'], str):
            raise ValueError()
        price = Decimal(item['preco'])
        if not price.is_finite() or price < 0 or price >= Decimal('10000000000') or price != price.quantize(Decimal('.01')):
            raise ValueError()
        code = commercial_code(item['categoria'], item['periodicidade'])
        for field in ('vigencia_inicio', 'vigencia_fim'):
            if item.get(field) is not None:
                date.fromisoformat(item[field])
        if item.get('vigencia_inicio') and item.get('vigencia_fim') and item['vigencia_fim'] < item['vigencia_inicio']:
            raise ValueError()
        # Moedas não BRL são exibidas para revisão, nunca convertidas automaticamente.
        if not isinstance(item['moeda'], str) or not 1 <= len(item['moeda']) <= 10:
            raise ValueError()
        return code
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise BusinessError('Oferta incompleta ou inválida na origem. Nenhum plano foi importado.') from None


def source_catalog():
    """Percorre todas as páginas, validando ordem e cursor; não aceita prévia parcial."""
    offers, cursor = [], 0
    while True:
        data = fetch(f'/central/planos?apos={cursor}')
        rows, next_cursor = data.get('planos'), data.get('proximo')
        if not isinstance(rows, list) or len(rows) > 50:
            raise BusinessError('Catálogo do Comercial inválido.')
        last = cursor
        for item in rows:
            validate_offer(item)
            if item['id'] <= last:
                raise BusinessError('Ordem do catálogo do Comercial inválida.')
            last = item['id']
        offers.extend(rows)
        if next_cursor is None:
            return offers
        if type(next_cursor) is not int or next_cursor != last or next_cursor <= cursor:
            raise BusinessError('Paginação do catálogo inválida. Nenhum plano foi importado.')
        cursor = next_cursor


def signature(offer):
    return (offer['periodicidade'], Decimal(offer['preco']), offer['moeda'], offer['usuarios'])


def preview():
    source = source_catalog()
    current_product = product()
    existing = {plan.codigo: plan for plan in db.session.scalars(db.select(Plano).where(
        Plano.produto_id == current_product.id))}
    groups = defaultdict(list)
    for item in source:
        groups[validate_offer(item)].append(item)
    result = []
    for code, offers in sorted(groups.items()):
        representative = max(offers, key=lambda item: (item['ativo'], item['versao'], item['id']))
        plan, conflict = existing.get(code), None
        if any(item['moeda'] != 'BRL' for item in offers):
            conflict = 'Moeda diferente de BRL: exige revisão, sem conversão automática.'
        elif len({signature(item) for item in offers}) > 1:
            conflict = 'Há versões com preços ou limites diferentes para o mesmo plano/ciclo. Exige revisão dos contratos; nenhum valor será sobrescrito.'
        elif not any(item['ativo'] or item['contratado'] for item in offers):
            conflict = 'Oferta inativa sem contrato: não importar.'
        elif plan and (not plan.ativo or plan.periodicidade != representative['periodicidade']
                       or plan.valor_mensal != Decimal(representative['preco'])
                       or plan.limite_usuarios != representative['usuarios']):
            conflict = 'Plano existente no Central diverge em ativação, preço, ciclo ou limite. Foi preservado; revise antes de migrar.'
        result.append({'codigo': code, 'oferta': representative, 'ofertas': offers,
            'plano_id': plan.id if plan else None, 'conflito': conflict,
            'acao': 'REVISAR' if conflict else 'EXISTENTE' if plan else 'CRIAR'})
    return {'linhas': result, 'hash': fingerprint({'produto':'COMERCIAL','planos':source}),
            'total_ofertas': len(source), 'produto_id': current_product.id}


def import_selected(expected_hash, selected_codes, confirmed):
    if not confirmed or not selected_codes or len(selected_codes) != len(set(selected_codes)):
        raise BusinessError('Selecione os planos e confirme a conferência da prévia.')
    current = preview()
    if current['hash'] != expected_hash:
        raise BusinessError('Catálogo de origem mudou. Atualize a prévia antes de importar.')
    chosen = {row['codigo']: row for row in current['linhas']}
    for code in selected_codes:
        if code not in chosen or chosen[code]['conflito']:
            raise BusinessError('Plano indisponível ou com divergência. Nenhum plano foi importado.')
    # Serializa importações deste produto, evitando criação concorrente por código.
    from app.models import Produto
    db.session.scalar(db.select(Produto).where(Produto.id == current['produto_id']).with_for_update())
    count = 0
    for code in selected_codes:
        row = chosen[code]
        offer = row['oferta']
        existing = db.session.scalar(db.select(Plano).where(Plano.produto_id == current['produto_id'], Plano.codigo == code)
            .execution_options(populate_existing=True))
        if existing:
            if (not existing.ativo or existing.valor_mensal != Decimal(offer['preco'])
                    or existing.periodicidade != offer['periodicidade'] or existing.limite_usuarios != offer['usuarios']):
                raise BusinessError('Plano foi alterado no Central. Atualize a prévia; nenhum plano foi sobrescrito.')
            continue
        values = {'produto_id':current['produto_id'], 'codigo':code, 'nome':offer['nome'],
            'valor_mensal':Decimal(offer['preco']), 'periodicidade':offer['periodicidade'],
            'limite_usuarios':offer['usuarios'], 'ativo':True,
            'descricao':'Oferta importada do Comercial; condições de origem registradas em auditoria.'}
        plan = save(Plano, PlanoInput, values)
        who, ip = actor()
        db.session.add(Auditoria(entidade=plan.__tablename__, entidade_id=plan.id,
            acao='CATALOGO_COMERCIAL_IMPORTADO', anterior={},
            novo={**snapshot(plan), 'ofertas_origem':row['ofertas'], 'catalogo_hash':current['hash']},
            responsavel=who, ip_origem=ip))
        count += 1
    return count