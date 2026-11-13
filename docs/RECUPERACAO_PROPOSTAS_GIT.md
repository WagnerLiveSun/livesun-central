# Recuperação do Propostas a partir do Git — 12/11/2026

## Origem confirmada

- Repositório: `WagnerLiveSun/livesun-propostas`.
- Branch padrão confirmada via `git ls-remote --symref origin HEAD`: `main`.
- Commit remoto: `fcea0abca8757bb93590e5bb60a3f011219117c1`, de 30/10/2026.
- `git fetch origin --prune` executado com sucesso. Na consulta, não havia commit mais recente em `origin/main`; a divergência estava nas alterações locais não commitadas.

## Procedimento

1. Backup completo do diretório local, inclusive `.git`, `.venv`, arquivos ignorados, uploads e configurações, em `D:\App_LiveSun\LiveSun_CentralControle\backups\Propostas-antes-atualizacao-20261112-183945`.
2. Patch das alterações rastreadas salvo no backup.
3. Arquivos rastreados restaurados com `git restore --source=origin/main --worktree -- .`; sem limpeza de arquivos ignorados ou não rastreados.
4. Reaplicados apenas hooks comerciais na factory/login, preservando autenticação, RBAC, PDF, logo, envios e health check da versão remota.
5. Mantidos módulos novos de integração, migration, configurações locais e testes; health check isento do bloqueio comercial para monitorar infraestrutura sem liberar rotas de negócio.
6. Testes originais isolados das configurações de integração do `.env` para executar em bancos temporários sem depender do ambiente pessoal.

Não reaplicadas as regressões locais antigas em scripts SQL, rotas de gestão/propostas e testes que removiam funcionalidades já presentes no Git. Todas permanecem recuperáveis no backup.

## Validação final

- Suíte completa do Propostas: **48 testes passaram em 37,242 segundos**.
- `pip check`: dependências consistentes.
- `compileall`: sem erros.
- `git diff --check`: sem erros.
- `.env` e arquivo SQLite local comparados por hash com o backup: preservados.
- Health: 200; CSS versionado presente na página de login.
- Consulta do produto ao Central local: ATIVA, acesso true.
- Nenhuma migration ou alteração de status contratual executada durante a recuperação.
- Nenhum commit ou push realizado. Alterações de integração permanecem locais para revisão/publicação.

Log final em `D:\App_LiveSun\LiveSun_CentralControle\backups\Propostas-antes-atualizacao-20261112-183945\validacao-final.txt`.

Este relatório substitui as pendências de CSS e asserção de impressão registradas em validações anteriores: ambas foram resolvidas pela restauração da versão remota, não por enfraquecimento dos testes.