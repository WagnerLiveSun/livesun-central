# Entrega 4 — implementação local e publicação condicionada

Conferência: 19/11/2026. **Nenhuma publicação autorizada ou executada.**

## Banco de produção: evidências e limites

Conexão do perfil local `.env.postgresql`, usando `default_transaction_read_only=on`,
`SHOW transaction_read_only=on`, timeout de conexão e de consulta. Não foram
executados DDL, downgrade, seed, exclusão ou atualização de registros.

- Revisão efetivamente registrada: **20261119_02**. A cadeia local até ela é
  `20261112_01 → 02 → 03 → 04 → 20261118_01 → 20261119_01 → 02`.
  Isso é evidência do registro Alembic e do esquema inspecionado, não histórico
  independente de cada comando que foi executado no passado.
- Conferidos campos, índices, constraints únicas e checks de clientes,
  assinaturas, cobranças, eventos e notificações. Há separação de customer IDs
  por ambiente e unicidade composta ambiente/payment e ambiente/subscription.
- Duas assinaturas ATIVA (#1 e #3) e uma TRIAL (#2), sem vínculos Asaas.
- Clientes #1 (`CAD_1_1`) e #2 (`CAD_1_2`); nenhum candidato encontrado pelo
  marcador `test` no nome/código ou domínio `example.com`. Não é prova de que
  não houve testes manuais. Classificação definitiva exige responsável pelo cadastro.
- Zero cobranças, zero eventos Asaas e zero configurações Asaas. Produto
  PROPOSTAS sem configuração Asaas. Portanto **não é possível confirmar sandbox
  ou produção em testes anteriores, nem consultar os webhooks remotos** com a
  configuração disponível. Não cadastrar outro webhook sem consultar a conta.
- O esquema tem `assinaturas.status VARCHAR(20)`, insuficiente para
  `PAGO_AGUARDANDO_LIBERACAO`. Foi preparada **20261119_03**, que apenas amplia
  para VARCHAR(32), sem atualizar dados. **NÃO aplicada em produção.**

Repetição da auditoria, a partir da raiz do Central:

```powershell
.\.venv\Scripts\python.exe scripts\conferir_producao_readonly.py --env-file 'D:\App_LiveSun\LiveSun_CentralControle\livesun-central\.env.postgresql'
```

Não usar os inicializadores locais, `render_prepare` antigo, `flask db upgrade`,
scripts de migração de configurações ou seeds para fazer esta conferência.

### Compatibilidade do código publicado

Não houve acesso à identificação do artefato/SHA efetivamente publicado.
O HEAD local anterior do Central é `b1ac9eb` (18/11/2026) e do Propostas,
`d3aa8f3` (18/11/2026); não presumir que sejam os publicados. Os status e campos
legados existentes continuam presentes. Não há registros no status novo no banco.
O caminho novo de status longo não funciona no PostgreSQL atual até a ampliação.
Não declarar compatibilidade integral do serviço publicado sem conferir o SHA,
health e logs do serviço. Retornar somente a um artefato cuja compatibilidade
com as revisões existentes tenha sido demonstrada.

## Fluxo entregue

- Central reaproveita contratação, assinatura, cobrança, fila Asaas e outbox.
- Mensal 80/MONTHLY; anual integral 600/YEARLY; valores definidos no servidor.
- UNDEFINED e link da fatura para escolha do meio de pagamento. Confirmar Pix
  habilitado na conta durante aceite controlado.
- Serialização por cliente, unicidade existente e recuperação por referência;
  contratação repetida mostra a vigente. Resposta ambígua do gateway continua
  em REVISAR, sem repetir POST cegamente.
- Assinatura vigente sem cobrança é reaproveitada; datas e quota do trial não
  são reiniciadas. Assinatura de outro ambiente exige reconciliação manual.
- Propostas: rota autenticada `/central/contratar`, cliente obtido do vínculo
  da empresa da sessão. Passagem HMAC com o segredo existente, audiência por
  prefixo/produto, validade de 5 minutos; Central troca o token por sessão
  restrita de 15 minutos e retira o token da URL. Não registrar query strings
  desse endpoint nos logs do proxy. POST permanece protegido por CSRF.
- Financeiro e acesso são exibidos separadamente. Pagamento não ativa nem
  remove ATIVA/TRIAL. Liberação exclusiva de superadmin/comercial/financeiro,
  paga no mesmo ambiente e com valor elegível, com usuário/data auditados.
- Os quatro e-mails usam o serviço atual e o mesmo worker. Financeiros são
  identificados por cobrança/tipo na outbox; CONFIRMED/RECEIVED não duplicam.
  Liberação usa exclusivamente o aviso existente. Sem backfill histórico.
  Falha ou resultado incerto do e-mail não desfaz pagamento. Resultado incerto
  não é reenviado automaticamente. Sandbox exige destinatário na allowlist.
- Em APP_ENV=production, cliente financeiro recusa sandbox; chave/URL/token
  globais não podem trocar o ambiente persistido silenciosamente.
- Nenhuma nova política de renovação, suspensão, cancelamento ou purga foi
  criada. A manutenção preexistente continua no worker; revisar sua fila antes
  de iniciar qualquer processo contra produção.

## Variáveis (somente nomes; preservar segredos existentes)

Central/web/worker: `APP_ENV=production`, `DB_ENGINE=postgresql`, `DATABASE_URL`,
`SECRET_KEY`, `JWT_SECRET`, `ENCRYPTION_KEY`, `TRUST_PROXY`,
`WEBHOOK_ALLOWED_HOSTS`, `WEBHOOK_ALLOW_LOCAL_HTTP=false`,
`RATELIMIT_STORAGE_URI` conforme arquitetura existente.

Túnel, se utilizado: `SSH_ENABLED`, `SSH_HOST`, `SSH_USER`, `SSH_PORT`,
`SSH_REMOTE_HOST` se exigido pela configuração, `SSH_REMOTE_PORT`, `SSH_LOCAL_PORT`,
`SSH_KEY_PATH`, `SSH_KNOWN_HOSTS_PATH`, `SSH_STARTUP_TIMEOUT_SECONDS`.

E-mails: `ACCESS_EMAIL_ENABLED` (liga a outbox existente e os avisos financeiros),
`BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`.
`EMAIL_TEST_RECIPIENTS`: lista separada por vírgulas, exclusivamente endereços
controlados para sandbox; vazia bloqueia e-mail sandbox.

Asaas: usar configuração criptografada existente no banco, vinculada ao produto.
Overrides opcionais `ASAAS_API_URL`, `ASAAS_API_KEY`, `ASAAS_WEBHOOK_TOKEN`:
se usados, exigir URL oficial explícita do mesmo ambiente. Não trocar a
`ENCRYPTION_KEY`, não exibir tokens e não copiar customer/payment IDs sandbox.

Propostas: `CENTRAL_ENABLED`, `CENTRAL_BASE_URL`, `CENTRAL_API_TOKEN`,
`CENTRAL_WEBHOOK_SECRET`, `CENTRAL_CACHE_TTL_SECONDS` (até 900),
`CENTRAL_FAILSAFE_MINUTES`, `CENTRAL_ALLOW_LOCAL_HTTP=false` e as variáveis de
banco/autenticação/Brevo já existentes. A passagem usa o segredo HMAC existente;
não exige nova credencial nem concessão de escopo write ao token de leitura.
`CENTRAL_CHECKOUT_URL` legado não é usado para identificar cliente na passagem.

## Worker e configuração de publicação

Comandos a partir da raiz do Central:

```sh
python -m flask --app wsgi worker
python scripts/with_ssh_tunnel.py worker
```

O segundo é a variante com túnel. O `render.yaml` atual usa **web e worker no
mesmo serviço supervisionado**, comando `python scripts/with_ssh_tunnel.py web-worker`.
Nesse modo, não iniciar outro worker separado inadvertidamente. `--once` também
processa manutenção e filas reais: **não é diagnóstico somente leitura**.
Não foi iniciado worker real nesta entrega.

`scripts/render_prepare.py` agora só verifica revisão em produção; não aplica
migration/seed/bootstrap e falha fechado se houver revisão pendente.

## Webhook: primeiro conferir o já existente

Após acesso autorizado à conta **de produção**, listar todas as páginas de
`GET /v3/webhooks`. Conferir URL, enabled, eventos, fila interrompida e token
sem imprimi-lo. Não foi possível fazer essa consulta: não há credencial Asaas
na configuração inspecionada. Não foi criado nem alterado webhook.

Reaproveitar o endpoint já configurado, se houver:

- `/api/v1/webhooks/asaas/producao` (ambiente explícito), ou
- `/api/asaas/webhook` (compatibilidade, exige token que identifique um único ambiente).

Eventos tratados: PAYMENT_CREATED, PAYMENT_CONFIRMED, PAYMENT_RECEIVED,
PAYMENT_OVERDUE, PAYMENT_REFUNDED. Autenticação por `asaas-access-token`, HTTPS.
Não apontar simultaneamente dois cadastros para o mesmo fluxo por conveniência.
Validar avisos automáticos da própria conta Asaas antes de habilitar os avisos
LiveSun para não duplicar comunicação de cobrança pelo provedor.

## Ordem exata, somente após aprovação final

1. Registrar SHA/configuração do Central, worker e Propostas atualmente publicados;
   preservar artefatos e backup verificado. Conferir filas existentes e plano de janela.
2. Conferir conta Asaas e webhook existentes somente por leitura; resolver bloqueios
   abaixo. Definir credenciais/configuração externamente apenas com aprovação.
3. Pausar o worker existente na janela autorizada para evitar manutenção/reprocessamento
   durante a troca. Não apagar filas, cobranças ou notificações.
4. Repetir auditoria de revisão. Após autorização específica, aplicar **somente**
   `20261119_02:20261119_03` pela cadeia Alembic normal (`flask --app wsgi db upgrade
   20261119_03`, no ambiente correto e túnel já validado). Não repetir 01/02, não stamp.
5. Publicar Central e validar health/revisão antes de liberar tráfego de contratação.
   No modo web-worker atual, web e worker sobem juntos: tratar como uma unidade,
   sem prometer publicação independente. Conferir filas antes dessa inicialização.
6. Se houver serviço worker independente, publicar o mesmo artefato do Central
   e iniciar **apenas esse** worker após o health; não manter o combinado também.
7. Publicar Propostas e validar login, quota, cache, passagem e reconhecimento de
   liberação. Não alterar CENTRAL_ENABLED automaticamente.
8. Só após aceite de ponta a ponta, habilitar tráfego/notificações/configuração
   de produção que tenham sido aprovados, reaproveitando o webhook existente.

## Verificação pós-publicação

- Central `/api/v1/health`, Propostas `/healthz`, revisão 20261119_03.
- Conferir novamente as assinaturas #1/#2/#3, datas, quotas e acesso sem alterações.
- Contratar com cliente controlado, mensal/anual, repetir clique e provar única
  assinatura/recorrência. Nenhuma cobrança de produção sem aprovação específica.
- Confirmar fatura, Pix/boleto e recorrência anual integral na conta.
- Confirmar tenant: alteração de parâmetro/cliente não muda a empresa autenticada.
- Reentrega do mesmo webhook, CONFIRMED seguido de RECEIVED e reconciliação:
  uma cobrança, um aviso de pagamento, sem ativação.
- Operador sem permissão recebe negativa; operador autorizado libera uma vez,
  usuário/data presentes. Segunda liberação não cria e-mail/evento novo.
- Confirmar recebimento de entitlement pelo Propostas e atualização da versão;
  renovar cobrança paga sem retirar acesso ATIVA.
- Conferir worker sem falhas, filas antigas, INCERTO/REVISAR e avisos do Asaas.
- Para qualquer ensaio usar apenas destinatários controlados; não enviar para
  clientes reais. Testes automatizados usam SQLite e HTTP bloqueado por padrão.

## Retorno compatível do código (sem downgrade)

Parar somente a nova contratação/worker na janela autorizada e retornar ao
artefato previamente testado contra o **esquema atual**, preservando as revisões
de migration 01/02/03 no pacote e o startup sem DDL. VARCHAR(32) aceita todos
os status anteriores. Não remover colunas, não limpar outbox e não reaplicar
migrations. Eventos financeiros/filas continuam armazenados e exigem conferência
antes de reiniciar o worker. Não voltar cegamente ao HEAD antigo: ele não conhece
as revisões locais novas e o startup antigo executa migrations automaticamente.
Não há artefato publicado de rollback identificado nesta conferência: é bloqueio
da publicação, não autorização para improvisar retorno.

## Pendências bloqueantes

1. Aprovação/aplicação da ampliação 20261119_03.
2. SHA e configuração efetivamente publicados, rollback testado e disponibilidade
   do serviço combinado no ambiente contratado.
3. Configuração Asaas de produção inexistente no banco consultado; validação dos
   meios de pagamento, credenciais e webhook remoto existente ainda não feita.
4. Origem de testes anteriores não comprovada; clientes #1/#2 não foram
   classificados como teste. Nenhuma remoção proposta ou executada.
5. Aceite de ponta a ponta com serviços reais somente após autorização, inclusive
   produção de cobrança, envio de e-mails e operação de worker.

## Arquivos desta continuidade

Base Central: `D:\App_LiveSun\LiveSun_CentralControle\livesun-central`.
Serviços: `app/services/asaas_service.py`, `assinatura_service.py`,
`notificacao_acesso_service.py`, novo `checkout_service.py`.
Rotas/config/modelo: `app/admin/assinaturas.py`, `app/api/assinaturas.py`
(formatação), `app/config.py`, `app/models/assinatura.py`.
Templates: `contratar_propostas.html`, `subscription.html`,
`subscription_actions.html`, `email/pagamento_confirmado.html`,
`email/cobranca_vencida.html`. Scripts: `scripts/render_prepare.py`, novo
`scripts/conferir_producao_readonly.py`. Migration: nova 20261119_03.
Testes: `tests/conftest.py`, `test_comercial_phase.py`, novo
`test_entrega4_checkout.py`. Este documento e relatório de validação.

Base Propostas: `D:\App_LiveSun\LiveSun_Propostas`.
`src/routes/central.py`, `src/services/central_client.py`,
`src/services/commercial_usage.py`, `src/templates/layout.html`,
`tests/conftest.py`, `tests/test_central.py`, `tests/test_commercial_usage.py`.

Já havia diversas modificações não commitadas e arquivos novos na chegada;
foram preservados. `git diff` também inclui a implementação anterior, não apenas
esta continuidade. Não foi criado commit nem efetuado push/publicação.