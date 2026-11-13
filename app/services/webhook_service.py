import hashlib
import hmac
import ipaddress
import json
import socket
import time
import secrets
from datetime import timedelta
from urllib.parse import urlsplit
import requests
from flask import current_app
from cryptography.fernet import InvalidToken
from sqlalchemy import or_
from app.extensions import db
from app.models import WebhookEntrega, WebhookTentativa
from app.models.base import now
from app.security import decrypt, encrypt
from .auditoria_service import audit, snapshot
from .assinatura_service import BusinessError


def validate_destination(url):
    parsed = urlsplit(url)
    allowed = [h.strip() for h in current_app.config['WEBHOOK_ALLOWED_HOSTS'] if h.strip()]
    if (parsed.scheme == 'http' and current_app.config.get('WEBHOOK_ALLOW_LOCAL_HTTP') is True
            and current_app.config['APP_ENV'] == 'development'
            and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
            and parsed.hostname in allowed and not parsed.username and not parsed.password
            and not parsed.fragment and not parsed.query):
        return
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or parsed.port not in (None, 443) or parsed.hostname not in allowed):
        raise BusinessError('Destino HTTPS deve pertencer a WEBHOOK_ALLOWED_HOSTS, na porta 443.')
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise BusinessError('Destino de webhook não pode usar rede privada/reservada.')


def validate_webhook_destination(url):
    validate_destination(url)
    if urlsplit(url).path in ('', '/'):
        raise BusinessError('Informe o endereço completo do receptor, por exemplo /webhooks/assinatura, não a página inicial do produto.')


def signed_headers(secret, payload, timestamp=None):
    timestamp = str(timestamp or int(time.time()))
    digest = hmac.new(secret.encode(), timestamp.encode() + b'.' + payload, hashlib.sha256).hexdigest()
    return {'Content-Type': 'application/json', 'X-LiveSun-Timestamp': timestamp,
            'X-LiveSun-Signature': 'sha256=' + digest}


def probe_receiver(product_code, destination, secret):
    """Teste assinado sem efeito comercial, com confirmação da identidade do produto."""
    validate_webhook_destination(destination)
    nonce=secrets.token_hex(32)
    raw=json.dumps({'produto':product_code,'nonce':nonce},separators=(',',':')).encode()
    headers=signed_headers(secret,raw)
    headers['X-LiveSun-Event']='INTEGRACAO_TESTE'
    try:
        with requests.Session() as http:
            http.trust_env=False
            response=http.post(destination,data=raw,headers=headers,timeout=(3,8),allow_redirects=False,stream=True)
            try:
                if response.status_code in (404,405):
                    raise BusinessError('O endereço não é um receptor POST de webhook. Confira a URL completa.')
                if response.status_code in (401,403):
                    raise BusinessError('O receptor não confirmou a assinatura. Confira o produto, segredo HMAC e horário dos servidores.')
                if response.status_code!=200:
                    raise BusinessError('O produto não está pronto para receber eventos. A configuração anterior foi preservada.')
                body=response.raw.read(8193,decode_content=True)
                if len(body)>8192:
                    raise BusinessError('Confirmação do receptor excede o limite permitido.')
                data=json.loads(body)
            finally:
                response.close()
        proof=hmac.new(secret.encode(),(product_code+':'+nonce).encode(),hashlib.sha256).hexdigest()
        if (not isinstance(data,dict) or data.get('produto')!=product_code or data.get('nonce')!=nonce
                or data.get('status')!='receptor_pronto' or not isinstance(data.get('prova'),str)
                or not hmac.compare_digest(proof,data['prova'])):
            raise BusinessError('O endereço não confirmou a identidade deste produto. Configuração não salva.')
    except (requests.RequestException,OSError,ValueError,TypeError) as error:
        if isinstance(error,BusinessError):
            raise
        raise BusinessError('Não foi possível confirmar o receptor. Confira serviço, URL e conexão; configuração não salva.') from None


def configure_receiver(product,destination,secret):
    # Não persiste nada antes do teste completo. Falha não altera o receptor anterior.
    probe_receiver(product.codigo,destination,secret)
    before=snapshot(product)
    product.url_webhook,product.webhook_secret=destination,encrypt(secret)
    audit(product,'WEBHOOK_CONFIGURADO_E_VALIDADO',before)
    # Todas as entregas sem sucesso passam a usar a configuração confirmada.
    entries=db.session.scalars(db.select(WebhookEntrega).where(WebhookEntrega.produto_id==product.id,
        WebhookEntrega.status.in_(['PENDENTE','FALHA','ESGOTADA','CONFIGURACAO'])).with_for_update(skip_locked=True)).all()
    for entry in entries:
        old=snapshot(entry)
        entry.url_destino,entry.status,entry.proxima_tentativa=destination,'PENDENTE',now()
        entry.lease_ate=None
        audit(entry,'WEBHOOK_RECUPERADO_APOS_CONFIGURACAO',old)
    return len(entries)


def recover_deliveries():
    """Recupera automaticamente após correção/retorno, sem repetir eventos em URL inválida."""
    from app.models import Produto
    product_ids=list(db.session.scalars(db.select(WebhookEntrega.produto_id).where(
        WebhookEntrega.status.in_(['CONFIGURACAO','ESGOTADA']),WebhookEntrega.proxima_tentativa<=now()).distinct()))
    for identifier in product_ids:
        product=db.session.get(Produto,identifier)
        rows=db.session.scalars(db.select(WebhookEntrega).where(WebhookEntrega.produto_id==identifier,
            WebhookEntrega.status.in_(['CONFIGURACAO','ESGOTADA']),WebhookEntrega.proxima_tentativa<=now())
            .with_for_update(skip_locked=True)).all()
        if not rows:
            continue
        try:
            if not product or not product.webhook_secret or not product.url_webhook:
                raise BusinessError('Configuração incompleta.')
            probe_receiver(product.codigo,product.url_webhook,decrypt(product.webhook_secret))
        except (BusinessError,InvalidToken,ValueError):
            for row in rows:
                row.proxima_tentativa=now()+timedelta(minutes=5)
            db.session.commit()
            continue
        for row in rows:
            before=snapshot(row)
            row.status,row.url_destino,row.proxima_tentativa='PENDENTE',product.url_webhook,now()
            audit(row,'WEBHOOK_RECUPERACAO_AUTOMATICA',before)
        db.session.commit()


def resend(entry):
    if entry.status not in ('FALHA', 'ESGOTADA', 'CONFIGURACAO'):
        raise BusinessError('Somente entregas com falha podem ser reenviadas.')
    before = snapshot(entry)
    # Reenvio explícito pode usar destino corrigido; tentativas anteriores permanecem auditadas.
    destination = entry.produto.url_webhook
    if not destination:
        raise BusinessError('Configure o receptor de webhook do produto antes de reenviar.')
    validate_webhook_destination(destination)
    entry.url_destino = destination
    entry.status, entry.proxima_tentativa, entry.lease_ate = 'PENDENTE', now(), None
    audit(entry, 'WEBHOOK_REENVIO', before)


def resend_product_failures(product_id):
    entries = db.session.scalars(db.select(WebhookEntrega).where(
        WebhookEntrega.produto_id == product_id, WebhookEntrega.status.in_(['FALHA','ESGOTADA','CONFIGURACAO']))
        .order_by(WebhookEntrega.id).with_for_update(skip_locked=True)).all()
    for entry in entries:
        resend(entry)
    return len(entries)


def dispatch_one():
    instant = now()
    entry = db.session.scalar(db.select(WebhookEntrega).where(
        or_(db.and_(WebhookEntrega.status.in_(['PENDENTE', 'FALHA']),
                    WebhookEntrega.proxima_tentativa <= instant),
            db.and_(WebhookEntrega.status == 'ENVIANDO', WebhookEntrega.lease_ate < instant)))
        .order_by(WebhookEntrega.id).with_for_update(skip_locked=True))
    if entry is None:
        db.session.rollback()
        return False
    identifier = entry.id
    if entry.produto.url_webhook and entry.url_destino!=entry.produto.url_webhook:
        before=snapshot(entry)
        entry.url_destino=entry.produto.url_webhook
        audit(entry,'WEBHOOK_DESTINO_ATUALIZADO_AUTOMATICAMENTE',before)
    entry.status, entry.lease_ate = 'ENVIANDO', instant + timedelta(seconds=90)
    entry.tentativas += 1
    db.session.commit()
    code, error = None, None
    try:
        if not entry.produto.webhook_secret:
            raise BusinessError('Credencial de webhook não configurada.')
        validate_webhook_destination(entry.url_destino)
        raw = json.dumps(entry.payload, separators=(',', ':'), ensure_ascii=False).encode()
        headers = signed_headers(decrypt(entry.produto.webhook_secret), raw)
        headers['X-LiveSun-Event'] = entry.payload['evento']
        # Nunca segue redirects nem registra corpo retornado pelo produto.
        with requests.Session() as http:
            http.trust_env = False
            response = http.post(entry.url_destino, data=raw, headers=headers, timeout=(5, 15),
                                 allow_redirects=False, stream=True)
            code = response.status_code
            response.close()
        if not 200 <= code < 300:
            error = 'METODO_NAO_PERMITIDO_CONFIRA_URL_RECEPTOR' if code == 405 else 'HTTP_NAO_SUCESSO'
    except (BusinessError,InvalidToken):
        error='CONFIGURACAO_RECEPTOR_INVALIDA'
    except (requests.RequestException, OSError, ValueError):
        error = 'FALHA_TRANSPORTE_OU_DESTINO'
    entry = db.session.get(WebhookEntrega, identifier)
    entry.resposta_http, entry.erro, entry.lease_ate = code, error, None
    entry.status = 'ENTREGUE' if error is None else 'FALHA'
    if error and entry.tentativas >= current_app.config['WEBHOOK_MAX_ATTEMPTS']:
        entry.status = 'ESGOTADA'
    entry.proxima_tentativa = now() + timedelta(seconds=min(3600, 5 * 2 ** min(entry.tentativas, 10)))
    if error and (code in (301,302,307,308,400,401,403,404,405,415,422) or error=='CONFIGURACAO_RECEPTOR_INVALIDA'):
        entry.status='CONFIGURACAO'
        entry.proxima_tentativa=now()+timedelta(minutes=5)
    db.session.add(WebhookTentativa(entrega_id=entry.id, numero=entry.tentativas,
                                    resposta_http=code, erro=error))
    db.session.commit()
    return True