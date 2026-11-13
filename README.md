# LiveSun Central

**PostgreSQL local preparado:** use `D:\App_LiveSun\LiveSun_CentralControle\Iniciar_LiveSun_Central_PostgreSQL.bat`. Perfil separado `.env.postgresql`, banco `DbCentral` em `127.0.0.1:55433`; configuração MySQL preservada. Instruções em `docs/POSTGRESQL_LOCAL.md`. Dados de MySQL não são transferidos automaticamente.

**Fluxo atual de operação:** consulte `docs/AJUSTE_COBRANCA_PAINEL.md`. Cobrança é configurada no produto e operada na assinatura do cliente/plano. O processo anterior de migração por arquivo foi removido. Bonificações existentes são preservadas e não iniciam cobrança automaticamente.

## Nova etapa: Comercial, Asaas de assinaturas e purga

Leia `D:\App_LiveSun\LiveSun_CentralControle\livesun-central\docs\COMERCIAL_CENTRAL.md` para a operação atual. A política anterior de exclusão apenas lógica foi substituída por retenção de 60 dias e purga autorizada **por produto**, com implantação gradual do receptor (Comercial disponível; Propostas ainda pendente). O Central preserva dados financeiros/auditoria mínimos, não apaga globalmente clientes com outros produtos.

Asaas de **assinaturas LiveSun** agora possui configuração no painel, fila e webhook. Isso não migra os boletos Asaas/Inter operacionais dos clientes do Comercial. Nenhuma chamada real ao Asaas ou virada automática foi executada. Use a área **Integrações e chaves** e a **prévia de migração**; configure sandbox e homologue antes de produção.

O produto COMERCIAL é cadastrado pelo seed; planos/preços vêm da importação ou cadastro, não são presumidos. Após atualização, reinicie web e worker. A migration Central `20261112_02` e os SQLs incrementais acompanham esta etapa.

Aplicação independente de gestão comercial. Não acessa bancos dos produtos e não controla seus usuários, menus ou permissões funcionais.

## Estado da entrega

Implementados: aplicação Flask, models, migration inicial, API v1, painel Jinja, RBAC, auditoria, cobrança manual, fila transacional de webhooks, worker, reconciliação e integração no Propostas. Testes locais usam SQLite descartável; geração SQL offline cobre MySQL/PostgreSQL. Isso **não equivale a homologação nos servidores Hostinger, PostgreSQL/MontuDB ou Render**. Consulte `docs/ACEITE.md` e `docs/LIMITACOES.md` antes de publicar.

## Instalação Windows / desenvolvimento

### Inicialização por duplo clique (MySQL local)

Execute `D:\App_LiveSun\LiveSun_CentralControle\Iniciar_LiveSun_Central.bat` (há também um atalho `.bat` dentro da pasta do projeto). O banco local configurado no `.env` é `central`, em `localhost:3306`.

O inicializador verifica dependências, aplica migrations pendentes sem apagar registros, executa seed idempotente e solicita a criação do primeiro superadmin se necessário. Em seguida inicia web e worker e abre `http://127.0.0.1:5001/login`. Defina seu e-mail, nome e senha quando solicitado; não existe senha padrão. Mantenha a janela aberta; `Ctrl+C` encerra os processos.

Senhas de operadores aceitam qualquer conteúdo não vazio, sem requisito de complexidade ou tamanho mínimo além de um caractere. Permanece o limite técnico de 128 caracteres e o armazenamento por hash Argon2. Para produção, prefira senhas longas e únicas.

Para somente preparar/verificar o banco: `D:\App_LiveSun\LiveSun_CentralControle\Iniciar_LiveSun_Central.bat --prepare-only`. Para outra porta, acrescente `--port 5002`. O inicializador só funciona em desenvolvimento e recusa banco não vazio sem controle Alembic. Não utiliza debugger/reloader nem expõe a aplicação na rede.

Scripts SQL de instalação futura estão em `D:\App_LiveSun\LiveSun_CentralControle\livesun-central\deploy\sql`, separados por dialeto. Leia o README dessa pasta: não reaplique a estrutura SQL em banco já inicializado pelas migrations.

Execute a partir de `D:\App_LiveSun\LiveSun_CentralControle\livesun-central`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Gere valores independentes para `SECRET_KEY` e `JWT_SECRET` com o primeiro comando; use a saída do segundo em `ENCRYPTION_KEY`. Guarde tudo apenas no `.env` local ou gerenciador de segredos. Preserve backup da chave Fernet: perdê-la impede ler credenciais cadastradas. Não substitua essa chave sem recriptografar os segredos.

Configure um banco **novo e exclusivo**, depois:

```powershell
flask --app wsgi db upgrade
flask --app wsgi seed
flask --app wsgi create-admin
flask --app wsgi run --host 127.0.0.1 --port 5001
```

Em outro terminal, com o mesmo ambiente:

```powershell
flask --app wsgi worker
```

Abra o painel em `http://127.0.0.1:5001`. Não há conta ou senha padrão. `create-admin` solicita senha sem eco e cria hash Argon2. A aplicação não executa `create_all` no startup.

## Variáveis

| Variável | Uso |
|---|---|
| `APP_ENV` | `development` ou `production`; produção exige HTTPS e rate limit compartilhado |
| `SECRET_KEY` | Sessões e CSRF; mínimo 32 caracteres |
| `JWT_SECRET` | Assinatura JWT de serviço; diferente da chave de sessão |
| `ENCRYPTION_KEY` | Chave Fernet para credenciais de webhook no banco |
| `DB_ENGINE` | `mysql` ou `postgresql` |
| `DATABASE_URL` | URL SQLAlchemy com driver explícito |
| `DB_SSL_CA` | CA MySQL opcional, recomenda-se TLS com validação em banco remoto |
| `WEBHOOK_ALLOWED_HOSTS` | Hosts autorizados, separados por vírgula, sem wildcard |
| `PROPOSTAS_WEBHOOK_SECRET` | Inicialização opcional do HMAC no seed; mínimo 32 caracteres |
| `RATELIMIT_STORAGE_URI` | `memory://` apenas desenvolvimento; produção exige Redis |
| `TRUST_PROXY` | `true` somente atrás de um proxy confiável, sem acesso direto ao backend |

Exemplos de configuração, sem alterar código:

```dotenv
DB_ENGINE=mysql
DATABASE_URL=mysql+pymysql://usuario:senha@host:3306/livesun_central
```

```dotenv
DB_ENGINE=postgresql
DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/livesun_central?sslmode=verify-full&sslrootcert=/path/ca.pem
```

Caracteres especiais de usuário/senha devem ser percent-encoded. A escolha de driver, pool e sessão está em `app/database.py`; models e serviços não possuem ramificações por banco. Alternar URL **não transfere dados existentes**: uma mudança de banco exige procedimento de migração de dados e conferência independente.

### MySQL Hostinger

Crie banco e usuário exclusivos do Central; configure acesso remoto, firewall/IPs autorizados e TLS conforme o serviço contratado. Teste a conectividade a partir do serviço Render antes de liberar tráfego. O usuário de migrations precisa de DDL; recomenda-se credencial distinta com privilégios reduzidos para o runtime após implantação. Não use nomes nem credenciais de banco dos produtos.

### PostgreSQL / MontuDB

Use o endpoint PostgreSQL real do provedor e o CA/SSL exigido por ele. O projeto usa `psycopg` 3. A compatibilidade de rede, extensões, pooler e políticas do serviço denominado MontuDB precisa ser verificada no ambiente contratado; não foi presumida nem homologada aqui.

## Render

`render.yaml` define web e worker separados. Publique somente a pasta do projeto; se usar um monorepo, configure a raiz do serviço para essa pasta. O Blueprint requer preencher o grupo `livesun-central-secrets` com os segredos antes da sincronização/deploy. Valores não ficam no Git.

- Build: `pip install -r requirements.lock.txt`.
- Pré-deploy web: `flask --app wsgi db upgrade && flask --app wsgi seed`.
- Web: Gunicorn conforme `render.yaml`, com access log desabilitado para evitar IDs/IPs em logs.
- Worker: `flask --app wsgi worker`; deve compartilhar banco, chave Fernet e HMAC com o web.
- Health check: `/api/v1/health`.
- Redis compartilhado: configure `RATELIMIT_STORAGE_URI`; nenhum segredo padrão é gerado automaticamente.
- Execute `create-admin` em shell administrativo privado após migration.
- Rode inicialmente migrations antes de iniciar o worker; no primeiro deploy ele pode reiniciar até a criação do esquema.
- Reconciliação: configure um agendador executando `flask --app wsgi reconcile --repair` a cada intervalo desejado. Também é possível executar manualmente.

`preDeployCommand` requer recurso pago compatível. Documentação oficial de referência: `https://render.com/docs/blueprint-spec` e `https://render.com/docs/deploys`. Variáveis secretas do grupo são preenchidas pelo Dashboard; `sync:false` não é usado dentro de envVarGroups porque não é suportado nesse contexto.

O worker entrega eventos assim que disponíveis (polling de 1 segundo quando ocioso), reexecuta tentativas com backoff e roda manutenção de vencimentos a cada minuto. Não usa thread daemon dentro do processo web. Um crash após o envio pode gerar repetição: receptores devem ser idempotentes.

## Operação do painel

1. Execute o seed: somente produto `PROPOSTAS` e plano único, valor inicial zero e limites não definidos.
2. Configure valor e limites do plano em Planos. `limite_personalizado_json` aceita `{"propostas_mes": 100}`; `limite_usuarios` aceita `3`.
3. Configure o segredo/destino em Webhooks ou via variável e seed. Com destino configurado, eventos são enfileirados mesmo sem segredo, mas as tentativas falham até cadastrar a credencial; reenvie falhas após configuração. Sem destino, o evento permanece auditado, sem entrega. **Não ative a integração sem validar o envio.**
4. Cadastre cliente e crie assinatura. Copie o ID do cliente para o vínculo do Propostas.
5. Planos/módulos de novos produtos são configurados pelos mesmos formulários, sem código específico.
6. Alterar limites do plano notifica assinaturas vigentes; mudar composição de módulos do plano afeta próximas contratações/trocas, não assinaturas já provisionadas.
7. Cobranças são lançadas e pagas manualmente; não há gateway de pagamento integrado nem política automática de suspensão por atraso. O financeiro pode suspender com justificativa.

### Perfis

- `superadmin`: todas as operações.
- `comercial`: cadastros comerciais, assinaturas, status, planos, módulos e limites; sem gerenciar credenciais/operadores.
- `financeiro`: consultas, cobranças e pagamentos; pode suspender, não reativar/excluir.
- `suporte`: consultas, suspensão/bloqueio com motivo e reenvio de webhooks.
- `auditor`: somente leitura.

Autorização é aplicada no servidor. Sessões do painel nunca autenticam endpoints `/api/v1`. Credenciais JWT possuem scopes `read`, `write`, `webhooks`; emita `read` para o Propostas:

```powershell
flask --app wsgi service-token PROPOSTAS --hours 720 --scope read
```

O comando imprime o token apenas para cadastro seguro, não o persiste em logs. `--rotate` invalida todos os tokens anteriores do produto. Planeje renovação antes da expiração; não armazene JWT em documentos, histórico de chat ou repositório.

## Integração no Propostas

Arquivos adicionados no projeto independente `D:\App_LiveSun\LiveSun_Propostas`:

- `src/models/central.py`: vínculo empresa → cliente Central, cache persistente e eventos recebidos.
- `src/services/central_client.py`: cliente HTTPS, validação, cache e decorator `require_active_subscription`.
- `src/routes/central.py`: webhook, consulta assinada de estado e comando de vínculo.
- `migrations/versions/c20261112_central_integracao.py` e `tests/test_central.py`.
- `deploy/.env.central.example` e `deploy/INTEGRACAO_CENTRAL.md`.

Aplicar migration, criar vínculos e configurar variáveis antes de `CENTRAL_ENABLED=true`. Integração fica desativada por padrão para não bloquear silenciosamente instalações sem cadastro comercial. **A proteção comercial só existe quando habilitada.** Login valida após senha correta e antes de `login_user`; um guard valida todas as requisições autenticadas, exceto estáticos, logout e endpoints assinados. Permissões internas permanecem intactas.

Cache é persistido no banco **do próprio Propostas** pelo próprio produto, nunca acessado diretamente pelo Central. Versões `(assinatura_id, versao)` impedem aplicar webhooks antigos. Nova assinatura tem ID crescente. Webhooks completos substituem o cache atomicamente, sem chamada de rede no receptor. Eventos atrasados com validade vencida forçam refresh na próxima requisição.

As operações protegidas são sensíveis e falham fechadas após expirar o cache. O opt-in `CENTRAL_ALLOW_FAIL_OPEN_NON_SENSITIVE` só funciona em chamadas explicitamente marcadas `sensitive=False`; nenhuma rota comercial é marcada assim nesta versão. Último estado bloqueado nunca ganha acesso por contingência.

## Testes

```powershell
python -m pytest -q
```

Para bancos reais **descartáveis e exclusivos**, nunca produção:

```powershell
$env:TEST_DATABASE_URL='mysql+pymysql://user:pass@localhost:3306/central_test'
python -m pytest tests/test_central.py -q
$env:TEST_DATABASE_URL='postgresql+psycopg://user:pass@localhost:5432/central_test'
python -m pytest tests/test_central.py -q
Remove-Item Env:TEST_DATABASE_URL
```

Esses fixtures criam e removem tabelas do banco de teste. As migrations de produção não permitem downgrade destrutivo. Os testes de migration também verificam ausência de drift com `flask db check` e compilação SQL dos dois dialetos. Testes não comprovam concorrência de banco real ou conectividade externa.

No Propostas:

```powershell
Set-Location 'D:\App_LiveSun\LiveSun_Propostas'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_central.py
```

Referências de contrato e homologação: `docs/API.md`, `docs/ACEITE.md`, `docs/LIMITACOES.md`.