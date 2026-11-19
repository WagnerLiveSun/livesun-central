# Entrega 3 — e-mail transacional de liberação PROPOSTAS

Banco real: PostgreSQL. Não foi alterado em produção nesta implementação.

Após backup, diagnóstico e autorização, aplicar uma vez:
1. `deploy/sql/postgresql/06_entrega_3_diagnostico.sql` (somente leitura).
2. `deploy/sql/postgresql/06_entrega_3_notificacoes.sql` (de 20261112_04 para 20261118_01).
3. `deploy/sql/postgresql/06_entrega_3_validacao.sql` (somente leitura).

Alternativa Alembic: `flask --app wsgi db upgrade 20261118_01`. Não aplicar ambos.
Preservar tabelas e deduplicação em rollback; não há downgrade destrutivo seguro.
Não modificar version_num manualmente para contornar estrutura ausente.

Environment: ACCESS_EMAIL_ENABLED=false por padrão, BREVO_API_KEY,
BREVO_SENDER_EMAIL (validado), BREVO_SENDER_NAME=LiveSun. Chave fora de Git/logs.
Manter envio desligado até migrations e homologação com mocks. Worker existente
é suficiente; nenhum processo novo foi criado. Precisa reiniciar web e worker
com a mesma configuração após publicação autorizada.

Somente eventos novos de PROPOSTAS: ASSINATURA_CRIADA em TRIAL/ATIVA,
ASSINATURA_ATIVADA e ASSINATURA_REATIVADA. Autocadastro aguarda VINCULADA;
demais fluxos aguardam entrega do evento ao produto. Nenhum contrato foi alterado.
Notificações de acesso revogado, ultrapassadas por outra liberação pendente ou com
destinatário alterado são canceladas para evitar anúncio incorreto.

Tabela notificacoes_acesso tem evento_id único e hash de destinatário, não corpo,
senha, token ou segredo. Tentativas são persistidas antes de chamar Brevo.
ACEITA_BREVO não prova entrega; recusa explícita é FALHA; 429 pode repetir até 3
vezes com intervalo; falha ambígua/timeout/processo interrompido é INCERTO e não
repete cegamente. Falha de e-mail não desfaz assinatura ou callback.

Não envia marketing, avisos de 3/1 dia, campanhas ou e-mails retroativos em massa.
Não resolve quota/pagamento, não acessa banco do Propostas. O link de acesso usa
url_producao do produto, validada como origem HTTPS sem credencial/query/fragmento.

Teste: `.venv\Scripts\python.exe -m pytest tests/test_notificacao_acesso.py -q`.
Nunca usar TEST_DATABASE_URL de banco real de uso: fixtures removem tabelas.
Consulte também no Propostas `deploy/ENTREGA_3.md` para aplicação coordenada e
diagnóstico dos dados demonstrativos antes de ativar a política única.