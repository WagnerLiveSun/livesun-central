# Empresas do Propostas: cadastro e vínculo pelo painel

Menu **Empresas do Propostas** (superadmin/comercial/suporte/auditor) lista empresas em páginas de 50 via endpoint assinado do produto, mostrando documento, e-mail e vínculo conhecido em cada sistema.

Somente superadmin/comercial pode acionar **Cadastrar cliente e vincular** (POST com CSRF). A primeira ação busca novamente os dados no produto e prepara solicitação pendente. Não cria assinatura, cliente ou cobrança nessa etapa. Na confirmação, o operador escolhe cliente existente com mesmo documento ou criação de cliente, plano ativo PROPOSTAS, status ATIVA/TRIAL e justificativa. Reaproveita o fluxo de cadastros recebidos e as proteções contra duplicação.

Após confirmar, a solicitação fica VINCULO_PENDENTE. O worker entrega os IDs e entitlements ao Propostas e só marca VINCULADA quando o produto confirma o evento. Falhas podem ser reenviadas na própria tela, sem duplicar cadastro/assinatura. Não habilita cobrança Asaas, não importa usuários/senhas, propostas ou dados operacionais; não modifica Comercial.

## Preparação da produção

1. Aplicar os arquivos e migration de integração no Propostas após backup. Guia no projeto: `D:\App_LiveSun\LiveSun_Propostas\deploy\INTEGRACAO_CENTRAL.md`.
2. Configurar o mesmo segredo HMAC no produto do Central e `CENTRAL_WEBHOOK_SECRET` do Propostas. Não colocar segredos em Git. Propostas pode continuar com CENTRAL_ENABLED=false durante o vínculo: somente endpoints assinados de preparação aceitam chamadas nessa fase.
3. No Central, `url_producao` precisa apontar à raiz HTTPS do Propostas e o host estar permitido. Sem integração publicada/configurada, a página informa indisponibilidade, sem criar dados. Não coleta em background nem lê banco remoto diretamente.
4. Usar Central com worker ativo (`web-worker` no Render Free). Sem worker, o cadastro aprovado permanece pendente de confirmação.
5. Conferir vínculos/assinaturas antes de ligar o controle de acesso comercial do Propostas. Apenas listar empresas não autoriza ativar guard: empresas não vinculadas serão bloqueadas quando CENTRAL_ENABLED=true.

O bootstrap de vínculo usa HMAC, timestamp e confirmação de produto/documento; GET não tem efeitos persistidos. Assinaturas GET incluem query string da paginação, além do path. POST não aceita substituição silenciosa de empresa/cliente existente. Toda exibição passa pelo escaping Jinja e perfis de leitura não podem cadastrar.

Ainda é necessário homologar ponta a ponta em produção. Testes locais usam bancos descartáveis e HTTP simulado, sem chamadas de cobrança ou alteração dos bancos dos produtos publicados.