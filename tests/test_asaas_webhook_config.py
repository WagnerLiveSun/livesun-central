from app.extensions import db
from app.models import ConfigAsaas, EventoAsaas
from app.security import encrypt
from test_comercial_phase import subscription


def payload(event='evt_test&123'):
    return {'id': event, 'event': 'PAYMENT_CREATED',
            'payment': {'id': 'pay_test', 'subscription': 'sub_test'}}


def test_database_token_works_when_global_url_missing(app, client):
    subscription(app)
    app.config.update(ASAAS_WEBHOOK_TOKEN='global-token-incompatible', ASAAS_API_URL='')
    headers = {'asaas-access-token': 't'*40}
    response = client.post('/api/asaas/webhook', headers=headers, json=payload())
    assert response.status_code == 200 and response.json['status'] == 'recebido'
    duplicate = client.post('/api/v1/webhooks/asaas/sandbox', headers=headers, json=payload())
    assert duplicate.status_code == 200 and duplicate.json['status'] == 'duplicado'
    assert db.session.scalar(db.select(db.func.count()).select_from(EventoAsaas)) == 1
    assert client.post('/api/asaas/webhook', headers={'asaas-access-token':'global-token-incompatible'},
                       json=payload('evt_invalid')).status_code == 401


def test_global_token_is_bound_only_to_matching_explicit_environment(app, client):
    subscription(app)
    db.session.add(ConfigAsaas(ambiente='producao', ativo=True, api_key=encrypt('prod'),
                               webhook_token=encrypt('p'*40)))
    db.session.commit()
    app.config.update(ASAAS_WEBHOOK_TOKEN='g'*40, ASAAS_API_URL='https://api-sandbox.asaas.com/v3')
    assert client.post('/api/v1/webhooks/asaas/sandbox', headers={'asaas-access-token':'g'*40},
                       json=payload('evt_sandbox')).status_code == 200
    assert client.post('/api/v1/webhooks/asaas/producao', headers={'asaas-access-token':'g'*40},
                       json=payload('evt_wrong_env')).status_code == 401
    assert client.post('/api/v1/webhooks/asaas/producao', headers={'asaas-access-token':'p'*40},
                       json=payload('evt_producao')).status_code == 200


def test_ambiguous_identical_tokens_do_not_identify_public_environment(app, client):
    subscription(app)
    db.session.add(ConfigAsaas(ambiente='producao', ativo=True, api_key=encrypt('prod'),
                               webhook_token=encrypt('t'*40)))
    db.session.commit()
    assert client.post('/api/asaas/webhook', headers={'asaas-access-token':'t'*40}, json=payload()).status_code == 401
    assert not db.session.scalar(db.select(EventoAsaas))