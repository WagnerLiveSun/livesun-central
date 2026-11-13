# Autocadastro Comercial → pendência no Central

## Fluxo

1. O cliente cadastra empresa e usuário no Comercial.
2. A mesma transação grava uma solicitação em `central_cadastros_pendentes`, sem senha, hash, permissões ou dados bancários. Não cria assinatura/trial local para esse cadastro novo integrado.
3. Após confirmar a transação, o Comercial tenta informar o Central por `POST /api/v1/cadastros`. Falha de rede não perde nem desfaz o cadastro: a solicitação permanece local para reenvio.
4. O Central mostra **Cadastros recebidos → Precisa ser habilitado/vinculado**, também contabilizado no dashboard. Receber não cria cliente, assinatura ou cobrança automaticamente.
5. O operador abre **Habilitar / vincular**, seleciona cliente existente com mesmo documento ou cria um cliente, escolhe plano do produto e confirma acesso inicial ATIVA/TRIAL. Não inicia recorrência financeira.
6. A solicitação fica **Vínculo aguardando confirmação**. O worker do Central devolve o vínculo ao Comercial por callback HMAC autenticado.
7. O Comercial grava cliente/assinatura/cache e recibo atomicamente; o Central marca **Habilitado e vinculado** somente após confirmação. Duplicatas não criam empresas, vínculos ou assinaturas repetidas.

Antes da habilitação/vínculo, novos autocadastros ficam bloqueados com mensagem de aguardar a LiveSun. Bonificações concedidas anteriormente permanecem com a condição e prazo originais; o callback recusa substituí-las por autorização não bonificada.

## Configuração

- Central: produto COMERCIAL ativo, plano ativo, URL do produto, URL de webhook e HMAC cadastrados.
- Comercial: configuração em `/backoffice/comercial/central/` com URL do Central, token de consulta do produto e mesmo HMAC. Tokens existentes com scope `read` podem encaminhar solicitação, mas não podem habilitar assinaturas; essa decisão exige operador do painel.
- Mantenha o worker do Central em execução. A cada ciclo de manutenção (aproximadamente 60 segundos), ele consulta também a fila pendente no Comercial por GET assinado `/central/cadastros-pendentes`. Assim há recuperação mesmo sem outra visita ao produto ou processo adicional na nuvem.
- Falha em devolver vínculo tem retry com backoff e botão de tentar novamente no Central. No backoffice do Comercial há botão de reenviar cadastro.
- Portas locais devem ser diferentes e HTTP loopback explicitamente autorizado no Central. Callback de produção exige HTTPS e host autorizado. Não é necessário CMD para operar o fluxo normal.

## Banco

- Central: migration `20261112_04`, aplicada ao MySQL local e verificada sem drift.
- Comercial: `migrations/mysql/039_central_autocadastro.sql` ou versão PostgreSQL; DDL somente aditivo. Aplique antes de publicar o novo código.
- SQL do Central: banco na revisão 03 usa `deploy/sql/<dialeto>/05_atualizar_20261112_03_para_head.sql`; revisões anteriores possuem incrementais correspondentes. Não reaplique estrutura inicial.
- Em PostgreSQL, owner deve validar grants e política RLS das tabelas novas para processos de integração. Não houve homologação contra PostgreSQL real.

## Contratos

- `POST /api/v1/cadastros`: Bearer de produto; payload com evento `cad_<uuidhex>`, empresa de origem, razão social, nome fantasia, CPF/CNPJ, e-mail, telefone e responsável. Campos extras são recusados. Identidade do produto vem da credencial, nunca de parâmetro livre.
- Idempotência: produto + empresa de origem e evento original. Outro evento para mesma empresa exige revisão; não sobrescreve cadastro aprovado.
- `POST /central/cadastros/vincular`: HMAC/timestamp, header `X-LiveSun-Event: CADASTRO_HABILITADO`; inclui referência original e snapshot de entitlements.
- `GET /central/cadastros-pendentes?apos=<id>`: HMAC sobre timestamp + ponto + path; paginação de 50 registros. Não retorna senhas ou credenciais.

Sem importação de contratos, sem leitura cruzada dos bancos e sem alteração das rotinas bancárias Asaas/Inter.