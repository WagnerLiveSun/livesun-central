# Publicação do LiveSun Central

## Destino autorizado

- Git: `https://github.com/WagnerLiveSun/livesun-central.git`
- Serviço web existente: `srv-dbrhj7mc6qcc73dufc9g`
- URL: `https://livesun-central.onrender.com`

## Situação da preparação

Código enviado à branch `publicacao-render`, sem alterar `main`. O serviço existente não foi administrado nem teve seu Environment alterado por esta sessão: não há credencial de administração Render disponível. Escolha conscientemente essa branch no serviço somente após completar banco remoto, Redis e segredos. O teste público de health não confirmou aplicação saudável nesta preparação.

101 testes locais passaram. `.env`, `.env.postgresql` e `.env.render` foram conferidos como ignorados; a preparação para Git verificou padrões de credenciais sem encontrar arquivos bloqueados. Isso não substitui revisão de segurança antes da ativação em produção.

Publique somente a pasta `livesun-central` como raiz do repositório. Não publique a pasta superior: ela contém backups e outros arquivos locais. Não publique `.env`, `.env.postgresql`, `.env.render`, certificados ou dumps.

## Pré-requisitos

1. PostgreSQL exclusivo acessível pelo Render, com TLS. `127.0.0.1:55433` aponta para a própria instância Render, não o computador local, e não serve como endereço do banco remoto.
2. Redis compartilhado para rate limit, configurado em `RATELIMIT_STORAGE_URI`. Web e worker devem receber as mesmas chaves da aplicação e URL de banco.
3. Permissão Git para publicar e acesso administrativo ao serviço Render para salvar Environment/deploy. O ID do serviço e os ranges de saída não são credenciais de API.
4. Receptores dos produtos publicados devem conter o contrato atual de integração. Publicar somente Central não atualiza Propostas ou Comercial automaticamente.

## Environment

Modelo sem segredos: `deploy/render.environment.example`.

Arquivo privado local: `.env.render`, ignorado pelo Git, contendo chaves novas para uma instalação vazia. Complete `DATABASE_URL` e `RATELIMIT_STORAGE_URI` antes de colar em Render → Environment → Add from .env. Não envie esse arquivo por chat. Para copiar dados criptografados existentes, preserve a chave de criptografia de origem ou faça recriptografia; chaves novas são para base nova.

O primeiro operador pode ser criado no pré-deploy por `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` e opcionalmente `BOOTSTRAP_ADMIN_NAME`. Remova a variável de senha depois do primeiro acesso. Não existe senha padrão.

## Serviço web

- Root Directory: vazio, quando o conteúdo de livesun-central é a raiz do Git.
- Build: `pip install -r requirements.lock.txt`
- Pre-deploy: `flask --app wsgi db upgrade && flask --app wsgi seed`
- Start: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --access-logfile /dev/null wsgi:app`
- Health Check: `/api/v1/health`
- Deploy automático: desativado durante homologação.

O manifesto é um modelo; não sincronize cegamente para substituir o serviço existente ou criar recursos cobrados sem conferir o painel. A configuração de pré-deploy exige recurso compatível no plano contratado.

## Worker

Crie/configure um Background Worker com o mesmo Git, build e Environment. Start: `flask --app wsgi worker`. Primeiro aplique migrations pelo serviço web. Sem worker, o painel/API podem responder, mas a fila de webhooks, manutenção e retornos de vínculos não operam normalmente.

## Rede

Os ranges informados `74.220.48.0/24` e `74.220.56.0/24` são para conferir na lista de saída do serviço e liberar no firewall do banco externo, quando aplicável. Confirme também os ranges do worker/região. Não atribua esses ranges a POSTGRES_HOST: eles não são o endereço do banco nem IP fixo exclusivo do aplicativo.

## Produtos

Após homologar o Central, configure nos produtos `CENTRAL_BASE_URL=https://livesun-central.onrender.com` e credenciais próprias por produto. Exija HTTPS; desabilite HTTP local. Cadastre no Central os receptores:

- Propostas: `https://propostas.livesun.com.br/webhooks/assinatura`
- Comercial: `https://app.livesun.com.br/webhooks/assinatura`

Não aponte clientes reais antes de conferir cadastro/assinatura/vínculos no banco remoto. Não replique URLs localhost. Habilite cobrança e purga somente após testes específicos em homologação.

## Referências oficiais

- `https://render.com/docs/configure-environment-variables`
- `https://render.com/docs/deploys`
- `https://render.com/docs/blueprint-spec`
- `https://render.com/docs/outbound-ip-addresses`