import pytest
from unittest.mock import patch,Mock
from app.extensions import db
from app.models import Produto,WebhookEntrega,WebhookTentativa,Auditoria
from app.services.webhook_service import validate_webhook_destination,resend,dispatch_one
from app.services.assinatura_service import BusinessError,create


def test_home_page_is_not_a_webhook_endpoint(app):
    app.config.update(WEBHOOK_ALLOW_LOCAL_HTTP=True,WEBHOOK_ALLOWED_HOSTS=['localhost'])
    for url in ('http://localhost:5000','http://localhost:5000/'):
        with pytest.raises(BusinessError,match='receptor'):
            validate_webhook_destination(url)
    validate_webhook_destination('http://localhost:5000/webhooks/assinatura')


def test_manual_resend_uses_current_destination_and_keeps_attempt_history(app):
    create(app.test_ids);db.session.commit()
    entry=db.session.scalar(db.select(WebhookEntrega))
    entry.status='FALHA';entry.resposta_http=405;entry.erro='HTTP_NAO_SUCESSO';entry.tentativas=1
    previous=entry.url_destino
    db.session.add(WebhookTentativa(entrega_id=entry.id,numero=1,resposta_http=405,erro='HTTP_NAO_SUCESSO'))
    entry.produto.url_webhook='https://propostas.livesun.com.br/webhooks/assinatura-corrigida'
    db.session.commit()
    with patch('app.services.webhook_service.validate_destination'):
        resend(entry)
    db.session.commit()
    assert entry.url_destino==entry.produto.url_webhook
    assert entry.status=='PENDENTE'
    assert db.session.scalar(db.select(WebhookTentativa)).resposta_http==405
    audit=db.session.scalar(db.select(Auditoria).where(Auditoria.acao=='WEBHOOK_REENVIO'))
    assert audit.anterior['url_destino']==previous
    assert audit.novo['url_destino']==entry.url_destino


def test_405_has_actionable_failure_code(app):
    create(app.test_ids);db.session.commit()
    with patch('app.services.webhook_service.validate_destination'),patch('requests.Session.post',return_value=Mock(status_code=405)):
        assert dispatch_one()
    entry=db.session.scalar(db.select(WebhookEntrega))
    assert entry.status=='CONFIGURACAO'
    assert entry.erro=='METODO_NAO_PERMITIDO_CONFIRA_URL_RECEPTOR'


def test_batch_retry_is_scoped_to_product_and_keeps_event_ids(app):
    from app.services.webhook_service import resend_product_failures
    create(app.test_ids);db.session.commit()
    own=db.session.scalar(db.select(WebhookEntrega))
    own.status='ESGOTADA';own.tentativas=8
    original_event=own.evento_id
    other_product=Produto(codigo='OUTRO',nome='Outro',url_webhook='https://outro.example/hook')
    db.session.add(other_product);db.session.flush()
    # Outra entrega usa o mesmo snapshot para testar apenas o escopo do reenvio.
    from app.models import EventoAssinatura
    from app.models.base import now
    event=EventoAssinatura(assinatura_id=own.payload['assinatura_id'],evento_id='evt_other',tipo_evento='TESTE',
        dados_anteriores={},dados_novos={},usuario_responsavel='teste')
    db.session.add(event);db.session.flush()
    other=WebhookEntrega(evento_id='evt_other',produto_id=other_product.id,url_destino=other_product.url_webhook,
        status='ESGOTADA',tentativas=8,payload={},proxima_tentativa=now())
    db.session.add(other);db.session.commit()
    with patch('app.services.webhook_service.validate_destination'):
        assert resend_product_failures(own.produto_id)==1
    db.session.commit()
    assert own.status=='PENDENTE' and own.evento_id==original_event and own.tentativas==8
    assert other.status=='ESGOTADA'