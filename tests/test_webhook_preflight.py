import hashlib
import hmac
import io
import json
from unittest.mock import patch,Mock
import pytest
from app.extensions import db
from app.models import Produto,WebhookEntrega
from app.models.base import now
from app.security import decrypt
from app.services.assinatura_service import create,BusinessError
from app.services.webhook_service import probe_receiver,configure_receiver,recover_deliveries


class HTTPBody(io.BytesIO):
    def read(self,amt=None,decode_content=False):
        return super().read(amt)


def valid_response(url,**kwargs):
    request=json.loads(kwargs['data'])
    secret='h'*40
    body={**request,'status':'receptor_pronto','prova':hmac.new(secret.encode(),
        (request['produto']+':'+request['nonce']).encode(),hashlib.sha256).hexdigest()}
    return Mock(status_code=200,raw=HTTPBody(json.dumps(body).encode()))


def test_preflight_checks_identity_and_secret(app):
    with patch('app.services.webhook_service.validate_destination'),patch('requests.Session.post',side_effect=valid_response):
        probe_receiver('PROPOSTAS','https://propostas.livesun.com.br/webhooks/assinatura','h'*40)
        with pytest.raises(BusinessError):
            probe_receiver('PROPOSTAS','https://propostas.livesun.com.br/webhooks/assinatura','wrong-secret')


@pytest.mark.parametrize('code',[401,404,405,503])
def test_failed_preflight_keeps_previous_configuration(app,code):
    product=db.session.get(Produto,app.test_ids['produto_id'])
    old_url,old_secret=product.url_webhook,product.webhook_secret
    with patch('app.services.webhook_service.validate_destination'),patch('requests.Session.post',return_value=Mock(status_code=code)):
        with pytest.raises(BusinessError):
            configure_receiver(product,'https://propostas.livesun.com.br/new-hook','h'*40)
    assert product.url_webhook==old_url and product.webhook_secret==old_secret


def test_configuration_recovers_old_queue_without_new_event(app):
    create(app.test_ids);db.session.commit()
    delivery=db.session.scalar(db.select(WebhookEntrega))
    original=delivery.evento_id
    delivery.status='ESGOTADA';delivery.tentativas=8
    db.session.commit()
    with patch('app.services.webhook_service.validate_destination'),patch('requests.Session.post',side_effect=valid_response):
        count=configure_receiver(delivery.produto,'https://propostas.livesun.com.br/fixed-hook','h'*40)
    db.session.commit()
    assert count==1 and delivery.status=='PENDENTE' and delivery.evento_id==original
    assert delivery.tentativas==8 and delivery.url_destino.endswith('/fixed-hook')


def test_automatic_recovery_waits_until_product_is_verified(app):
    create(app.test_ids);db.session.commit()
    delivery=db.session.scalar(db.select(WebhookEntrega))
    delivery.status='CONFIGURACAO';delivery.proxima_tentativa=now();db.session.commit()
    with patch('app.services.webhook_service.probe_receiver',side_effect=BusinessError('wrong product')):
        recover_deliveries()
    assert delivery.status=='CONFIGURACAO'
    delivery.proxima_tentativa=now();db.session.commit()
    with patch('app.services.webhook_service.probe_receiver'):
        recover_deliveries()
    assert delivery.status=='PENDENTE'


def test_html_200_is_not_a_receiver_confirmation(app):
    response=Mock(status_code=200,raw=HTTPBody(b'<html>login</html>'))
    with patch('app.services.webhook_service.validate_destination'),patch('requests.Session.post',return_value=response):
        with pytest.raises(BusinessError):
            probe_receiver('PROPOSTAS','https://propostas.livesun.com.br/hook','h'*40)