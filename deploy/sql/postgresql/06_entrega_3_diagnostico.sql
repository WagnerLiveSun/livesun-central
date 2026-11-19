-- SOMENTE LEITURA | PostgreSQL | Central. Sem dados pessoais ou credenciais.
SELECT current_database() AS banco, version() AS servidor;
SELECT version_num AS revisao FROM alembic_version;
SELECT a.status, COUNT(*) AS assinaturas FROM assinaturas a
JOIN produtos p ON p.id=a.produto_id WHERE p.codigo='PROPOSTAS' GROUP BY a.status;
SELECT COUNT(*) AS trials_sem_prazo FROM assinaturas a
JOIN produtos p ON p.id=a.produto_id
WHERE p.codigo='PROPOSTAS' AND a.status='TRIAL' AND a.trial_ate IS NULL;
SELECT COUNT(*) AS trials_sem_inicio FROM assinaturas a
JOIN produtos p ON p.id=a.produto_id
WHERE p.codigo='PROPOSTAS' AND a.status='TRIAL' AND a.data_inicio IS NULL;
SELECT s.status, COUNT(*) AS cadastros FROM solicitacoes_cadastro s
JOIN produtos p ON p.id=s.produto_id WHERE p.codigo='PROPOSTAS' GROUP BY s.status;
SELECT COUNT(*) AS trials_com_problema_periodo FROM assinaturas a
JOIN produtos p ON p.id=a.produto_id
WHERE p.codigo='PROPOSTAS' AND a.status='TRIAL' AND a.trial_ate < a.data_inicio;
-- Nao cria notificacoes retroativas; nao altera clientes, assinaturas ou vinculos.