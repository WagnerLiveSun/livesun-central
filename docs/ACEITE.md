# Checklist de homologação

Marcar somente após executar no ambiente de destino. Os testes automatizados são evidência local, não aceite de infraestrutura.

## Automatizado local

- [x] Criação, TRIAL, ativação, suspensão, bloqueio, reativação, cancelamento e exclusão lógica.
- [x] Entitlements permitidos/bloqueados, limites e validação de entrada.
- [x] Plano único e proibição de upgrade/módulos do PROPOSTAS.
- [x] Futuro produto com múltiplos planos, upgrade/downgrade e dependências de módulos.
- [x] JWT separado do painel, scopes e isolamento por produto.
- [x] Páginas do painel, CSRF e restrições de perfis.
- [x] Auditoria sem campos de senha/segredo.
- [x] Webhooks HMAC, falha/retry/reenvio e histórico de tentativas.
- [x] Cobrança manual, atraso, pagamento e expiração.
- [x] Migration em banco vazio SQLite, sem drift e seed idempotente.
- [x] Geração SQL offline MySQL/PostgreSQL.
- [x] Propostas: login/recursos bloqueados por suspensão, restauração, replay, duplicatas, eventos fora de ordem, cache refresh e indisponibilidade.

## Obrigatório antes de produção

- [ ] Executar migrations e testes em MySQL real dedicado, com mesma versão/configuração da Hostinger.
- [ ] Executar migrations e testes em PostgreSQL real/MontuDB.
- [ ] Testar concorrência: duas assinaturas simultâneas, duas mudanças de status, worker concorrente e cadastro de plano único.
- [ ] Validar URLs, CA/TLS, rede remota, egress e allowlist.
- [ ] Deploy web + worker + Redis, HTTPS, cookies e proxy confiável.
- [ ] Criar superadmin com senha forte; validar cada perfil por ação.
- [ ] Configurar valor/limites do plano único antes de contratar clientes.
- [ ] Configurar HMAC e JWT no Propostas; confirmar que nenhum segredo foi commitado.
- [ ] Aplicar migration no Propostas e vincular todas as empresas corretas aos clientes do Central.
- [ ] Habilitar CENTRAL_ENABLED e comprovar ciclo real entre serviços HTTPS.
- [ ] Suspender/bloquear e testar novo login e uma sessão já autenticada; reativar e confirmar retorno.
- [ ] Simular queda do Central até e após TTL; comprovar política fail-closed.
- [ ] Testar retries, reenvio manual, crash do worker e idempotência real.
- [ ] Testar `reconcile`, induzir divergência e reparar via snapshot.
- [ ] Conferir que exclusão lógica não remove dados comerciais ou operacionais.
- [ ] Auditar logs do proxy, hospedagem e Propostas; backups, restauração e rotação de chaves.
- [ ] Validar enforcement de limites no produto antes de anunciar limites rígidos.
- [ ] Revisar duas falhas preexistentes da suíte do Propostas indicadas em LIMITACOES.md.
- [ ] Validar UI desktop/mobile, teclado, contraste e temas BlueMetal/Moonlight.