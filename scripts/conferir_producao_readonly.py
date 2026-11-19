"""Auditoria sem app factory, DDL, credenciais na saída ou chamadas HTTP."""
import argparse
import json
from pathlib import Path
import sys
from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def audit(env_file):
    cfg = dotenv_values(env_file)
    url = make_url(cfg.get('DATABASE_URL', ''))
    if url.drivername != 'postgresql+psycopg':
        raise ValueError('Use um perfil PostgreSQL explícito.')
    engine = create_engine(url, hide_parameters=True, connect_args={
        'connect_timeout': 5,
        'options': '-c default_transaction_read_only=on -c statement_timeout=10000'})
    try:
        with engine.connect() as connection:
            result = {'read_only': connection.scalar(text('SHOW transaction_read_only')),
                      'revisoes_registradas': connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all(),
                      'schema': {}}
            inspector = inspect(connection)
            for table in ('clientes', 'assinaturas', 'cobrancas', 'eventos_asaas_central',
                          'notificacoes_acesso', 'tentativas_notificacao_acesso'):
                result['schema'][table] = {
                    'columns': [{'name': col['name'], 'type': str(col['type']), 'nullable': col['nullable']}
                                for col in inspector.get_columns(table)],
                    'indexes': inspector.get_indexes(table),
                    'unique': inspector.get_unique_constraints(table),
                    'checks': inspector.get_check_constraints(table)}
            queries = {
                'configuracoes_asaas': 'SELECT id, ambiente, ativo FROM config_asaas_assinaturas',
                'produtos': 'SELECT id, codigo, config_asaas_id FROM produtos',
                'assinaturas': 'SELECT id, cliente_id, produto_id, status, asaas_ambiente, asaas_habilitado FROM assinaturas ORDER BY id',
                'cobrancas_por_ambiente': 'SELECT asaas_ambiente, status, count(*) AS total FROM cobrancas GROUP BY asaas_ambiente,status',
                'eventos_por_ambiente': 'SELECT ambiente, status, count(*) AS total FROM eventos_asaas_central GROUP BY ambiente,status',
                'candidatos_teste_nao_confirmados': "SELECT id, codigo_externo FROM clientes WHERE lower(razao_social) LIKE '%test%' OR lower(email_principal) LIKE '%@example.com' OR lower(codigo_externo) LIKE '%test%'"}
            for name, query in queries.items():
                result[name] = [dict(row) for row in connection.execute(text(query)).mappings()]
            return result
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.env_file.resolve()), ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as error:
        print('Conferência indisponível: ' + type(error).__name__ + '. Nenhum dado foi alterado.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())