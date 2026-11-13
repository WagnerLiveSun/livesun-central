"""Receber autocadastro de produtos para habilitação explícita."""
from alembic import op
import sqlalchemy as sa

revision='20261112_04'
down_revision='20261112_03'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('solicitacoes_cadastro',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('produto_id',sa.Integer(),sa.ForeignKey('produtos.id',name='fk_solicitacoes_cadastro_produto_id_produtos'),nullable=False),
        sa.Column('empresa_origem',sa.String(50),nullable=False),
        sa.Column('evento_origem',sa.String(50),nullable=False),
        sa.Column('razao_social',sa.String(200),nullable=False),
        sa.Column('nome_fantasia',sa.String(200)),
        sa.Column('cnpj_cpf',sa.String(18),nullable=False),
        sa.Column('email',sa.String(254),nullable=False),
        sa.Column('telefone',sa.String(30)),
        sa.Column('responsavel',sa.String(150),nullable=False),
        sa.Column('status',sa.String(25),nullable=False),
        sa.Column('cliente_id',sa.Integer(),sa.ForeignKey('clientes.id',name='fk_solicitacoes_cadastro_cliente_id_clientes')),
        sa.Column('assinatura_id',sa.Integer(),sa.ForeignKey('assinaturas.id',name='fk_solicitacoes_cadastro_assinatura_id_assinaturas')),
        sa.Column('motivo',sa.String(500)),
        sa.Column('tentativas_vinculo',sa.Integer(),nullable=False),
        sa.Column('erro_vinculo',sa.String(100)),
        sa.Column('proxima_tentativa',sa.DateTime()),
        sa.Column('vinculado_em',sa.DateTime()),
        sa.Column('criado_em',sa.DateTime(),nullable=False),
        sa.Column('atualizado_em',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('produto_id','empresa_origem',name='uq_solicitacoes_cadastro_produto_id'))
    op.create_index('ix_solicitacoes_cadastro_produto_id','solicitacoes_cadastro',['produto_id'])
    op.create_index('ix_solicitacoes_cadastro_status','solicitacoes_cadastro',['status'])


def downgrade():
    raise RuntimeError('Preserve solicitações e vínculos; use migration corretiva.')