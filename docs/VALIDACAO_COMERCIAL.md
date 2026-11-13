# Validação da etapa Comercial — 12/11/2026

## Resultados

- Central: **53 testes passaram**; incluem credenciais persistentes/revogação, painel, importação idempotente sem rede, autenticação do webhook Asaas, eventos antigos consultando estado atual, operação ambígua exigindo revisão, retenção e purga por produto, impedimento de purga com nova assinatura e upgrade preservando registros existentes.
- Comercial `src/tests`: **50 testes passaram**, incluindo módulos, permissões, cadastro/trial legado e integração nova em SQLite descartável.
- Comercial `tests/test_central_assinatura_separation.py`, `test_asaas_boleto.py`, `test_inter_bolepix.py`: **10 testes passaram**.
- Smoke HTTP real local do Central: passou (health, login, logo, criação e suspensão) com banco temporário.
- Central MySQL local: migration `20261112_02` aplicada; `flask db check` sem diferenças.
- Comercial MySQL local: tabelas aditivas da integração criadas; configuração ativa = zero. Nenhuma migração de contrato, alteração de status, purga ou criação de cobrança real realizada.
- Configuração Asaas do Central = zero; operações Asaas = zero; purgas = zero na conferência local.
- SQL inicial e incremental Central gerado offline para MySQL/PostgreSQL; DDL do Comercial gerado nos dois dialetos.
- Compilação Python e `git diff --check`: sem erros; dependências Central consistentes.
- Comparação SHA-256 com o backup confirmou preservação de `.env` do Comercial e de todos os sete arquivos operacionais conferidos: serviços/clientes/rotas Asaas e Inter e rota de cobranças bancárias.

## Backup

`D:\App_LiveSun\LiveSun_CentralControle\backups\Comercial-antes-central-20261112-191645` contém código, configurações e arquivos locais; excluídos do backup desta etapa o ambiente virtual, histórico Git, caches, dist e backups anteriores. A subpasta `central-antes` preserva o Central anterior. Backup não substitui dump dos bancos.

## Pendente / não afirmar como homologado

- Asaas sandbox real e produção não foram acessados; nenhum segredo bancário foi lido ou migrado automaticamente.
- Migração dos contratos existentes é iniciada pelo operador com prévia, não foi executada.
- Integração permanece desativada no Comercial; purga possui trava adicional de homologação desabilitada por padrão.
- Purga foi testada em esquema mínimo descartável, não na cópia completa do banco Comercial. Dependências desconhecidas, RLS/PostgreSQL e arquivos/anexos exigem ensaio específico. Não há exclusão automática de diretórios.
- Receptor de purga do Propostas ainda não implementado; Central não o chama até homologação específica desse produto.
- Captura/tokenização de cartão e prorrata não implementadas. Boleto/Pix e ciclos mensal/anual são o escopo desta etapa.
- UI verificada por testes de páginas/templates, não por automação visual/mobile.
- Autocadastro de empresa no Comercial integrado cria empresa/usuário locais sem criar automaticamente contrato no Central: operador deve provisionar/vincular; acesso permanece negado sem vínculo. Pareamento automático e portal de pagamento do cliente exigem evolução adicional.
- Não houve deploy, commit ou push. Confira arquivos ignorados pelo `.gitignore` antes de publicar testes/migrations novos.

O guia de operação e virada está em `D:\App_LiveSun\LiveSun_CentralControle\livesun-central\docs\COMERCIAL_CENTRAL.md`.