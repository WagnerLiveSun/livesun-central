"""Preparação explícita do legado Comercial por API, nunca por conexão ao MySQL."""
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import requests
from app.extensions import db
from app.models import Produto, SolicitacaoCadastro, Assinatura, Plano, Entitlement, Auditoria
from app.models.base import now
from app.schemas import CadastroProdutoInput
from app.security import decrypt
from .assinatura_service import BusinessError, apply_plan_modules, record
from .auditoria_service import actor, snapshot
from .cadastro_service import receive, resolve_customer
from .webhook_service import validate_destination, signed_headers


def legacy_event(identifier):
    return 'cad_' + hashlib.sha256(f'comercial:empresa:{identifier}'.encode()).hexdigest()[:32]


def is_legacy(row):
    return row.produto.codigo == 'COMERCIAL' and row.evento_origem == legacy_event(row.empresa_origem)


def product():
    row = db.session.scalar(db.select(Produto).where(Produto.codigo == 'COMERCIAL'))
    if not row or not row.ativo or not row.url_producao or not row.webhook_secret:
        raise BusinessError('Configure endereço e HMAC do produto COMERCIAL em Conexões dos produtos.')
    return row


def fetch(path):
    item = product()
    url = item.url_producao.rstrip('/') + path
    validate_destination(url)
    parsed = urlsplit(url)
    signed_path = parsed.path + ('?' + parsed.query if parsed.query else '')
    headers = signed_headers(decrypt(item.webhook_secret), signed_path.encode())
    try:
        with requests.Session() as http:
            http.trust_env = False
            with http.get(url, headers=headers, timeout=(3, 15), allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise BusinessError('Comercial não confirmou a consulta. Confira publicação, endereço e HMAC; mantenha o controle desativado.')
                raw = response.raw.read(262145, decode_content=True)
                if len(raw) > 262144:
                    raise BusinessError('Resposta do Comercial excede o tamanho permitido.')
                data = json.loads(raw)
        if not isinstance(data, dict) or data.get('produto') != 'COMERCIAL':
            raise ValueError()
        return data
    except (requests.RequestException, OSError, ValueError, TypeError) as exc:
        if isinstance(exc, BusinessError):
            raise
        raise BusinessError('Não foi possível consultar o Comercial. Nenhum cadastro foi alterado.') from None


def validate_company(item):
    if not isinstance(item, dict) or not isinstance(item.get('dados'), dict):
        raise BusinessError('Resposta de empresas do Comercial inválida.')
    identifier, linked = item['dados'].get('empresa_id'), item.get('cliente_id')
    if (type(identifier) is not int or not 1 <= identifier <= 2147483647
            or type(item.get('ativo')) is not bool
            or (linked is not None and (type(linked) is not int or linked <= 0))
            or (item.get('assinatura') is not None and not isinstance(item['assinatura'], dict))):
        raise BusinessError('Identificação da empresa do Comercial inválida.')
    return item


def list_companies(cursor=0):
    data = fetch(f'/central/empresas?apos={cursor}')
    rows, next_cursor = data.get('empresas'), data.get('proximo')
    if not isinstance(rows, list) or len(rows) > 50:
        raise BusinessError('Lista de empresas do Comercial inválida.')
    last = cursor
    for item in rows:
        validate_company(item)
        if item['dados']['empresa_id'] <= last:
            raise BusinessError('Ordem de empresas do Comercial inválida.')
        last = item['dados']['empresa_id']
    if next_cursor is not None and (type(next_cursor) is not int or next_cursor != last or next_cursor <= cursor):
        raise BusinessError('Paginação de empresas do Comercial inválida.')
    return rows, next_cursor


def company(identifier):
    item = validate_company(fetch(f'/central/empresas/{identifier}').get('empresa'))
    if item['dados']['empresa_id'] != identifier:
        raise BusinessError('Comercial retornou outra empresa; operação cancelada.')
    return item


def fingerprint(item):
    return hashlib.sha256(json.dumps(item, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def audit_origin(row, action, item):
    who, ip = actor()
    db.session.add(Auditoria(entidade=row.__tablename__, entidade_id=row.id, acao=action,
        anterior={}, novo={**snapshot(row), 'origem': item, 'hash': fingerprint(item)},
        responsavel=who, ip_origem=ip))


def prepare_registration(identifier):
    item = company(identifier)
    if not item['ativo'] or item['cliente_id'] is not None:
        raise BusinessError('Empresa excluída ou já vinculada no Comercial. Confira o vínculo existente.')
    data = CadastroProdutoInput.model_validate(item['dados']).model_dump(mode='json')
    if data['evento_id'] != legacy_event(identifier):
        raise BusinessError('Identificação do legado Comercial inválida.')
    row, created = receive(product(), data)
    if created:
        audit_origin(row, 'LEGADO_COMERCIAL_PREPARADO', item)
    return row


def conditions(item):
    legacy = item.get('assinatura')
    if not legacy:
        raise BusinessError('Empresa sem assinatura legada. Regularize a origem antes da migração.')
    try:
        if type(legacy['id']) is not int or legacy['id'] <= 0:
            raise ValueError()
        if legacy.get('mudanca_plano_pendente'):
            raise BusinessError('Há mudança de plano agendada. Regularize-a na origem antes de migrar.')
        if legacy.get('recorrencia_externa'):
            raise BusinessError('Há recorrência externa existente. Migração exige revisão específica para evitar cobrança duplicada.')
        if not legacy['bonificada'] and legacy.get('bloqueio_nivel', 'nenhum') != 'nenhum' and legacy['status'] in ('ativa','trial'):
            raise BusinessError('Há restrição de acesso legada. Revise a origem antes de migrar sem bloqueio equivalente.')
        if type(legacy.get('carencia_dias', 7)) is not int or not 0 <= legacy.get('carencia_dias', 7) <= 365:
            raise ValueError()
        if type(legacy['bonificada']) is not bool or type(legacy['usuarios']) is not int or legacy['usuarios'] < 0:
            raise ValueError()
        status = {'ativa':'ATIVA', 'trial':'TRIAL', 'suspensa':'SUSPENSA',
                  'cancelada':'CANCELADA', 'expirada':'EXPIRADA', 'bloqueada':'BLOQUEADA'}[legacy['status']]
        start = date.fromisoformat(legacy['data_inicio'])
        due = date.fromisoformat(legacy['data_vencimento'])
        trial = date.fromisoformat(legacy['trial_ate']) if legacy.get('trial_ate') else None
        bonus_end = date.fromisoformat(legacy['bonificacao_ate']) if legacy.get('bonificacao_ate') else None
        if legacy['bonificada']:
            if bonus_end and bonus_end < date.today():
                raise BusinessError('Bonificação vencida: revise a condição na origem antes de migrar, sem prorrogar o prazo.')
            status = 'ATIVA'
        if status == 'TRIAL' and trial is None:
            raise BusinessError('Trial sem data final: corrija a origem; nenhum prazo será presumido.')
        if status == 'TRIAL' and trial <= date.today():
            status = 'EXPIRADA'
        return legacy, status, start, due, trial, bonus_end
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, BusinessError):
            raise
        raise BusinessError('Condições legadas incompletas ou inválidas. Confira a origem antes de confirmar.') from None


def plan_mismatch(plan, legacy):
    """Mesma regra na prévia e na confirmação; não presume categoria pelo nome."""
    category = str(legacy.get('plano', '')).strip().lower()
    period = str(legacy.get('periodicidade', '')).strip().lower()
    if plan.codigo.lower().removesuffix('_anual') != category or plan.periodicidade != period:
        return (f'A origem exige {category} / {period}; o plano escolhido é '
                f'{plan.codigo} / {plan.periodicidade}. Selecione ou cadastre o plano correspondente em Planos.')
    if legacy.get('preco') is not None:
        try:
            price = Decimal(legacy['preco'])
            if not price.is_finite() or price < 0 or price != plan.valor_mensal:
                raise ValueError()
        except (InvalidOperation, ValueError):
            return 'Preço do plano difere da oferta legada. Confira o catálogo antes de migrar.'
    return None


def confirm(identifier, client_id, plan_id, expected_hash, confirmed, reason):
    row = db.session.scalar(db.select(SolicitacaoCadastro).where(SolicitacaoCadastro.id == identifier)
        .with_for_update().execution_options(populate_existing=True))
    if not row or not is_legacy(row) or row.status != 'PENDENTE':
        raise BusinessError('Migração não está pendente de confirmação.')
    if not confirmed or not reason or not 3 <= len(reason.strip()) <= 500:
        raise BusinessError('Confira as condições e informe uma justificativa para confirmar.')
    item = company(int(row.empresa_origem))
    if not row.produto.ativo:
        raise BusinessError('Produto COMERCIAL indisponível.')
    if not item['ativo'] or item['cliente_id'] is not None or fingerprint(item) != expected_hash:
        raise BusinessError('Dados do Comercial mudaram. Atualize a prévia antes de confirmar.')
    received = CadastroProdutoInput.model_validate(item['dados']).model_dump()
    if received['cnpj_cpf'] != row.cnpj_cpf or received['evento_id'] != row.evento_origem:
        raise BusinessError('Identidade da empresa alterada; revise o cadastro antes de confirmar.')
    legacy, status, start, due, trial, bonus_end = conditions(item)
    plan = db.session.get(Plano, plan_id)
    if not plan or not plan.ativo or plan.produto_id != row.produto_id:
        raise BusinessError('Selecione um plano ativo do COMERCIAL.')
    mismatch = plan_mismatch(plan, legacy)
    if mismatch:
        raise BusinessError(mismatch)
    customer = resolve_customer(row, client_id)
    existing = db.session.scalar(db.select(Assinatura).where(Assinatura.cliente_id == customer.id,
        Assinatura.produto_id == row.produto_id).with_for_update())
    code = f'COMERCIAL:empresa:{row.empresa_origem}:assinatura:{legacy["id"]}'
    historical = db.session.scalar(db.select(Assinatura).where(Assinatura.codigo_legado == code))
    if existing or historical:
        raise BusinessError('Cliente já possui assinatura COMERCIAL ou legado migrado. Revise o vínculo para não duplicar contratos.')
    subscription = Assinatura(cliente_id=customer.id, produto_id=row.produto_id, plano_id=plan.id,
        status=status, data_inicio=start, data_proxima_cobranca=due, trial_ate=trial,
        cortesia=legacy['bonificada'], cortesia_ate=bonus_end,
        carencia_dias=legacy.get('carencia_dias', 7),
        slot_vigente=None if status in ('CANCELADA','EXPIRADA') else 1,
        codigo_legado=code, versao=0, motivo_status=reason.strip(), asaas_habilitado=False)
    db.session.add(subscription)
    db.session.flush()
    apply_plan_modules(subscription)
    db.session.add(Entitlement(assinatura_id=subscription.id, chave='usuarios',
                              valor=legacy['usuarios'], ativo=True))
    record(subscription, 'ASSINATURA_LEGADA_MIGRADA', {})
    row.cliente_id, row.assinatura_id = customer.id, subscription.id
    row.status, row.motivo, row.proxima_tentativa = 'VINCULO_PENDENTE', reason.strip(), now()
    audit_origin(row, 'LEGADO_COMERCIAL_CONFIRMADO', item)
    return row