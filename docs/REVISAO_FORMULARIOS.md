# Revisão de formulários — 12/11/2026

## Diagnóstico local

O produto COMERCIAL possui apenas um plano ativo, PREMIUM, já contratado nas assinaturas locais. Alteração de plano exclui corretamente o plano atual, mas antes mostrava seletor vazio sem explicação. Não foi criado plano adicional automaticamente.

## Correções

- Troca de plano: alternativas apenas ativas do mesmo produto, excluindo atual. Sem alternativa, exibe orientação, links para cadastro/listagem de planos do produto e desabilita confirmação vazia.
- Nova assinatura: preserva filtro restrito ao formulário; bloqueia criação também na ausência de cliente/produto, não apenas de plano.
- Cadastros genéricos: defaults de status/ativo aplicados corretamente; seletores sem opções não viram campos livres de ID; produto/código imutáveis preservados na edição; módulos listam somente produtos compatíveis.
- Edição de plano: produto inativo permanece identificado corretamente; composição de módulos voltou à tela específica com checkboxes e seleção salva.
- Cobranças: estado vazio explícito e botão bloqueado sem assinaturas elegíveis; bonificação vigente não é cobrada.
- Módulos em assinatura e habilitação de cadastro: seletores vazios explicados e confirmação desabilitada.
- Campos JSON inválidos recebem mensagem específica. Nenhum segredo é incluído na mensagem.

## Validação

- 82 testes passaram, incluindo envio de troca de plano, composição de módulos, defaults, ausência de opções e varredura de formulários renderizados (CSRF presente, sem forms aninhados, selects não vazios).
- Chromium com páginas renderizadas em banco temporário: diálogo de plano com/sem alternativas, abertura/fechamento, categoria Comercial, nova assinatura e execução de JS nas páginas de clientes, produtos, módulos, usuários, cobranças, webhooks, cobrança de produto e conexões. Sem erros de JavaScript nesse ensaio.
- Testes não executam alterações nos dados locais reais nem chamadas ao Asaas. Somente leitura do banco local para diagnóstico; sem migrations nesta revisão.

O teste de navegador é reproduzível com `scripts/auditar_formularios_browser.py`, usando o Python com Playwright já disponível no projeto Comercial.