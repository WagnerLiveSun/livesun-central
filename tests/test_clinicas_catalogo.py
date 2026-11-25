from app.cli import seed_clinicas
from app.extensions import db
from app.models import Produto, Plano, Assinatura, SolicitacaoCadastro
from app.security import service_token
from app.security import encrypt
from app.services.cadastro_service import receive, review, deliver_one
from unittest.mock import patch, Mock
import json
from test_central import login


def test_clinicas_seed_is_idempotent_without_plans_or_prices(app):
    seed_clinicas()
    seed_clinicas()
    products = db.session.scalars(db.select(Produto).filter_by(codigo='CLINICAS')).all()
    assert len(products) == 1
    product = products[0]
    assert product.nome == 'LiveSun Clínicas'
    assert product.url_producao is None and product.url_webhook is None
    assert db.session.scalar(db.select(db.func.count()).select_from(Plano).filter_by(produto_id=product.id)) == 0


def test_clinicas_can_submit_registration_without_authorizing_access(app, client):
    seed_clinicas()
    product = db.session.scalar(db.select(Produto).filter_by(codigo='CLINICAS'))
    token = service_token(product, ['read'])
    headers = {'Authorization': 'Bearer ' + token}
    payload = {'evento_id': 'cad_' + 'a' * 32, 'empresa_id': 123,
               'razao_social': 'Estética Exemplo', 'nome_fantasia': 'Estética Exemplo',
               'cnpj_cpf': '52998224725', 'email': 'gestora@example.com',
               'telefone': '11999990000', 'responsavel': 'Gestora Exemplo'}
    response = client.post('/api/v1/cadastros', json=payload, headers=headers)
    assert response.status_code == 202
    assert response.json['produto'] == 'CLINICAS'
    assert response.json['status'] == 'PENDENTE'
    assert response.json['cliente_id'] is None
    duplicate = client.post('/api/v1/cadastros', json=payload, headers=headers)
    assert duplicate.status_code == 200
    assert duplicate.json['solicitacao_id'] == response.json['solicitacao_id']
    assert db.session.scalar(db.select(db.func.count()).select_from(Assinatura)) == 0
    assert db.session.scalar(db.select(db.func.count()).select_from(SolicitacaoCadastro)) == 1


def test_novos_clientes_configures_clinicas_and_shows_received_registration(app, client):
    login(client)
    page = client.get('/cadastros-recebidos').get_data(as_text=True)
    assert 'Adicionar Clínicas ao catálogo' in page
    assert client.post('/cadastros-recebidos/configurar-clinicas').status_code == 302
    assert client.post('/cadastros-recebidos/configurar-clinicas').status_code == 302
    product = db.session.scalar(db.select(Produto).filter_by(codigo='CLINICAS'))
    assert product is not None
    payload = {'evento_id': 'cad_' + 'c' * 32, 'empresa_id': 789,
               'razao_social': 'Clínica Aurora', 'nome_fantasia': 'Clínica Aurora',
               'cnpj_cpf': '52998224725', 'email': 'aurora@example.com',
               'telefone': '11999990000', 'responsavel': 'Gestora Aurora'}
    response = client.post('/api/v1/cadastros', json=payload,
                           headers={'Authorization': 'Bearer ' + service_token(product, ['read'])})
    assert response.status_code == 202
    html = client.get('/cadastros-recebidos').get_data(as_text=True)
    assert 'Clínica Aurora' in html and 'LiveSun Clínicas' in html
    assert 'Adicionar Clínicas ao catálogo' not in html
    assert db.session.scalar(db.select(db.func.count()).select_from(Produto).filter_by(codigo='CLINICAS')) == 1
    assert db.session.scalar(db.select(db.func.count()).select_from(Plano).filter_by(produto_id=product.id)) == 0


def test_clinicas_catalog_setup_requires_permission(app, client):
    login(client, 'suporte')
    assert client.post('/cadastros-recebidos/configurar-clinicas').status_code == 403
    assert db.session.scalar(db.select(Produto).filter_by(codigo='CLINICAS')) is None


def test_clinicas_approval_sends_existing_signed_link_contract_with_document(app):
    seed_clinicas()
    product = db.session.scalar(db.select(Produto).filter_by(codigo='CLINICAS'))
    product.url_producao = 'https://clinicas.example'
    product.webhook_secret = encrypt('h' * 40)
    plan = Plano(produto_id=product.id, codigo='CLINICAS_TESTE', nome='Teste', valor_mensal=0, periodicidade='mensal', ativo=True, limite_personalizado_json={})
    db.session.add(plan)
    db.session.commit()
    payload = {'evento_id': 'cad_' + 'b' * 32, 'empresa_id': 456,
               'razao_social': 'Estética Exemplo', 'nome_fantasia': 'Estética Exemplo',
               'cnpj_cpf': '52998224725', 'email': 'gestora@example.com',
               'telefone': '11999990000', 'responsavel': 'Gestora Exemplo'}
    row, _ = receive(product, payload)
    db.session.commit()
    review(row.id, None, plan.id, 'ATIVA', 'Cadastro aprovado')
    db.session.commit()
    response = Mock(status_code=200)
    response.json.return_value = {'evento_id': row.evento_origem}
    with patch('app.services.cadastro_service.validate_destination'), patch('requests.Session.post', return_value=response) as post:
        assert deliver_one()
    sent = json.loads(post.call_args.kwargs['data'])
    assert sent['produto'] == 'CLINICAS'
    assert sent['cnpj_cpf'] == '52998224725'
    assert sent['empresa_id'] == 456
    assert sent['entitlements']['acesso_produto'] is True
    assert post.call_args.kwargs['headers']['X-LiveSun-Event'] == 'CADASTRO_HABILITADO'
    assert row.status == 'VINCULADA'