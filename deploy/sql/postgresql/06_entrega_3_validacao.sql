-- SOMENTE LEITURA | esperado 20261118_01.
SELECT version_num AS revisao FROM alembic_version;
SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns
WHERE table_schema=current_schema() AND table_name IN
('notificacoes_acesso','tentativas_notificacao_acesso') ORDER BY table_name,ordinal_position;
SELECT status, COUNT(*) FROM notificacoes_acesso GROUP BY status;
SELECT resultado, COUNT(*) FROM tentativas_notificacao_acesso GROUP BY resultado;
SELECT COUNT(*) AS eventos_duplicados FROM (
 SELECT evento_id FROM notificacoes_acesso GROUP BY evento_id HAVING COUNT(*) > 1
) AS duplicados;
-- Nao ha backfill: aplicar a estrutura nao cria mensagens de eventos antigos.