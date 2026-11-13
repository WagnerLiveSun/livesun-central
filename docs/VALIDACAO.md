# Validação executada em 12/11/2026

## Central

- `python -m pytest -q --disable-warnings`: **29 testes passaram**, seis avisos de bibliotecas/migrations.
- `python scripts/smoke_http.py`: **passou**, com servidor HTTP real local e migration em SQLite temporário: health, login, asset do logo, criação e suspensão de assinatura.
- `python -m compileall -q app tests scripts migrations`: sem erros de compilação.
- `python -m pip check`: dependências consistentes.
- Migration inicial em banco SQLite vazio, `flask db check` sem diferenças e seed repetido sem duplicidade.
- SQL offline de migration compilado nos dialetos MySQL e PostgreSQL.
- Migration de produção não contém operações de drop e recusa downgrade destrutivo.

## Propostas

- `.venv\Scripts\python.exe -m unittest discover -s tests -p test_central.py`: **8 testes passaram**.
- Compilação dos novos arquivos e migration: sem erros.
- `git diff --check`: sem erros de whitespace; apenas avisos de normalização LF/CRLF existentes.
- Suíte preexistente `test_app.py`: **21 testes executados, 19 passaram, um erro e uma falha**. Erro: `stylesheet_url` versionada ausente. Falha: asserção local exige literal `window.print() - test_app.py:182` em vez de `window.print()`. Esses problemas já constavam das alterações locais; não foram mascarados nem o teste modificado.

## Não executado

Não houve deploy, acesso a bancos de produção, Redis, teste em MySQL/PostgreSQL real, entrega HTTPS entre serviços publicados, teste visual em navegador nem auditoria de logs da infraestrutura. Nenhum banco do produto foi conectado pelo Central. Nenhuma migration foi aplicada ao banco real do Propostas. Nenhum `.env` real foi criado/modificado e nenhum segredo de produção foi lido para esta implementação.

Consulte `ACEITE.md` para validação pendente. A implementação local não significa que todos os critérios de produção estejam concluídos.

## Complemento: inicializador Windows e MySQL local

- Configurado `.env` local ignorado pelo Git, com chaves aleatórias e banco exclusivo `central` em `localhost:3306`.
- Servidor local identificado como MySQL 8.0.31; banco inicialmente vazio.
- Executado `D:\App_LiveSun\LiveSun_CentralControle\Iniciar_LiveSun_Central.bat --prepare-only` duas vezes: migration `20261112_01` aplicada, 15 tabelas criadas e nenhuma diferença com os models.
- Seed: um produto PROPOSTAS, um plano e nenhum operador. Primeiro início interativo solicita cadastro seguro do superadmin.
- Seed SQL MySQL executado duas vezes sem duplicar produto/plano.
- HTTP com aplicação conectada ao MySQL local: health, login e logo retornaram 200.
- Suíte atualizada: **33 testes passaram**, incluindo verificações do exportador SQL e inicializador.
- SQL de estrutura e seed exportado para MySQL e PostgreSQL em `deploy/sql`; não aplicado a serviços de produção.
- PostgreSQL continua sem teste contra servidor real. Teste interativo de navegador/cadastro do operador deve ser realizado pelo usuário na primeira execução do `.bat`.