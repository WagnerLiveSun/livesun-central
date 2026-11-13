import requests
from urllib.parse import urlsplit
from flask import current_app
from app.extensions import db
from app.models import Assinatura
from app.security import decrypt
from .webhook_service import validate_destination, signed_headers
from .entitlement_service import effective
from .assinatura_service import record
from .auditoria_service import snapshot, audit


def reconcile_all(repair=False):
    result = {'verificadas': 0, 'divergentes': 0, 'indisponiveis': 0}
    identifiers = list(db.session.scalars(db.select(Assinatura.id)))
    for identifier in identifiers:
        subscription = db.session.get(Assinatura, identifier)
        # Apenas a assinatura vigente/mais recente do par cliente/produto é reconciliada.
        latest = db.session.scalar(db.select(Assinatura.id).filter_by(cliente_id=subscription.cliente_id,
            produto_id=subscription.produto_id).order_by(db.case((Assinatura.slot_vigente == 1, 0), else_=1), Assinatura.id.desc()).limit(1))
        if latest != identifier:
            continue
        product = subscription.produto
        if not product.webhook_secret or not product.url_producao:
            result['indisponiveis'] += 1
            continue
        path = f'/central/estado/{subscription.cliente_id}'
        url = product.url_producao.rstrip('/') + path
        try:
            validate_destination(url)
            headers = signed_headers(decrypt(product.webhook_secret), urlsplit(url).path.encode())
            with requests.Session() as http:
                http.trust_env = False
                response = http.get(url, headers=headers, timeout=(3, 8), allow_redirects=False)
                if response.status_code != 200 or len(response.content) > 131072:
                    raise ValueError('Estado indisponível.')
                remote = response.json()
            local = effective(subscription)
            keys = ('assinatura_id', 'status', 'plano', 'acesso_produto', 'modulos', 'limites', 'versao')
            different = any(remote.get('entitlements', {}).get(k) != local.get(k) for k in keys)
            result['verificadas'] += 1
            if different:
                result['divergentes'] += 1
                audit(subscription, 'RECONCILIACAO_DIVERGENTE')
                if repair:
                    # Reenvia snapshot oficial sem simular mudança de status.
                    from uuid import uuid4
                    from app.models import EventoAssinatura, WebhookEntrega
                    from app.models.base import now, iso
                    from .auditoria_service import actor
                    who, ip = actor()
                    event_id = 'evt_' + uuid4().hex
                    db.session.add(EventoAssinatura(assinatura_id=identifier, evento_id=event_id,
                        tipo_evento='LIMITE_ALTERADO', dados_anteriores={}, dados_novos={'entitlements': local},
                        usuario_responsavel=who, ip_origem=ip))
                    db.session.flush()
                    db.session.add(WebhookEntrega(evento_id=event_id, produto_id=product.id,
                        url_destino=product.url_webhook, proxima_tentativa=now(), payload={
                            'evento': 'LIMITE_ALTERADO', 'evento_id': event_id, 'produto': product.codigo,
                            'cliente_id': str(subscription.cliente_id), 'assinatura_id': identifier,
                            'versao': subscription.versao, 'status_novo': subscription.status,
                            'ocorrido_em': iso(now()), 'entitlements': local, 'reconciliacao': True}))
            db.session.commit()
        except Exception:
            db.session.rollback()
            result['indisponiveis'] += 1
    return result