-- INSTALACAO EM BANCO VAZIO. Nao reaplicar em banco migrado.
-- Gerado das migrations Alembic. Nao contem credenciais nem dados de testes.
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20261112_01

CREATE TABLE auditoria_central (
    entidade VARCHAR(50) NOT NULL, 
    entidade_id INTEGER, 
    acao VARCHAR(60) NOT NULL, 
    anterior JSON NOT NULL, 
    novo JSON NOT NULL, 
    responsavel VARCHAR(150) NOT NULL, 
    ip_origem VARCHAR(45), 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_auditoria_central PRIMARY KEY (id)
);

CREATE TABLE clientes (
    codigo_externo VARCHAR(100) NOT NULL, 
    razao_social VARCHAR(200) NOT NULL, 
    nome_fantasia VARCHAR(200), 
    cnpj_cpf VARCHAR(18), 
    email_principal VARCHAR(254) NOT NULL, 
    telefone VARCHAR(30), 
    status VARCHAR(20) NOT NULL, 
    observacoes TEXT, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_clientes PRIMARY KEY (id), 
    CONSTRAINT uq_clientes_codigo_externo UNIQUE (codigo_externo)
);

CREATE TABLE produtos (
    codigo VARCHAR(50) NOT NULL, 
    nome VARCHAR(150) NOT NULL, 
    descricao TEXT, 
    url_producao VARCHAR(500), 
    url_webhook VARCHAR(500), 
    versao_api VARCHAR(20) NOT NULL, 
    webhook_secret TEXT, 
    permite_multiplos_planos BOOLEAN NOT NULL, 
    permite_modulos BOOLEAN NOT NULL, 
    ativo BOOLEAN NOT NULL, 
    token_version INTEGER NOT NULL, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_produtos PRIMARY KEY (id), 
    CONSTRAINT uq_produtos_codigo UNIQUE (codigo)
);

CREATE TABLE usuarios_central (
    nome VARCHAR(150) NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    senha_hash VARCHAR(255) NOT NULL, 
    perfil VARCHAR(20) NOT NULL, 
    ativo BOOLEAN NOT NULL, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_usuarios_central PRIMARY KEY (id), 
    CONSTRAINT uq_usuarios_central_email UNIQUE (email)
);

CREATE TABLE modulos (
    produto_id INTEGER NOT NULL, 
    codigo VARCHAR(50) NOT NULL, 
    nome VARCHAR(150) NOT NULL, 
    descricao TEXT, 
    depende_de JSON NOT NULL, 
    obrigatorio BOOLEAN NOT NULL, 
    ativo BOOLEAN NOT NULL, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_modulos PRIMARY KEY (id), 
    CONSTRAINT fk_modulos_produto_id_produtos FOREIGN KEY(produto_id) REFERENCES produtos (id), 
    CONSTRAINT uq_modulos_produto_id UNIQUE (produto_id, codigo)
);

CREATE TABLE planos (
    produto_id INTEGER NOT NULL, 
    codigo VARCHAR(50) NOT NULL, 
    nome VARCHAR(150) NOT NULL, 
    descricao TEXT, 
    valor_mensal NUMERIC(12, 2) NOT NULL, 
    periodicidade VARCHAR(20) NOT NULL, 
    limite_usuarios INTEGER, 
    limite_registros INTEGER, 
    limite_armazenamento_mb INTEGER, 
    limite_personalizado_json JSON NOT NULL, 
    ativo BOOLEAN NOT NULL, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_planos PRIMARY KEY (id), 
    CONSTRAINT fk_planos_produto_id_produtos FOREIGN KEY(produto_id) REFERENCES produtos (id), 
    CONSTRAINT uq_planos_produto_id UNIQUE (produto_id, codigo)
);

CREATE TABLE assinaturas (
    cliente_id INTEGER NOT NULL, 
    produto_id INTEGER NOT NULL, 
    plano_id INTEGER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    slot_vigente INTEGER, 
    data_inicio DATE NOT NULL, 
    data_fim DATE, 
    data_proxima_cobranca DATE, 
    motivo_status VARCHAR(500), 
    versao INTEGER NOT NULL, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_assinaturas PRIMARY KEY (id), 
    CONSTRAINT ck_assinaturas_status_valido CHECK (status IN ('TRIAL','ATIVA','SUSPENSA','BLOQUEADA','CANCELADA','EXPIRADA','EXCLUIDA')), 
    CONSTRAINT fk_assinaturas_cliente_id_clientes FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
    CONSTRAINT fk_assinaturas_plano_id_planos FOREIGN KEY(plano_id) REFERENCES planos (id), 
    CONSTRAINT fk_assinaturas_produto_id_produtos FOREIGN KEY(produto_id) REFERENCES produtos (id), 
    CONSTRAINT uq_assinaturas_cliente_id UNIQUE (cliente_id, produto_id, slot_vigente)
);

CREATE INDEX ix_assinaturas_cliente_id ON assinaturas (cliente_id);

CREATE TABLE plano_modulos (
    plano_id INTEGER NOT NULL, 
    modulo_id INTEGER NOT NULL, 
    liberado BOOLEAN NOT NULL, 
    limite INTEGER, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_plano_modulos PRIMARY KEY (id), 
    CONSTRAINT fk_plano_modulos_modulo_id_modulos FOREIGN KEY(modulo_id) REFERENCES modulos (id), 
    CONSTRAINT fk_plano_modulos_plano_id_planos FOREIGN KEY(plano_id) REFERENCES planos (id), 
    CONSTRAINT uq_plano_modulos_plano_id UNIQUE (plano_id, modulo_id)
);

CREATE TABLE assinatura_modulos (
    assinatura_id INTEGER NOT NULL, 
    modulo_id INTEGER NOT NULL, 
    liberado BOOLEAN NOT NULL, 
    limite INTEGER, 
    data_liberacao TIMESTAMP WITHOUT TIME ZONE, 
    data_remocao TIMESTAMP WITHOUT TIME ZONE, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_assinatura_modulos PRIMARY KEY (id), 
    CONSTRAINT fk_assinatura_modulos_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id), 
    CONSTRAINT fk_assinatura_modulos_modulo_id_modulos FOREIGN KEY(modulo_id) REFERENCES modulos (id), 
    CONSTRAINT uq_assinatura_modulos_assinatura_id UNIQUE (assinatura_id, modulo_id)
);

CREATE TABLE cobrancas (
    assinatura_id INTEGER NOT NULL, 
    competencia VARCHAR(7) NOT NULL, 
    valor NUMERIC(12, 2) NOT NULL, 
    vencimento DATE NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    data_pagamento TIMESTAMP WITHOUT TIME ZONE, 
    gateway VARCHAR(50), 
    referencia_externa VARCHAR(150), 
    observacoes TEXT, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_cobrancas PRIMARY KEY (id), 
    CONSTRAINT fk_cobrancas_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id), 
    CONSTRAINT uq_cobrancas_assinatura_id UNIQUE (assinatura_id, competencia)
);

CREATE TABLE entitlements (
    assinatura_id INTEGER NOT NULL, 
    chave VARCHAR(100) NOT NULL, 
    valor JSON, 
    limite INTEGER, 
    ativo BOOLEAN NOT NULL, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_entitlements PRIMARY KEY (id), 
    CONSTRAINT fk_entitlements_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id), 
    CONSTRAINT uq_entitlements_assinatura_id UNIQUE (assinatura_id, chave)
);

CREATE TABLE eventos_assinatura (
    assinatura_id INTEGER NOT NULL, 
    evento_id VARCHAR(50) NOT NULL, 
    tipo_evento VARCHAR(50) NOT NULL, 
    dados_anteriores JSON NOT NULL, 
    dados_novos JSON NOT NULL, 
    usuario_responsavel VARCHAR(150) NOT NULL, 
    ip_origem VARCHAR(45), 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_eventos_assinatura PRIMARY KEY (id), 
    CONSTRAINT fk_eventos_assinatura_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id), 
    CONSTRAINT uq_eventos_assinatura_evento_id UNIQUE (evento_id)
);

CREATE INDEX ix_eventos_assinatura_assinatura_id ON eventos_assinatura (assinatura_id);

CREATE TABLE webhook_entregas (
    evento_id VARCHAR(50) NOT NULL, 
    produto_id INTEGER NOT NULL, 
    url_destino VARCHAR(500) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    tentativas INTEGER NOT NULL, 
    resposta_http INTEGER, 
    erro VARCHAR(100), 
    payload JSON NOT NULL, 
    proxima_tentativa TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    lease_ate TIMESTAMP WITHOUT TIME ZONE, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_webhook_entregas PRIMARY KEY (id), 
    CONSTRAINT fk_webhook_entregas_evento_id_eventos_assinatura FOREIGN KEY(evento_id) REFERENCES eventos_assinatura (evento_id), 
    CONSTRAINT fk_webhook_entregas_produto_id_produtos FOREIGN KEY(produto_id) REFERENCES produtos (id), 
    CONSTRAINT uq_webhook_entregas_evento_id UNIQUE (evento_id)
);

CREATE INDEX ix_webhook_entregas_proxima_tentativa ON webhook_entregas (proxima_tentativa);

CREATE INDEX ix_webhook_entregas_status ON webhook_entregas (status);

CREATE TABLE webhook_tentativas (
    entrega_id INTEGER NOT NULL, 
    numero INTEGER NOT NULL, 
    resposta_http INTEGER, 
    erro VARCHAR(100), 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_webhook_tentativas PRIMARY KEY (id), 
    CONSTRAINT fk_webhook_tentativas_entrega_id_webhook_entregas FOREIGN KEY(entrega_id) REFERENCES webhook_entregas (id)
);

INSERT INTO alembic_version (version_num) VALUES ('20261112_01') RETURNING alembic_version.version_num;

-- Running upgrade 20261112_01 -> 20261112_02

CREATE TABLE config_asaas_assinaturas (
    ambiente VARCHAR(20) NOT NULL, 
    api_key TEXT NOT NULL, 
    webhook_token TEXT NOT NULL, 
    ativo BOOLEAN NOT NULL, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
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
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_eventos_asaas_central PRIMARY KEY (id), 
    CONSTRAINT uq_eventos_asaas_central_evento_externo UNIQUE (evento_externo)
);

CREATE TABLE credenciais_servico (
    produto_id INTEGER NOT NULL, 
    digest VARCHAR(64) NOT NULL, 
    nome VARCHAR(100) NOT NULL, 
    ativo BOOLEAN NOT NULL, 
    scopes JSON NOT NULL, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
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
    proxima_tentativa TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_operacoes_asaas_central PRIMARY KEY (id), 
    CONSTRAINT fk_operacoes_asaas_central_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id)
);

CREATE INDEX ix_operacoes_asaas_central_assinatura_id ON operacoes_asaas_central (assinatura_id);

CREATE TABLE purgas_produto (
    assinatura_id INTEGER NOT NULL, 
    operacao_id VARCHAR(50) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    executar_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    lease_ate TIMESTAMP WITHOUT TIME ZONE, 
    tentativas INTEGER NOT NULL, 
    antecipada BOOLEAN NOT NULL, 
    motivo VARCHAR(500) NOT NULL, 
    erro VARCHAR(100), 
    concluida_em TIMESTAMP WITHOUT TIME ZONE, 
    id SERIAL NOT NULL, 
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT pk_purgas_produto PRIMARY KEY (id), 
    CONSTRAINT fk_purgas_produto_assinatura_id_assinaturas FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id), 
    CONSTRAINT uq_purgas_produto_assinatura_id UNIQUE (assinatura_id), 
    CONSTRAINT uq_purgas_produto_operacao_id UNIQUE (operacao_id)
);

ALTER TABLE assinaturas ADD COLUMN excluida_em TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE assinaturas ADD COLUMN trial_ate DATE;

ALTER TABLE assinaturas ADD COLUMN cortesia BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE assinaturas ADD COLUMN cortesia_ate DATE;

ALTER TABLE assinaturas ADD COLUMN carencia_dias INTEGER DEFAULT '7' NOT NULL;

ALTER TABLE assinaturas ADD COLUMN suspensa_por_inadimplencia BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE assinaturas ADD COLUMN asaas_ambiente VARCHAR(20);

ALTER TABLE assinaturas ADD COLUMN asaas_customer_id VARCHAR(100);

ALTER TABLE assinaturas ADD COLUMN asaas_subscription_id VARCHAR(100);

ALTER TABLE assinaturas ADD COLUMN asaas_habilitado BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE assinaturas ADD COLUMN asaas_forma VARCHAR(20) DEFAULT 'BOLETO' NOT NULL;

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

