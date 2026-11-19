# Validação da continuidade — 19/11/2026

## Resultados executados

| Projeto | Resultado | Tempo | Avisos |
|---|---|---|---|
| Central | **274 passed** | 58,18 s | 14 warnings |
| Propostas | **179 passed + 28 subtests passed** | 100,96 s | 58 warnings |

Comando, executado na raiz de cada projeto, usando seu próprio virtualenv:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings --tb=short
```

No Central foi explicitado `TEST_DATABASE_URL=sqlite:///:memory:`. A fixture
agora recusa outro banco para a suíte funcional. Os testes de migration usam
SQLite temporário e geração SQL offline dos dialetos; **não são aplicação de
migration em PostgreSQL**. Ambas as suítes bloqueiam HTTP externo por padrão;
testes de integração usam mocks. Nenhuma mensagem ou cobrança real foi enviada.

`compileall` dos fontes/testes concluído nos dois projetos. `git diff --check`
sem erros de whitespace; Git avisou apenas normalização futura LF/CRLF em
templates já existentes. Os warnings de pytest não foram eliminados; executar
sem `--disable-warnings` para investigar cada aviso em manutenção separada.

## Cobertura verificada

- Contratação mensal/anual, 80/MONTHLY e 600/YEARLY no payload do servidor.
- Nova contratação e repetição; reaproveitamento de trial sem alterar início,
  término e quota; recuperação de recorrência após resposta ambígua.
- HMAC de passagem válido, inválido e expirado; ID isolado rejeitado; dados da
  empresa autenticada prevalecem sobre parâmetros forjados.
- Assinaturas/cobranças de clientes diferentes não são resolvidas por customer.
- Webhook autenticado, duplicado, fora de ordem, falha e reprocessamento;
  endpoint antigo e compatível não geram dois eventos.
- Pagamento mantém TRIAL; renovação paga mantém ATIVA; nenhuma ativação
  automática. Liberação manual autorizada registra usuário/data; repetição é no-op.
- Worker existente chama o processamento da outbox e mantém supervisor existente.
- E-mails de criação, pagamento e vencimento; pagamento CONFIRMED/RECEIVED
  produz um aviso. Liberação usa o mesmo fluxo de acesso sem segundo e-mail.
- Falha de envio não desfaz pagamento; resultado incerto não repete; sandbox
  não envia a destinatário fora da allowlist; produção recusa cliente sandbox.
- Migração de ampliação validada em SQLite temporário e SQL offline; nenhum
  downgrade executado.

## Segunda conferência do banco

Nova auditoria usando o script somente leitura confirmou:

- `transaction_read_only=on`.
- Revisão **20261119_02**, sem execução da nova **20261119_03**.
- Assinaturas #1 ATIVA, #2 TRIAL, #3 ATIVA; todas sem Asaas habilitado.
- Nenhuma configuração Asaas e nenhum candidato a teste pelos marcadores usados.

O arquivo local `.auditoria-entrega4.json` contém o inventário técnico sem
credenciais e é ignorado pelo Git. Não usá-lo como catálogo público de clientes.

## Limitações do aceite

Não executados: worker contra produção, pagamento real, acesso à conta Asaas,
consulta aos webhooks remotos, envio Brevo real, publicação Render ou teste
PostgreSQL descartável. Assim, os resultados demonstram comportamento local
isolado e preservação das consultas de produção, não aceite externo completo.

Roteiro de publicação, variáveis, worker, retorno e bloqueios em
`D:\App_LiveSun\LiveSun_CentralControle\livesun-central\docs\ENTREGA_4_PUBLICACAO.md`.