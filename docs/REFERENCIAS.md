# Referências técnicas

Documentação oficial consultada para configuração de deploy e armazenamento de rate limit:

- Render Blueprint: `https://render.com/docs/blueprint-spec`
- Render deploys: `https://render.com/docs/deploys`
- Grupos de ambiente e segredos: `https://render.com/tutorials/advanced-blueprint-patterns/env-var-groups`
- Flask-Limiter configuration: `https://flask-limiter.readthedocs.io/en/latest/configuration.html`

O grupo de ambiente deve ser preenchido antes da sincronização do Blueprint; `sync:false` não é aplicável dentro de grupos. O backend `memory://` não compartilha limites entre processos e foi restrito ao desenvolvimento/testes nesta aplicação. A configuração precisa ser validada no plano Render e rede contratados.