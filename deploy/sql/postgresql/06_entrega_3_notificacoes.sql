-- Entrega 3 | Central | PostgreSQL | aplicar UMA VEZ apos 20261112_04
-- Backup antes. Sem disparo retroativo de emails.
BEGIN;

CREATE TABLE notificacoes_acesso (
    id SERIAL NOT NULL,
    evento_id VARCHAR(50) NOT NULL,
    assinatura_id INTEGER NOT NULL,
    destinatario_hash VARCHAR(64) NOT NULL,
    status VARCHAR(25) NOT NULL,
    criada_em TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    proxima_tentativa TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    lease_ate TIMESTAMP WITHOUT TIME ZONE,
    tentativas INTEGER NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (evento_id),
    FOREIGN KEY(evento_id) REFERENCES eventos_assinatura (evento_id),
    FOREIGN KEY(assinatura_id) REFERENCES assinaturas (id)
);

CREATE TABLE tentativas_notificacao_acesso (
    id SERIAL NOT NULL,
    notificacao_id INTEGER NOT NULL,
    numero INTEGER NOT NULL,
    resultado VARCHAR(25) NOT NULL,
    categoria VARCHAR(40),
    iniciada_em TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    concluida_em TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY(notificacao_id) REFERENCES notificacoes_acesso (id)
);

CREATE INDEX ix_tentativas_notificacao_acesso_notificacao_id ON tentativas_notificacao_acesso (notificacao_id);


UPDATE alembic_version SET version_num='20261118_01' WHERE version_num='20261112_04';
COMMIT;
SELECT version_num AS revisao FROM alembic_version;
