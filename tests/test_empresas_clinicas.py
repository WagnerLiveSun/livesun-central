from unittest.mock import patch
import pytest
from app.cli import seed_clinicas
from app.extensions import db
from app.models import Assinatura, Cobranca, Plano, Produto, SolicitacaoCadastro
from app.services.assinatura_service import BusinessError
from app.services.empresas_clinicas_service import list_companies, prepare_registration
from test_autocadastro import payload
from test_central import login


def company(identifier=123):
    return {'dados': payload(identifier, 'cad_' + 'a' * 32), 'ativo': True,
            'cliente_id': None, 'cadastro_novo': False, 'gestor_ativo': True}


def test_existing_clinic_review_without_email_confirmation(app, client):
    seed_clinicas()
    product = db.session.scalar(db.select(Produto).filter_by(codigo='CLINICAS'))
    product.url_producao = 'https://clinicas.example'
    product.webhook_secret = 'configured-test-secret'
    plan = Plano(produto_id=product.id, codigo='TESTE', nome='Teste', valor_mensal=0)
    db.session.add(plan); db.session.commit()
    login(client)
    assert 'Preparar clínicas existentes' in client.get('/cadastros-recebidos').get_data(as_text=True)
    with patch('app.services.empresas_clinicas_service.list_companies', return_value=([company()], None)):
        html = client.get('/empresas-clinicas').get_data(as_text=True)
        assert 'Preparar vínculo' in html and 'sem nova confirmação de e-mail' in html
    with patch('app.services.empresas_clinicas_service.fetch', return_value={'empresa': company()}):
        first = client.post('/empresas-clinicas/123/preparar')
        second = client.post('/empresas-clinicas/123/preparar')
    assert first.status_code == second.status_code == 302 and first.location == second.location
    row = db.session.scalar(db.select(SolicitacaoCadastro))
    assert row.status == 'PENDENTE'
    assert db.session.scalar(db.select(db.func.count()).select_from(Assinatura)) == 0
    result = client.post(f'/cadastros-recebidos/{row.id}/habilitar', data={'plano_id': plan.id, 'status': 'TRIAL', 'motivo': 'Vínculo conferido'})
    assert result.status_code == 302 and row.status == 'VINCULO_PENDENTE'
    assert db.session.scalar(db.select(db.func.count()).select_from(Cobranca)) == 0


@pytest.mark.parametrize('change', [{'ativo': False}, {'cliente_id': 12}, {'cadastro_novo': True}, {'gestor_ativo': False}, {'dados': payload(124)}])
def test_rejects_ineligible_existing_clinic(app, change):
    seed_clinicas()
    with patch('app.services.empresas_clinicas_service.fetch', return_value={'empresa': {**company(), **change}}):
        with pytest.raises(BusinessError):
            prepare_registration(123)
    assert db.session.scalar(db.select(db.func.count()).select_from(SolicitacaoCadastro)) == 0


def test_requires_complete_identity_and_permissions(app, client):
    seed_clinicas()
    bad = company(); bad['dados']['cnpj_cpf'] = ''
    with patch('app.services.empresas_clinicas_service.fetch', return_value={'empresa': bad}):
        with pytest.raises(BusinessError):
            prepare_registration(123)
    login(client, 'suporte')
    assert client.post('/empresas-clinicas/123/preparar').status_code == 403


def test_rejects_invalid_pagination(app):
    with patch('app.services.empresas_clinicas_service.fetch', return_value={'empresas': [company()], 'proximo': 123}):
        assert list_companies() == ([company()], 123)
    with patch('app.services.empresas_clinicas_service.fetch', return_value={'empresas': [company(), company()], 'proximo': None}):
        with pytest.raises(BusinessError):
            list_companies()