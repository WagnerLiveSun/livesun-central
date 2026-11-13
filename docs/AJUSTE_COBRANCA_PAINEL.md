# Cobrança relacionada e painel operacional

Esta revisão substitui o fluxo anterior de importação/migração. Não há tela de migração nem necessidade de exportar contratos: a base informada possui bonificações, que são preservadas sem cobrança.

## Operação

1. **Produtos → Cobrança e planos**: configurar conta/ambiente Asaas e testar conexão. Chaves ficam criptografadas. Uma conta pode atender vários produtos, mas cada produto possui vínculo explícito com a configuração utilizada.
2. **Planos**: cadastrar preço e periodicidade do produto.
3. **Assinaturas**: selecionar cliente, produto e plano. Na própria linha estão botões Ativar/Reativar, Suspender, Bloquear, Cancelar, Excluir, Alterar plano (quando permitido), Trial e Bonificar. Botões abrem confirmação contextual, sem pedir código de ação.
4. **Assinatura → Cobranças**: exibe cliente, produto, plano, preço e vencimento. Iniciar cobrança usa a configuração do produto, não exige ambiente nem identificador digitado. A operação e os pagamentos permanecem vinculados à assinatura.
5. **Cobranças**: lista identifica cliente/produto/plano; lançamento manual seleciona assinatura pelo nome, não por ID livre.

Bonificações aparecem na listagem, mantêm prazo ou ausência de prazo e impedem iniciar recorrência ou cobrança manual. No Comercial, bonificações existentes sem vínculo continuam com a regra original. Ao criar vínculo, o sistema exige bonificação equivalente no Central, inclusive data final. Não converte bonificação em cobrança automaticamente.

## Alterações de banco e validação

Migration `20261112_03` adiciona `produtos.config_asaas_id`. Foi aplicada somente no MySQL local do Central e verificada sem drift. Configurações de produção, contratos e credenciais não foram criados nem alterados automaticamente. Reinicie web e worker após atualização.

SQL inicial e incrementais gerados para MySQL/PostgreSQL. Banco na revisão 02 usa `04_atualizar_20261112_02_para_head.sql`; não reaplicar scripts de estrutura inicial.

O histórico técnico conserva identificadores para auditoria, mas nenhum formulário operacional exige digitá-los. A página Conexões dos produtos mantém somente credenciais de comunicação; não configura cobrança.

## Validação executada

- 57 testes Central passaram, incluindo vínculo da configuração ao produto, fila por assinatura, bloqueio de cobrança em bonificação e botões diretamente na listagem.
- 50 testes `src/tests` do Comercial passaram.
- 12 testes selecionados do Comercial passaram: integração, preservação de bonificação sem prazo, não prorrogação de bonificação vencida e serviços bancários Asaas/Inter.
- Smoke de renderização de listagem, detalhe, cobrança de produto, conexões e cobranças passou com dados temporários, sem rede externa.
- Smoke HTTP local passou; SQL das revisões 01/02/03 foi compilado para MySQL/PostgreSQL; MySQL local na revisão 03, sem drift.
- Nenhuma cobrança real criada, nenhuma bonificação persistente alterada e nenhum processo de importação executado. Não houve deploy ou homologação visual em navegador.

Backup anterior ao ajuste: `D:\App_LiveSun\LiveSun_CentralControle\backups\Ajuste-cobranca-UX-20261112-194452`.