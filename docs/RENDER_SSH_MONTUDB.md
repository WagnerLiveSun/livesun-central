# Render com MontuDB por SSH

## Configuração no Dashboard

1. Serviço `srv-dbrhj7mc6qcc73dufc9g`: Git `WagnerLiveSun/livesun-central`, branch `publicacao-render`, raiz vazia.
2. Em Settings → Build/Source, selecione runtime **Docker** e Dockerfile `./Dockerfile`. Não use os comandos antigos de runtime Python.
3. Pre-deploy: `python scripts/with_ssh_tunnel.py prepare`.
4. Docker Command: `python scripts/with_ssh_tunnel.py web`.
5. Health: `/api/v1/health`. Mantenha deploy manual durante homologação.
6. Mantenha o Secret File **SKey** em `/etc/secrets/SKey`. Não cole a chave em Environment, Git, logs ou chat. O Docker não inclui esse arquivo; o Render deve montá-lo em runtime e pré-deploy.
7. No worker, use o mesmo runtime, Git, Environment e Secret File SKey, mas Docker Command `python scripts/with_ssh_tunnel.py worker`. O túnel do web não é compartilhado com worker/pré-deploy: cada processo abre o próprio.

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

Complete também SECRET_KEY, JWT_SECRET, ENCRYPTION_KEY e RATELIMIT_STORAGE_URI (Redis acessível no Render). As chaves existentes do banco que contém credenciais criptografadas precisam ser preservadas; esta publicação não recriptografa nem transfere dados. As chaves novas geradas em `.env.render` são apropriadas para instalação ainda sem dados criptografados prévios.

No primeiro acesso, se não houver operador, use BOOTSTRAP_ADMIN_EMAIL/NAME/PASSWORD no Environment e remova a senha após a criação pelo seed. Não há senha padrão.

## Segurança SSH

O arquivo versionado `deploy/montudb_known_hosts` contém apenas a **chave pública ed25519 do servidor**, copiada da entrada já confiada no known_hosts da estação. Fingerprint deve ser conferida com o administrador; ela não é a chave privada SKey. Não usamos ssh-keyscan em runtime, aceitação automática nem StrictHostKeyChecking=no. Rotação de chave do servidor exige atualizar a chave pública após confirmar a nova identidade.

SKey deve ser chave privada OpenSSH/PEM utilizável não interativamente, cuja pública esteja autorizada na conta opc. Se a chave exigir passphrase, este supervisor não pede senha nem ativa agente; configure uma chave dedicada de serviço conforme política de segurança. Chave pública isolada, PPK ou conteúdo incompleto não abre túnel.

A chave montada pode ser somente leitura/permissões amplas: o supervisor a copia para diretório temporário privado e arquivo 0600 e remove ao encerrar. Não registra o conteúdo, stderr SSH ou credenciais do banco. O host é fixado, a conexão não usa senha SSH e o encaminhamento escuta somente em 127.0.0.1.

## Operação

- Aplicação só inicia após túnel SSH e `SELECT 1` no banco confirmados.
- Queda de SSH tenta reconectar com backoff; conexões SQLAlchemy usam pool_pre_ping. Se não recuperar dentro do prazo, o supervisor encerra a aplicação com erro para a plataforma detectar; não libera acesso por falha de assinatura.
- SIGTERM/SIGINT encerra aplicação, workers filhos e SSH.
- Pré-deploy executa migrations/seed sem apagar tabelas ou recriar banco. Recusa banco sem Alembic ou com tabelas externas.
- Falha de POST comercial em andamento continua sujeita aos mecanismos de fila/idempotência; túnel não garante ausência de falhas de rede.
- Logs esperados: `ssh_tunnel_and_database_ready`, `application_started` e, em queda, `ssh_tunnel_disconnected`.

Se timeout: conferir SKey no serviço certo, autorização de chave opc, firewall SSH 22 para saída do Render (incluindo worker), fingerprint e serviço MontuDB2 na porta 55433. Não apagar tabelas para corrigir conectividade.

## Situação de validação

OpenSSH/servidor PostgreSQL locais disponíveis para diagnóstico. Ambiente Docker/Render não foi executado nesta estação porque Docker e administração Render não estão disponíveis. Não foi lida a chave privada nem aberto túnel SSH nesta implementação. Testes de configuração/supervisão usam processos simulados e cópias temporárias fictícias. A validação real exige deploy e conferência dos logs no Render.

Referências oficiais consultadas: `https://render.com/docs/native-runtimes`, `https://render.com/docs/configure-environment-variables`, `https://render.com/docs/deploys`.