-- SOMENTE bancos na revisao 20261112_02.
BEGIN;

-- Running upgrade 20261112_02 -> 20261112_03

ALTER TABLE produtos ADD COLUMN config_asaas_id INTEGER;

ALTER TABLE produtos ADD CONSTRAINT fk_produtos_config_asaas_id_config_asaas_assinaturas FOREIGN KEY(config_asaas_id) REFERENCES config_asaas_assinaturas (id);

UPDATE alembic_version SET version_num='20261112_03' WHERE alembic_version.version_num = '20261112_02';

-- Running upgrade 20261112_03 -> 20261112_04

CREATE TABLE solicitacoes_cadastro (
    id SERIAL NOT NULL, 
    produto_id INTEGER NOT NULL, 
    empresa_origem VARCHAR(50) NOT NULL, 
    evento_origem VARCHAR(50) NOT NULL, 
    razao_social VARCHAR(200) NOT NULL, 
    nome_fantasia VARCHAR(200), 
    cnpj_cpf VARCHAR(18) NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    telefone VARCHAR(30), 
    responsavel VARCHAR(150) NOT NULL, 
    status VARCHAR(25) NOT NULL, 
    cliente_id INTEGER, 
    assinatura_id INTEGER, 
    motivo VARCHAR(500), 
    tentativas_vinculo INTEGER NOT NULL, 
    erro_vinculo VARCHAR(100), 
    proxima_tentativa TIMESTAMP WITHOUT TIME ZONE, 
    vinculado_em TIMESTAMP WITHOUT TIME ZONE, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_solicitacoes_cadastro PRIMARY KEY (id), 
    CONSTRAINT uq_solicitacoes_cadastro_produto_id UNIQUE (produto_id, empresa_origem), 
    CONSTRAINT fk_solicitacoes_cadastro_produto_id_produtos FOREIGN KEY(produto_id) REFERENCES produtos (id), 
    CONSTRAINT fk_solicitacoes_cadastro_cliente_id_clientes FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
    CONSTRAINT fk_solicitacoes_cadastro_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id)
);

CREATE INDEX ix_solicitacoes_cadastro_produto_id ON solicitacoes_cadastro (produto_id);

CREATE INDEX ix_solicitacoes_cadastro_status ON solicitacoes_cadastro (status);

UPDATE alembic_version SET version_num='20261112_04' WHERE alembic_version.version_num = '20261112_03';

COMMIT;

