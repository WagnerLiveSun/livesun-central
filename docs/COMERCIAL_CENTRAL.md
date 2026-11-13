# Central e Comercial — operação e virada controlada

**Atualização:** o processo de migração/importação descrito historicamente abaixo foi retirado. O fluxo vigente está em `AJUSTE_COBRANCA_PAINEL.md`: configuração de cobrança por produto, ações por assinatura e preservação das bonificações locais, sem arquivos de importação.

## Separação obrigatória

O Central controla somente a assinatura paga à LiveSun pelos produtos. Não recebe credenciais de conta bancária dos clientes. `asaas_boleto.py`, `inter_bolepix.py`, seus clientes/rotas e `cobrancas_bancarias.py` do Comercial permanecem inalterados. O serviço de assinatura legado é desativado quando a integração do Central é ativada, sem desativar os serviços operacionais.

## O que mudou no painel Central

- Ações de status por botões e confirmação, motivos por seleção, limites numéricos e diagnóstico técnico recolhido.
- Produtos nos formulários por seleção e códigos gerados se vazios. Propostas continua plano único e sem módulos.
- Área **Integrações e chaves**: gerar credencial de consulta, revogar, renovar HMAC, configurar Asaas sandbox/produção e testar conexão sem criar cobrança.
- Credencial persistente com hash no banco e revogação; segredo exibido uma vez, sem depender de JWT renovado a cada mês. JWT anterior continua compatível.
- Área **Migrar assinaturas**: prévia e importação do export de assinatura do Comercial. Não cria cliente/recorrência no Asaas durante importação.
- Trial e cortesia administrados no Central; cobranças/recebimentos e purgas por worker.

## Instalação local

A migration Central `20261112_02` é aditiva e foi aplicada ao banco local `central`, sem drift. Reinicie web e worker pelo `.bat`. O seed registra o produto COMERCIAL sem inventar preços/planos: esses são importados das ofertas ou cadastrados pelo painel.

No Comercial, aplique `D:\App_LiveSun\LiveSun_Comercial_X\migrations\mysql\038_central_assinaturas.sql` ou a versão PostgreSQL correspondente antes de publicar a nova versão. Não misture dialetos. As tabelas guardam configuração criptografada, vínculo empresa/cliente, cache e recibos de eventos/purga. Para PostgreSQL com RLS, o owner precisa validar/grantar acesso às novas tabelas para o runtime; comandos assinados usam escopo de tenant verificado, não cabeçalhos de usuário.

## Migração pelo navegador (sem CMD na nuvem)

1. Acesse o backoffice do Comercial com operador autorizado. Entre em `/backoffice/comercial/central/`.
2. Clique **Exportar assinaturas**. O arquivo contém dados comerciais sensíveis, não credenciais bancárias. Armazene temporariamente com acesso restrito e descarte após a conferência.
3. No Central, use **Migrar assinaturas** para visualizar o arquivo. Confira preços, status, ciclo, trial, bônus e IDs de assinatura/cliente Asaas. Empresas sem oferta com preço exigem revisão; não se presume preço.
4. Confirme a importação e escolha o ambiente de origem real (sandbox não compartilha IDs com produção). A importação é idempotente por assinatura legada. Não une clientes automaticamente por CNPJ; confira vínculos para clientes que já contratam outro produto.
5. Configure URL de produção e webhook do produto COMERCIAL no Central; localmente, use porta diferente do Propostas. Se Comercial usa 5000 e Propostas também, não podem rodar simultaneamente nessa porta. Ex.: Comercial 5002, Propostas 5000 e Central 5001.
6. Gere credencial **read** e HMAC em Integrações; no backoffice do Comercial, preencha endereço do Central, token e HMAC. Deixe desativado enquanto confere os vínculos.
7. Vincule cada empresa ao ID correto do cliente no Central. Teste conexão por botão.
8. Configure a conta Asaas de **assinaturas LiveSun** no Central, inicialmente sandbox. Token de webhook é independente do HMAC dos produtos.
9. Para a virada, pause ações legadas de assinatura, importe/concilie novamente o necessário, ative o Central no Comercial com confirmação CENTRAL e só então habilite cada vínculo existente no Asaas pelo Central. Informe ID existente, nunca gere uma recorrência nova para contrato já cobrado.
10. Mude o destino de webhook de assinatura no painel Asaas para o Central. Não mude os webhooks operacionais Asaas/Inter dos clientes. Após ativação, `/webhooks/asaas` legado responde 410, enquanto `/asaas-boletos/webhook` e Inter permanecem intactos.

**Não foi feita virada automática nem chamadas reais ao Asaas.** Credenciais reais devem ser configuradas conscientemente pelo operador. Asaas exige callback público acessível; HTTP local sem túnel não recebe eventos vindos do gateway.

## Asaas

Endpoints do Central: `/api/v1/webhooks/asaas/sandbox` e `/api/v1/webhooks/asaas/producao`. Autenticação pelo header `asaas-access-token` configurado, idempotência por ambiente/evento. Nunca aplica webhook usando somente customer ID: o cliente pode contratar vários produtos. O worker consulta o payment atual no gateway antes de aplicar, evitando regressão por evento antigo.

Operações externas ocorrem em fila. Resposta perdida após POST fica em REVISAR, não recria automaticamente assinatura; operador confere gateway e autoriza repetir. Planos mensais/anuais são suportados. Boleto e Pix suportados; cartão requer um fluxo de tokenização seguro adicional, não captura dados de cartão neste painel. Atualização de plano não muda cobranças já emitidas nem calcula prorrata automaticamente. Suspensão/inativação de recorrência impede futuras cobranças, sem cancelar dívidas existentes silenciosamente. Estorno/chargeback exige conferência e política de inadimplência.

## Retenção e purga por produto

Excluir bloqueia acesso e agenda purga 60 dias depois. Superadmin pode autorizar antecipação com PURGAR e justificativa. Worker chama `/central/purgar` do produto com HMAC, timestamp, ID único e escopo cliente/produto/assinatura. Recibo do produto persiste atomicamente com a exclusão do banco; retries não repetem a operação.

O Comercial apaga apenas linhas do tenant alvo em tabelas que possuem `empresa_id`, em ordem de dependências, sem desabilitar FKs; referências incompatíveis fazem a purga falhar e exigir revisão em vez de arriscar outros tenants. Nova assinatura vigente para o mesmo produto impede purga antiga. Assinaturas de outros produtos não são alteradas. O Central preserva metadados comerciais/auditoria e recibo de conclusão; não apaga globalmente o cliente nem documentos financeiros.

**Limitação explícita:** limpeza de arquivos externos/anexos e remoção de registros sem `empresa_id` requer inventário específico antes de habilitar purga em produção. Não há varredura cega de diretórios. O Propostas ainda precisa implementar o receptor de purga; até lá sua purga fica com falha visível, sem apagar dados por acesso direto ao banco.

Por segurança, o receptor de purga do Comercial inicia desabilitado. Após ensaio em cópia descartável, marque a opção de purga na tela de integração e confirme `PURGA HOMOLOGADA`. Enquanto desabilitado, pedidos ficam com falha visível no Central, nunca são executados silenciosamente.

GET do backoffice não dispara mais purga. Importação de exclusões legadas não agenda limpeza automaticamente: revisar datas e autorizar explicitamente.

## Bootstrap de nuvem

Operações rotineiras são feitas pelo navegador. Chaves-mestras de criptografia e banco ainda precisam ser configuradas uma vez no provedor. Para criar o primeiro superadmin sem shell, configure `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` e opcionalmente `BOOTSTRAP_ADMIN_NAME` no provedor; o `seed` do pré-deploy cria a conta somente se não houver superadmin ativo. Remova a variável de senha após o primeiro acesso. Não substitui senha de conta existente nem oferece instalador público. Não há execução arbitrária de shell por botão.

## Aceite antes de produção

- Homologar Asaas sandbox real, webhook HTTPS e links de pagamento.
- Conferir importação com preços/IDs reais sem duplicar recorrências.
- Validar PostgreSQL/RLS, migração SQL e perfis.
- Ensaiar purga com cópia descartável do banco completo e arquivos; nunca testar primeiro no tenant real.
- Testar pagamentos operacionais Asaas/Inter e confirmar que credenciais/rotas permanecem separadas.
- Testar suspensão e reativação com sessões abertas e falha de comunicação.