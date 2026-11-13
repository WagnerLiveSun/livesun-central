"""Autocadastro gera solicitação, nunca acesso ou cobrança sem decisão do operador."""
import json
from datetime import timedelta
from urllib.parse import urlsplit
import requests
from app.extensions import db
from app.models import SolicitacaoCadastro, Cliente, Assinatura, Produto, Plano
from app.models.base import now
from app.schemas import CadastroProdutoInput, ClienteInput
from app.security import decrypt
from .assinatura_service import BusinessError, create
from .auditoria_service import audit, snapshot
from .entitlement_service import effective
from .webhook_service import validate_destination, signed_headers


def receive(product, payload):
    data = CadastroProdutoInput.model_validate(payload).model_dump()
    row = db.session.scalar(db.select(SolicitacaoCadastro).where(
        SolicitacaoCadastro.produto_id == product.id,
        SolicitacaoCadastro.empresa_origem == str(data['empresa_id'])).with_for_update())
    if row:
        if row.evento_origem != data['evento_id']:
            raise BusinessError('Empresa de origem já possui outra solicitação. Revise o vínculo existente.')
        return row, False
    row = SolicitacaoCadastro(produto_id=product.id, empresa_origem=str(data['empresa_id']),
        evento_origem=data['evento_id'], razao_social=data['razao_social'], nome_fantasia=data['nome_fantasia'],
        cnpj_cpf=data['cnpj_cpf'], email=str(data['email']), telefone=data['telefone'], responsavel=data['responsavel'])
    db.session.add(row)
    db.session.flush()
    audit(row, 'AUTOCADASTRO_RECEBIDO')
    return row, True


def review(identifier, client_id, plan_id, status, reason):
    row = db.session.scalar(db.select(SolicitacaoCadastro).where(SolicitacaoCadastro.id == identifier)
        .with_for_update().execution_options(populate_existing=True))
    if not row or row.status != 'PENDENTE':
        raise BusinessError('Solicitação não está pendente de habilitação.')
    if status not in ('ATIVA', 'TRIAL') or not reason or len(reason.strip()) < 3 or len(reason) > 500:
        raise BusinessError('Informe acesso inicial e justificativa válidos.')
    before = snapshot(row)
    product = db.session.scalar(db.select(Produto).where(Produto.id == row.produto_id).with_for_update())
    if not product or not product.ativo:
        raise BusinessError('Produto indisponível.')
    plan = db.session.get(Plano, plan_id)
    if not plan or not plan.ativo or plan.produto_id != product.id:
        raise BusinessError('Selecione um plano ativo deste produto.')
    if client_id:
        customer = db.session.get(Cliente, client_id)
        if not customer or customer.status != 'ATIVO':
            raise BusinessError('Cliente indisponível.')
        # O operador pode escolher cliente de outro produto, mas não outro documento.
        document = ''.join(c for c in (customer.cnpj_cpf or '') if c.isdigit())
        if document != row.cnpj_cpf:
            raise BusinessError('CPF/CNPJ do cliente selecionado não corresponde ao cadastro recebido.')
    else:
        normalized = db.func.replace(db.func.replace(db.func.replace(db.func.replace(
            Cliente.cnpj_cpf,'.',''),'/',''),'-',''),' ','')
        matches = list(db.session.scalars(db.select(Cliente).where(normalized == row.cnpj_cpf)))
        if matches:
            raise BusinessError('Já existe cliente com esse documento. Selecione-o para evitar duplicação.')
        code = 'CAD_' + str(row.produto_id) + '_' + row.empresa_origem
        data = ClienteInput.model_validate({'codigo_externo':code, 'razao_social':row.razao_social,
            'nome_fantasia':row.nome_fantasia, 'cnpj_cpf':row.cnpj_cpf,
            'email_principal':row.email, 'telefone':row.telefone}).model_dump()
        customer = Cliente(**data)
        db.session.add(customer)
        db.session.flush()
        audit(customer, 'CLIENTE_AUTOCADASTRO_HABILITADO')
    existing = db.session.scalar(db.select(Assinatura).where(Assinatura.cliente_id == customer.id,
        Assinatura.produto_id == product.id, Assinatura.slot_vigente == 1).with_for_update())
    if existing:
        # Pode vincular assinatura já existente sem trocar plano/status/cortesia.
        if existing.plano_id != plan.id or existing.status not in ('ATIVA','TRIAL'):
            raise BusinessError('Assinatura existente incompatível. Regularize-a antes de vincular o cadastro.')
        subscription = existing
    else:
        subscription = create({'cliente_id':customer.id, 'produto_id':product.id,
                               'plano_id':plan.id, 'status':status})
    row.cliente_id, row.assinatura_id = customer.id, subscription.id
    row.status, row.motivo, row.proxima_tentativa = 'VINCULO_PENDENTE', reason.strip(), now()
    audit(row, 'AUTOCADASTRO_HABILITADO_PELO_OPERADOR', before)
    return row


def status_payload(row):
    return {'solicitacao_id':row.id, 'empresa_id':int(row.empresa_origem), 'evento_id':row.evento_origem,
        'produto':row.produto.codigo, 'status':row.status,
        'cliente_id':row.cliente_id if row.status in ('VINCULO_PENDENTE','VINCULADA') else None,
        'assinatura_id':row.assinatura_id if row.status in ('VINCULO_PENDENTE','VINCULADA') else None}


def pull_pending():
    """Worker do Central recolhe outbox: funciona mesmo sem novas visitas ao Comercial."""
    products = db.session.scalars(db.select(Produto).where(Produto.ativo.is_(True), Produto.codigo == 'COMERCIAL')).all()
    for product in products:
        if not product.url_producao or not product.webhook_secret:
            continue
        try:
            url = product.url_producao.rstrip('/') + '/central/cadastros-pendentes'
            validate_destination(url)
            cursor = 0
            while True:
                path = urlsplit(url).path
                headers = signed_headers(decrypt(product.webhook_secret), path.encode())
                with requests.Session() as http:
                    http.trust_env = False
                    response = http.get(url, params={'apos':cursor}, headers=headers, timeout=(3,8), allow_redirects=False)
                if response.status_code != 200 or len(response.content) > 256*1024:
                    raise BusinessError('Produto não confirmou fila de cadastros.')
                payload = response.json()
                rows = payload.get('cadastros')
                if not isinstance(rows, list) or len(rows) > 50:
                    raise BusinessError('Fila de cadastros inválida.')
                for item in rows:
                    row, _ = receive(product, item['dados'])
                    db.session.commit()
                next_cursor = payload.get('proximo')
                if next_cursor is None:
                    break
                if type(next_cursor) is not int or next_cursor <= cursor:
                    raise BusinessError('Paginação de cadastros inválida.')
                cursor = next_cursor
        except Exception:
            db.session.rollback()
            # Sem dados do cadastro, URL com credenciais ou exceções no log.
            from flask import current_app
            current_app.logger.warning('pending', extra={'safe_event':'autocadastro_coleta_pendente'})


def deliver_one():
    row = db.session.scalar(db.select(SolicitacaoCadastro).where(
        SolicitacaoCadastro.status == 'VINCULO_PENDENTE', SolicitacaoCadastro.proxima_tentativa <= now())
        .order_by(SolicitacaoCadastro.id).with_for_update(skip_locked=True))
    if not row:
        db.session.rollback()
        return False
    row.tentativas_vinculo += 1
    # Lease simples pela próxima tentativa; receptor é idempotente.
    row.proxima_tentativa = now() + timedelta(minutes=2)
    db.session.commit()
    try:
        subscription = row.assinatura
        if not subscription or subscription.status not in ('ATIVA','TRIAL'):
            raise BusinessError('Assinatura não habilitada para concluir o vínculo.')
        product = row.produto
        url = product.url_producao.rstrip('/') + '/central/cadastros/vincular'
        validate_destination(url)
        data = {**status_payload(row), 'entitlements':effective(subscription)}
        if product.codigo == 'PROPOSTAS':
            data['cnpj_cpf'] = row.cnpj_cpf
        raw = json.dumps(data,separators=(',',':'),ensure_ascii=False).encode()
        headers = signed_headers(decrypt(product.webhook_secret), raw)
        headers['X-LiveSun-Event'] = 'CADASTRO_HABILITADO'
        with requests.Session() as http:
            http.trust_env = False
            response = http.post(url,data=raw,headers=headers,timeout=(3,10),allow_redirects=False)
        if response.status_code != 200 or response.json().get('evento_id') != row.evento_origem:
            raise BusinessError('Produto não confirmou o vínculo.')
        row.status, row.vinculado_em, row.erro_vinculo = 'VINCULADA', now(), None
        audit(row,'AUTOCADASTRO_VINCULADO_NO_PRODUTO')
    except Exception:
        db.session.rollback()
        row = db.session.get(SolicitacaoCadastro,row.id)
        row.erro_vinculo = 'VINCULO_NAO_CONFIRMADO'
        row.proxima_tentativa = now() + timedelta(seconds=min(3600,10*2**min(row.tentativas_vinculo,8)))
    db.session.commit()
    return True