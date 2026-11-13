-- SOMENTE bancos na revisao 20261112_01. Backup antes de aplicar.
-- Running upgrade 20261112_01 -> 20261112_02

CREATE TABLE config_asaas_assinaturas (
    ambiente VARCHAR(20) NOT NULL, 
    api_key TEXT NOT NULL, 
    webhook_token TEXT NOT NULL, 
    ativo BOOL NOT NULL, 
    id INTEGER NOT NULL AUTO_INCREMENT, 
    criado_em DATETIME NOT NULL, 
    atualizado_em DATETIME NOT NULL, 
    CONSTRAINT pk_config_asaas_assinaturas PRIMARY KEY (id), 
    CONSTRAINT uq_config_asaas_assinaturas_ambiente UNIQUE (ambiente)
);

CREATE TABLE eventos_asaas_central (
    evento_externo VARCHAR(150) NOT NULL, 
    ambiente VARCHAR(20) NOT NULL, 
    payment_id VARCHAR(100), 
    subscription_id VARCHAR(100), 
    tipo VARCHAR(100) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    erro VARCHAR(100), 
    id INTEGER NOT NULL AUTO_INCREMENT, 
    criado_em DATETIME NOT NULL, 
    atualizado_em DATETIME NOT NULL, 
    CONSTRAINT pk_eventos_asaas_central PRIMARY KEY (id), 
    CONSTRAINT uq_eventos_asaas_central_evento_externo UNIQUE (evento_externo)
);

CREATE TABLE credenciais_servico (
    produto_id INTEGER NOT NULL, 
    digest VARCHAR(64) NOT NULL, 
    nome VARCHAR(100) NOT NULL, 
    ativo BOOL NOT NULL, 
    scopes JSON NOT NULL, 
    id INTEGER NOT NULL AUTO_INCREMENT, 
    criado_em DATETIME NOT NULL, 
    atualizado_em DATETIME NOT NULL, 
    CONSTRAINT pk_credenciais_servico PRIMARY KEY (id), 
    CONSTRAINT fk_credenciais_servico_produto_id_produtos FOREIGN KEY(produto_id) REFERENCES produtos (id), 
    CONSTRAINT uq_credenciais_servico_digest UNIQUE (digest)
);

CREATE INDEX ix_credenciais_servico_produto_id ON credenciais_servico (produto_id);

CREATE TABLE operacoes_asaas_central (
    assinatura_id INTEGER NOT NULL, 
    tipo VARCHAR(30) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    tentativas INTEGER NOT NULL, 
    erro VARCHAR(100), 
    proxima_tentativa DATETIME NOT NULL, 
    id INTEGER NOT NULL AUTO_INCREMENT, 
    criado_em DATETIME NOT NULL, 
    atualizado_em DATETIME NOT NULL, 
    CONSTRAINT pk_operacoes_asaas_central PRIMARY KEY (id), 
    CONSTRAINT fk_operacoes_asaas_central_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id)
);

CREATE INDEX ix_operacoes_asaas_central_assinatura_id ON operacoes_asaas_central (assinatura_id);

CREATE TABLE purgas_produto (
    assinatura_id INTEGER NOT NULL, 
    operacao_id VARCHAR(50) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    executar_em DATETIME NOT NULL, 
    lease_ate DATETIME, 
    tentativas INTEGER NOT NULL, 
    antecipada BOOL NOT NULL, 
    motivo VARCHAR(500) NOT NULL, 
    erro VARCHAR(100), 
    concluida_em DATETIME, 
    id INTEGER NOT NULL AUTO_INCREMENT, 
    criado_em DATETIME NOT NULL, 
    atualizado_em DATETIME NOT NULL, 
    CONSTRAINT pk_purgas_produto PRIMARY KEY (id), 
    CONSTRAINT fk_purgas_produto_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id), 
    CONSTRAINT uq_purgas_produto_assinatura_id UNIQUE (assinatura_id), 
    CONSTRAINT uq_purgas_produto_operacao_id UNIQUE (operacao_id)
);

ALTER TABLE assinaturas ADD COLUMN excluida_em DATETIME;

ALTER TABLE assinaturas ADD COLUMN trial_ate DATE;

ALTER TABLE assinaturas ADD COLUMN cortesia BOOL NOT NULL DEFAULT false;

ALTER TABLE assinaturas ADD COLUMN cortesia_ate DATE;

ALTER TABLE assinaturas ADD COLUMN carencia_dias INTEGER NOT NULL DEFAULT '7';

ALTER TABLE assinaturas ADD COLUMN suspensa_por_inadimplencia BOOL NOT NULL DEFAULT false;

ALTER TABLE assinaturas ADD COLUMN asaas_ambiente VARCHAR(20);

ALTER TABLE assinaturas ADD COLUMN asaas_customer_id VARCHAR(100);

ALTER TABLE assinaturas ADD COLUMN asaas_subscription_id VARCHAR(100);

ALTER TABLE assinaturas ADD COLUMN asaas_habilitado BOOL NOT NULL DEFAULT false;

ALTER TABLE assinaturas ADD COLUMN asaas_forma VARCHAR(20) NOT NULL DEFAULT 'BOLETO';

ALTER TABLE assinaturas ADD COLUMN codigo_legado VARCHAR(100);

ALTER TABLE assinaturas ADD CONSTRAINT uq_assinaturas_asaas_subscription_id UNIQUE (asaas_subscription_id);

ALTER TABLE cobrancas ADD COLUMN gateway_payment_id VARCHAR(100);

ALTER TABLE cobrancas ADD COLUMN invoice_url VARCHAR(1000);

ALTER TABLE cobrancas ADD CONSTRAINT uq_cobrancas_gateway_payment_id UNIQUE (gateway_payment_id);

UPDATE alembic_version SET version_num='20261112_02' WHERE alembic_version.version_num = '20261112_01';

-- Running upgrade 20261112_02 -> 20261112_03

ALTER TABLE produtos ADD COLUMN config_asaas_id INTEGER;

ALTER TABLE produtos ADD CONSTRAINT fk_produtos_config_asaas_id_config_asaas_assinaturas FOREIGN KEY(config_asaas_id) REFERENCES config_asaas_assinaturas (id);

UPDATE alembic_version SET version_num='20261112_03' WHERE alembic_version.version_num = '20261112_02';

-- Running upgrade 20261112_03 -> 20261112_04

CREATE TABLE solicitacoes_cadastro (
    id INTEGER NOT NULL AUTO_INCREMENT, 
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
    proxima_tentativa DATETIME, 
    vinculado_em DATETIME, 
    criado_em DATETIME NOT NULL, 
    atualizado_em DATETIME NOT NULL, 
    CONSTRAINT pk_solicitacoes_cadastro PRIMARY KEY (id), 
    CONSTRAINT uq_solicitacoes_cadastro_produto_id UNIQUE (produto_id, empresa_origem), 
    CONSTRAINT fk_solicitacoes_cadastro_produto_id_produtos FOREIGN KEY(produto_id) REFERENCES produtos (id), 
    CONSTRAINT fk_solicitacoes_cadastro_cliente_id_clientes FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
    CONSTRAINT fk_solicitacoes_cadastro_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id)
);

CREATE INDEX ix_solicitacoes_cadastro_produto_id ON solicitacoes_cadastro (produto_id);

CREATE INDEX ix_solicitacoes_cadastro_status ON solicitacoes_cadastro (status);

UPDATE alembic_version SET version_num='20261112_04' WHERE alembic_version.version_num = '20261112_03';

