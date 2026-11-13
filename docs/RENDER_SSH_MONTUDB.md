# Render com MontuDB por SSH

## Configuração no Dashboard

1. Serviço `srv-dbrhj7mc6qcc73dufc9g`: Git `WagnerLiveSun/livesun-central`, branch `publicacao-render`, raiz vazia.
2. Em Settings → Build/Source, selecione runtime **Docker** e Dockerfile `./Dockerfile`. Não use os comandos antigos de runtime Python.
3. Plano **Free**: deixe **Pre-deploy Command vazio**. O modo `web` executa migrations/seed após confirmar o túnel e antes de iniciar Gunicorn. Não execute migrations no build.
4. Docker Command: `python scripts/with_ssh_tunnel.py web-worker`.
5. Health: `/api/v1/health`. Mantenha deploy manual durante homologação.
6. Mantenha o Secret File **SKey** em `/etc/secrets/SKey`. Não cole a chave em Environment, Git, logs ou chat. O Docker não inclui esse arquivo; o Render deve montá-lo em runtime.
7. O manifesto cria somente um serviço web Free, sem serviço pago adicional. O modo `web-worker` inicia Gunicorn e um processo Flask worker após migrations/seed; ambos usam o mesmo túnel e Environment. Se Docker Command estiver sobrescrito manualmente no Dashboard, atualize-o para `web-worker`; mudar somente o Dockerfile não substitui esse campo. O modo `web` continua disponível para API isolada; `worker` para serviço separado. Não execute outro worker sem necessidade.

### Limitações do Free

- O serviço suspende após 15 minutos sem tráfego de entrada; SSH/banco não substituem tráfego de entrada. Não há garantia de operação contínua.
- API e worker funcionam enquanto a instância estiver ativa, compartilhando CPU/memória. Ao suspender, ambos param. Ao iniciar novamente, o worker consulta filas persistidas no PostgreSQL e usa os mecanismos existentes de recuperação/lease; não há garantia de execução contínua ou horário exato.
- A preparação roda em cada inicialização do web, inclusive após suspensão, uma vez por supervisor (não por worker Gunicorn nem reconexão SSH). Se falhar, a API não inicia. Reserve tempo de inicialização para túnel e migrations; não execute instâncias concorrentes migrando o mesmo banco.
- O plano Free não garante operação contínua de produção. Ao ativar `web-worker`, o worker existente processará tarefas elegíveis já persistidas: webhooks, cadastros, manutenção de cobranças/Asaas e purgas previamente agendadas. Não são criadas novas autorizações comerciais, nem alteradas regras de bônus/purga por produto. Confira filas e credenciais antes do deploy; testes usam mocks e não executam cobranças/purgas reais.

## Environment

Modelo sem credenciais: `deploy/render.ssh.environment.example`. Arquivo privado de preenchimento local: `.env.render` (não versionado).

```dotenv
SSH_ENABLED=true
SSH_HOST=wagner.montudb.com
SSH_USER=opc
SSH_PORT=22
SSH_REMOTE_PORT=55433
SSH_LOCAL_PORT=55433
SSH_KEY_PATH=/etc/secrets/SKey
SSH_KNOWN_HOSTS_PATH=/app/deploy/montudb_known_hosts
SSH_STARTUP_TIMEOUT_SECONDS=90
DB_ENGINE=postgresql
DATABASE_URL=postgresql+psycopg://postgres:SENHA_DO_BANCO@127.0.0.1:55433/DbCentral?sslmode=disable&connect_timeout=5
```

O PostgreSQL MontuDB foi consultado pelo túnel local e informou `ssl=off`. O tráfego até a VM é protegido pelo **SSH**; o PostgreSQL é alcançado por loopback na VM. Não use esta URL sem o supervisor do túnel. Não exponha a porta 55433 publicamente. O usuário postgres é o acesso administrativo fornecido: recomenda-se criar posteriormente usuário de runtime com privilégios mínimos.

Complete também SECRET_KEY, JWT_SECRET e ENCRYPTION_KEY. As chaves existentes do banco que contém credenciais criptografadas precisam ser preservadas; esta publicação não recriptografa nem transfere dados. As chaves novas geradas em `.env.render` são apropriadas para instalação ainda sem dados criptografados prévios.

### Rate limit sem Redis

Redis não é obrigatório no cenário atual de instância única. Remova `RATELIMIT_STORAGE_URI` do Environment se contiver placeholder. Sem essa variável (ou vazia), o Central usa memória local, mantendo login 5/minuto e API 120/minuto por IP. O supervisor inicia Gunicorn com **1 processo e 4 threads**; não aumente processos/instâncias sem configurar armazenamento compartilhado. Não há nova variável obrigatória nem serviço adicional.

Limitação aceita no Free: contadores zeram em reinícios, suspensão/retomada ou reciclagem do processo e não são compartilhados com outra instância (inclusive sobreposição de deploys). A documentação Flask-Limiter recomenda armazenamento persistente/compartilhado em produção. Redis continua opcional por `RATELIMIT_STORAGE_URI` para futura expansão; não foi desativada a proteção de login/API. Ver `https://flask-limiter.readthedocs.io/en/stable/configuration.html`.

No primeiro acesso, se não houver operador, use BOOTSTRAP_ADMIN_EMAIL/NAME/PASSWORD no Environment e remova a senha após a criação pelo seed. Não há senha padrão.

## Segurança SSH

O arquivo versionado `deploy/montudb_known_hosts` contém apenas a **chave pública ed25519 do servidor**, copiada da entrada já confiada no known_hosts da estação. Fingerprint deve ser conferida com o administrador; ela não é a chave privada SKey. Não usamos ssh-keyscan em runtime, aceitação automática nem StrictHostKeyChecking=no. Rotação de chave do servidor exige atualizar a chave pública após confirmar a nova identidade.

SKey deve ser chave privada OpenSSH/PEM utilizável não interativamente, cuja pública esteja autorizada na conta opc. Se a chave exigir passphrase, este supervisor não pede senha nem ativa agente; configure uma chave dedicada de serviço conforme política de segurança. Chave pública isolada, PPK ou conteúdo incompleto não abre túnel.

A chave montada pode ser somente leitura/permissões amplas: o supervisor a copia para diretório temporário privado e arquivo 0600 e remove ao encerrar. Não registra o conteúdo, stderr SSH ou credenciais do banco. O host é fixado, a conexão não usa senha SSH e o encaminhamento escuta somente em 127.0.0.1.

## Operação

- API só inicia após túnel SSH, `SELECT 1` e migrations/seed concluídos com sucesso.
- Queda de SSH tenta reconectar com backoff; conexões SQLAlchemy usam pool_pre_ping. Se não recuperar dentro do prazo, o supervisor encerra a aplicação com erro para a plataforma detectar; não libera acesso por falha de assinatura.
- SIGTERM/SIGINT encerra web, worker e SSH. Se o worker sair (mesmo código zero), o supervisor encerra o conjunto com erro; se a API sair, encerra worker/túnel. O worker não é iniciado dentro de cada processo Gunicorn nem duplicado em reconexões SSH.
- A preparação na inicialização executa migrations/seed sem recriar banco. Recusa banco sem Alembic ou com tabelas externas. Migrations devem ser revisadas antes de publicar.
- Falha de POST comercial em andamento continua sujeita aos mecanismos de fila/idempotência; túnel não garante ausência de falhas de rede.
- Logs esperados: `ssh_tunnel_and_database_ready`, `database_preparation_started`, `database_preparation_completed`, `application_started`, `worker_started` e, em queda, `ssh_tunnel_disconnected` ou `worker_exited`.
- A preparação registra `preparation_stage_started` e, em falha, `preparation_stage_failed` com `stage` e orientação fixa, sem valores de Environment nem texto de exceções. Estágios distinguem chaves ausentes, configuração de produção/Redis, chave Fernet, criação da aplicação, schema, migrations, seeds e bootstrap do administrador.
- Uma falha de preparação não significa falha SSH: `ssh_tunnel_and_database_ready` confirma que SSH e SELECT 1 funcionaram naquela tentativa. Se surgir porta ocupada, não mate processos desconhecidos nem desative a verificação. O teste de porta em Linux permite TIME_WAIT, mas continua recusando listeners ativos; o encerramento tenta parar SSH mesmo se parar o filho falhar.

Se timeout: conferir SKey no serviço certo, autorização de chave opc, firewall SSH 22 para saída do Render (incluindo worker), fingerprint e serviço MontuDB2 na porta 55433. Não apagar tabelas para corrigir conectividade.

## Situação de validação

OpenSSH/servidor PostgreSQL locais disponíveis para diagnóstico. Ambiente Docker/Render não foi executado nesta estação porque Docker e administração Render não estão disponíveis. Não foi lida a chave privada nem aberto túnel SSH nesta implementação. Testes de configuração/supervisão usam processos simulados e cópias temporárias fictícias. A validação real exige deploy e conferência dos logs no Render.

Referências oficiais consultadas: `https://render.com/docs/native-runtimes`, `https://render.com/docs/configure-environment-variables`, `https://render.com/docs/deploys`.