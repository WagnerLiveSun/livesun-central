"""Configuração isolada de provedores de pagamento alternativos."""
from alembic import op
import sqlalchemy as sa

revision = '20261123_01'
down_revision = '20261119_03'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('gateways_alternativos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('produto_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('ambiente', sa.String(length=20), nullable=False),
        sa.Column('url_api', sa.String(length=500), nullable=False),
        sa.Column('url_callback', sa.String(length=500)),
        sa.Column('credenciais_criptografadas', sa.Text(), nullable=False),
        sa.Column('ativo', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['produto_id'], ['produtos.id'], name='fk_gateways_alternativos_produto_id_produtos'),
        sa.PrimaryKeyConstraint('id', name='pk_gateways_alternativos'),
        sa.UniqueConstraint('produto_id', 'nome', 'ambiente', name='uq_gateway_alternativo_produto_nome_ambiente'))
    op.create_index('ix_gateways_alternativos_produto_id', 'gateways_alternativos', ['produto_id'])


def downgrade():
    raise RuntimeError('Downgrade desabilitado; preserve as configurações existentes.')