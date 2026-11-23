from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
import requests

from app.extensions import db
from app.models import OperacaoAsaas
from app.models.base import now
from app.services.asaas_service import enqueue, process_one
from test_comercial_phase import subscription


@pytest.mark.parametrize('failure', ['timeout', 429, 503])
def test_read_failures_retry_automatically_with_backoff(app, failure):
    obj = subscription(app)
    enqueue(obj, 'SINCRONIZAR')
    db.session.commit()
    op_id = db.session.scalar(db.select(OperacaoAsaas.id))
    response = Mock(status_code=failure, content=b'{}') if isinstance(failure, int) else None
    error = requests.Timeout('should not leak') if failure == 'timeout' else None
    with patch('requests.Session.request', side_effect=error, return_value=response):
        assert process_one()
    op = db.session.get(OperacaoAsaas, op_id)
    assert op.status == 'PENDENTE' and op.tentativas == 1
    assert op.erro in ('ASAAS_CONEXAO_LEITURA', 'ASAAS_INDISPONIVEL')
    assert now() < op.proxima_tentativa <= now() + timedelta(seconds=31)
    assert not process_one()


@pytest.mark.parametrize('failure,category', [(401, 'ASAAS_AUTENTICACAO'), (400, 'ASAAS_REQUISICAO_RECUSADA')])
def test_definitive_rejection_is_visible_without_auto_retry(app, failure, category):
    obj = subscription(app)
    enqueue(obj, 'SINCRONIZAR'); db.session.commit()
    op_id = db.session.scalar(db.select(OperacaoAsaas.id))
    with patch('requests.Session.request', return_value=Mock(status_code=failure, content=b'{}')):
        assert process_one()
    op = db.session.get(OperacaoAsaas, op_id)
    assert (op.status, op.erro) == ('REVISAR', category)


def test_uncertain_post_is_not_repeated(app):
    obj = subscription(app)
    obj.asaas_subscription_id = None
    obj.asaas_customer_id = 'already-existing'
    enqueue(obj, 'SINCRONIZAR'); db.session.commit()
    op_id = db.session.scalar(db.select(OperacaoAsaas.id))
    response = Mock(status_code=200, content=b'{}')
    response.json.return_value = {'data': [], 'hasMore': False}
    with patch('requests.Session.request', side_effect=[response, response, requests.Timeout('sensitive')]) as send:
        assert process_one()
        assert send.call_count == 3
    op = db.session.get(OperacaoAsaas, op_id)
    assert (op.status, op.erro) == ('REVISAR', 'ASAAS_RESPOSTA_INDEFINIDA')
    assert not process_one()


def test_success_after_read_failure_uses_same_operation(app):
    obj = subscription(app)
    enqueue(obj, 'CONSULTAR'); db.session.commit()
    op_id = db.session.scalar(db.select(OperacaoAsaas.id))
    with patch('requests.Session.request', side_effect=requests.Timeout):
        assert process_one()
    op = db.session.get(OperacaoAsaas, op_id)
    op.proxima_tentativa = now() - timedelta(seconds=1)
    db.session.commit()
    response = Mock(status_code=200, content=b'{}')
    response.json.return_value = {'data': [], 'hasMore': False}
    with patch('requests.Session.request', return_value=response):
        assert process_one()
    op = db.session.get(OperacaoAsaas, op_id)
    assert op.status == 'CONCLUIDA' and op.tentativas == 2 and op.erro is None