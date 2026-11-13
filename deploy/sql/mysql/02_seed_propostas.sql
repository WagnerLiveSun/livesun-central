-- Seed inicial idempotente; sem credenciais ou operadores.
BEGIN;
INSERT INTO produtos (codigo, nome, url_producao, url_webhook, versao_api, permite_multiplos_planos, permite_modulos, ativo, token_version, criado_em, atualizado_em) SELECT 'PROPOSTAS' AS anon_1, 'LiveSun Propostas' AS anon_2, 'https://propostas.livesun.com.br' AS anon_3, 'https://propostas.livesun.com.br/webhooks/assinatura' AS anon_4, 'v1' AS anon_5, false AS anon_6, false AS anon_7, true AS anon_8, 1 AS anon_9, '2026-11-12 00:00:00' AS anon_10, '2026-11-12 00:00:00' AS anon_11 FROM DUAL 
WHERE NOT (EXISTS (SELECT produtos.id 
FROM produtos 
WHERE produtos.codigo = 'PROPOSTAS'));

INSERT INTO planos (produto_id, codigo, nome, descricao, valor_mensal, periodicidade, limite_personalizado_json, ativo, criado_em, atualizado_em) SELECT (SELECT produtos.id 
FROM produtos 
WHERE produtos.codigo = 'PROPOSTAS') AS anon_1, 'PROPOSTAS' AS anon_2, 'LiveSun Propostas' AS anon_3, 'Plano único do LiveSun Propostas' AS anon_4, 0 AS anon_5, 'mensal' AS anon_6, '{}' AS anon_7, true AS anon_8, '2026-11-12 00:00:00' AS anon_9, '2026-11-12 00:00:00' AS anon_10 FROM DUAL 
WHERE NOT (EXISTS (SELECT planos.id 
FROM planos 
WHERE planos.produto_id = (SELECT produtos.id 
FROM produtos 
WHERE produtos.codigo = 'PROPOSTAS') AND (planos.codigo = 'PROPOSTAS' OR planos.ativo IS true)));
COMMIT;
