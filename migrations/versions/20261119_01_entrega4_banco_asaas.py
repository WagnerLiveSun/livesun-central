"""Entrega 4: campos incrementais de cobrança Asaas no modelo existente."""
from alembic import op
import sqlalchemy as sa

revision = '20261119_01'
down_revision = '20261118_01'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clientes') as batch:
        batch.add_column(sa.Column('asaas_sandbox_customer_id', sa.String(100), nullable=True))
        batch.add_column(sa.Column('asaas_producao_customer_id', sa.String(100), nullable=True))
        batch.create_unique_constraint(
            'uq_clientes_asaas_sandbox_customer_id',
            ['asaas_sandbox_customer_id'])
        batch.create_unique_constraint(
            'uq_clientes_asaas_producao_customer_id',
            ['asaas_producao_customer_id'])
        batch.create_index('ix_clientes_asaas_sandbox_customer_id',
                           ['asaas_sandbox_customer_id'], unique=False)
        batch.create_index('ix_clientes_asaas_producao_customer_id',
                           ['asaas_producao_customer_id'], unique=False)

    with op.batch_alter_table('assinaturas') as batch:
        batch.drop_constraint('uq_assinaturas_asaas_subscription_id', type_='unique')
        batch.add_column(sa.Column('liberado_por_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('liberado_em', sa.DateTime(), nullable=True))
        batch.create_foreign_key(
            'fk_assinaturas_liberado_por_id_usuarios_central',
            'usuarios_central', ['liberado_por_id'], ['id'])
        batch.create_index('ix_assinaturas_liberado_por_id',
                           ['liberado_por_id'], unique=False)
        batch.create_index('ix_assinaturas_asaas_subscription_id',
                           ['asaas_subscription_id'], unique=False)
        batch.create_unique_constraint(
            'uq_assinaturas_asaas_ambiente_subscription_id',
            ['asaas_ambiente', 'asaas_subscription_id'])

    dialect = op.get_bind().dialect.name
    if dialect == 'postgresql':
        op.execute("ALTER TABLE assinaturas DROP CONSTRAINT IF EXISTS ck_assinaturas_status_valido")
        op.execute(
            "ALTER TABLE assinaturas ADD CONSTRAINT ck_assinaturas_status_valido "
            "CHECK (status IN ('TRIAL','ATIVA','PAGO_AGUARDANDO_LIBERACAO','SUSPENSA',"
            "'BLOQUEADA','CANCELADA','EXPIRADA','EXCLUIDA'))")
    elif dialect == 'mysql':
        op.execute("ALTER TABLE assinaturas DROP CONSTRAINT IF EXISTS ck_assinaturas_status_valido")
        op.execute(
            "ALTER TABLE assinaturas ADD CONSTRAINT ck_assinaturas_status_valido "
            "CHECK (status IN ('TRIAL','ATIVA','PAGO_AGUARDANDO_LIBERACAO','SUSPENSA',"
            "'BLOQUEADA','CANCELADA','EXPIRADA','EXCLUIDA'))")

    with op.batch_alter_table('cobrancas') as batch:
        batch.drop_constraint('uq_cobrancas_gateway_payment_id', type_='unique')
        batch.add_column(sa.Column('asaas_ambiente', sa.String(20), nullable=True))
        batch.add_column(sa.Column('billing_type', sa.String(20), nullable=True))
        batch.add_column(sa.Column('ultimo_evento', sa.String(100), nullable=True))
        batch.add_column(sa.Column('ultimo_evento_em', sa.DateTime(), nullable=True))
        batch.create_index('ix_cobrancas_gateway_payment_id',
                           ['gateway_payment_id'], unique=False)
        batch.create_index('ix_cobrancas_asaas_ambiente',
                           ['asaas_ambiente'], unique=False)
        batch.create_unique_constraint(
            'uq_cobrancas_asaas_ambiente_gateway_payment_id',
            ['asaas_ambiente', 'gateway_payment_id'])

    with op.batch_alter_table('eventos_asaas_central') as batch:
        batch.add_column(sa.Column('event_id', sa.String(150), nullable=True))
        batch.add_column(sa.Column('cobranca_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('data_recebimento', sa.DateTime(), nullable=True))
        batch.create_foreign_key(
            'fk_eventos_asaas_central_cobranca_id_cobrancas',
            'cobrancas', ['cobranca_id'], ['id'])
        batch.create_index('ix_eventos_asaas_central_event_id',
                           ['event_id'], unique=False)
        batch.create_index('ix_eventos_asaas_central_cobranca_id',
                           ['cobranca_id'], unique=False)
        batch.create_index('ix_eventos_asaas_central_status',
                           ['status'], unique=False)

    eventos = sa.table(
        'eventos_asaas_central',
        sa.column('id', sa.Integer()),
        sa.column('evento_externo', sa.String()),
        sa.column('ambiente', sa.String()),
        sa.column('event_id', sa.String()),
        sa.column('criado_em', sa.DateTime()),
        sa.column('data_recebimento', sa.DateTime()),
    )
    connection = op.get_bind()
    if connection.dialect.name != 'sqlite' or connection.engine is not None:
        try:
            result = connection.execute(sa.select(
                eventos.c.id,
                eventos.c.evento_externo,
                eventos.c.ambiente,
                eventos.c.criado_em,
            ))
            rows = result.mappings() if hasattr(result, 'mappings') else ()
            for row in rows:
                external = row['evento_externo'] or ''
                event_id = external.split(':', 1)[1] if ':' in external else external
                connection.execute(
                    eventos.update().where(eventos.c.id == row['id']).values(
                        event_id=event_id,
                        data_recebimento=row['criado_em'],
                    ))
        except AttributeError:
            pass

    with op.batch_alter_table('eventos_asaas_central') as batch:
        batch.alter_column('event_id', existing_type=sa.String(150), nullable=False)
        batch.create_unique_constraint(
            'uq_eventos_asaas_central_ambiente_event_id',
            ['ambiente', 'event_id'])


def downgrade():
    raise RuntimeError('Downgrade destrutivo desabilitado. Use migration corretiva preservando os dados.')
