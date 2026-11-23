import importlib.util
import json
import re
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db
from app.models import GatewayAlternativo, InstituicaoBancaria
from test_central import login
from test_gateway_alternativo import gateway_form

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_matches_source_snapshot():
    rows = json.loads((ROOT / 'app/data/instituicoes_bancarias.json').read_text(encoding='utf-8'))
    assert len(rows) == len({row['codigo_banco'] for row in rows}) == 461
    assert all(re.fullmatch(r'[0-9]{3}', row['codigo_banco']) and len(row['nome_banco']) <= 150 for row in rows)
    assert next(row['nome_banco'] for row in rows if row['codigo_banco'] == '001') == 'Banco do Brasil S.A.'
    source = ROOT.parent.parent / 'LiveSun_Comercial_X' / 'migrations/mysql/042_create_instituicoes_bancarias.sql'
    if source.exists():
        pattern = re.compile(r"^INSERT INTO instituicoes_bancarias .* VALUES \('([0-9]{3})', '((?:[^']|'')*)', CURRENT_TIMESTAMP\)")
        original = [pattern.match(line) for line in source.read_text(encoding='utf-8').splitlines()
                    if line.startswith('INSERT INTO instituicoes_bancarias')]
        assert all(original)
        assert rows == [{'codigo_banco': match.group(1), 'nome_banco': match.group(2).replace("''", "'")}
                        for match in original]


def test_migration_upgrades_existing_schema_and_preserves_gateways(tmp_path):
    app = create_app({'TESTING': True, 'APP_ENV': 'development', 'DB_ENGINE': 'sqlite',
        'DATABASE_URL': 'sqlite:///' + str(tmp_path / 'instituicoes.db'),
        'SECRET_KEY': 's' * 40, 'JWT_SECRET': 'j' * 40, 'ENCRYPTION_KEY': Fernet.generate_key().decode()})
    with app.app_context():
        from flask_migrate import upgrade, check
        upgrade(revision='20261123_01')
        with db.engine.begin() as conn:
            conn.execute(text("INSERT INTO produtos (id,codigo,nome,versao_api,permite_multiplos_planos,permite_modulos,ativo,token_version,criado_em,atualizado_em) VALUES (1,'EXEMPLO','Exemplo','v1',0,0,1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT INTO gateways_alternativos (id,produto_id,nome,ambiente,url_api,credenciais_criptografadas,ativo,criado_em,atualizado_em) VALUES (1,1,'Provedor','sandbox','https://example.com','encrypted',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        upgrade()
        check()
        assert db.session.scalar(db.select(db.func.count()).select_from(InstituicaoBancaria)) == 461
        row = db.session.get(GatewayAlternativo, 1)
        assert row.nome == 'Provedor' and row.codigo_banco is None
        assert inspect(db.engine).get_foreign_keys('gateways_alternativos')


def test_gateway_validates_institution_and_preserves_leading_zero(app, client):
    db.session.add(InstituicaoBancaria(codigo_banco='001', nome_banco='Banco do Brasil S.A.'))
    db.session.commit()
    login(client)
    assert client.post('/configuracoes/gateways', data=gateway_form(app, codigo_banco='999')).status_code == 422
    assert client.post('/configuracoes/gateways', data=gateway_form(app, codigo_banco='1')).status_code == 422
    assert client.post('/configuracoes/gateways', data=gateway_form(app, codigo_banco='001')).status_code == 302
    row = db.session.scalar(db.select(GatewayAlternativo))
    assert row.codigo_banco == '001' and row.instituicao.nome_banco == 'Banco do Brasil S.A.'
    html = client.get('/configuracoes/gateways').get_data(as_text=True)
    assert '001 — Banco do Brasil S.A.' in html
    assert client.post('/configuracoes/gateways', data=gateway_form(app, id=str(row.id),
        codigo_banco='', api_key='', client_id='')).status_code == 422


def test_generated_postgresql_script_matches_both_migrations():
    path = ROOT / 'scripts/gerar_sql_instituicoes_bancarias.py'
    spec = importlib.util.spec_from_file_location('instituicoes_sql_generator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sql = module.OUTPUT.read_text(encoding='utf-8')
    assert sql == module.generate()
    assert sql.count('INSERT INTO instituicoes_bancarias') == 461
    assert 'BEGIN;' in sql and 'COMMIT;' in sql
    assert "version_num = '20261119_03'" in sql
    assert "version_num='20261123_02' WHERE version_num='20261119_03'" in sql
    assert 'REFERENCES instituicoes_bancarias (codigo_banco)' in sql
    assert "VALUES ('001', 'Banco do Brasil S.A.')" in sql