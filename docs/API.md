# API LiveSun Central v1

Base: `/api/v1`. JSON UTF-8. Bearer JWT de serviço, issuer `livesun-central`, audience `livesun-products`, algoritmo HS256 e scopes explícitos. Health é público. Um token só acessa o produto ao qual pertence; não há enumeração de outros produtos. Integrações confiáveis com `write` têm administração comercial do seu produto: nunca distribua esse scope ao navegador ou a clientes finais.

| Método / rota | Scope | Resposta |
|---|---|---|
| GET `/health` | público | serviço/banco; 200 ou 503 |
| GET `/produtos` | read | produto do token, planos e módulos ativos |
| GET `/entitlements/{cliente_id}/{produto_codigo}` | read | estado efetivo; 404 se não cadastrado |
| GET `/assinaturas/{id}` | read | assinatura e entitlements |
| POST `/assinaturas` | write | 201; cria e audita |
| PATCH `/assinaturas/{id}/status` | write | estado efetivo atualizado |
| PATCH `/assinaturas/{id}/plano` | write | troca imediata; 422 se não permitido |
| PATCH `/assinaturas/{id}/modulos` | write | liberação/remoção imediata; 422 se não permitido |
| PATCH `/assinaturas/{id}/limites` | write | sobrescreve limites informados |
| POST `/produtos/{id}/webhooks/registrar` | webhooks | cadastra URL/segredo |
| POST `/webhooks/{id}/reenviar` | webhooks | 202; agenda nova tentativa |

IDs são inteiros positivos; campos desconhecidos são rejeitados. Erros: 400 JSON malformado, 401 sem credencial válida, 403 sem scope, 404 fora do produto/inexistente, 409 duplicidade/vínculo incompatível, 422 regra/validação, 429 rate limit, 500 falha interna sem detalhe sensível. Formato: `{"error":"mensagem"}`. Limite de payload: 128 KiB. Rate limit API: 120/minuto por IP, compartilhado por Redis em produção.

## Corpos de requisição

Criação:

```json
{"cliente_id":123,"produto_id":1,"plano_id":1,"status":"TRIAL","data_inicio":"2026-11-12","data_fim":null,"data_proxima_cobranca":"2026-12-12"}
```

Status: `{"status":"SUSPENSA","motivo":"Inadimplência"}`. Estados: TRIAL, ATIVA, SUSPENSA, BLOQUEADA, CANCELADA, EXPIRADA, EXCLUIDA. A criação admite TRIAL/ATIVA; não se retorna a TRIAL; EXCLUIDA é terminal. CANCELADA/EXPIRADA só reativam para ATIVA ou são excluídas. Reativar requer inexistência de outra assinatura vigente para o par cliente/produto. Suspensa/bloqueada mantêm a vaga vigente; encerradas liberam a vaga sem apagar dados.

Plano: `{"plano_id":2}`. Módulo: `{"modulo_id":3,"liberado":false,"limite":null}`. Dependências impedem remoção; remova dependentes explicitamente antes. Troca de plano substitui imediatamente a composição inteira por módulos do novo plano mais obrigatórios; dados operacionais nunca são apagados.

Limites: `{"limites":{"usuarios":3,"propostas_mes":100}}`. Valores inteiros não negativos; zero significa zero, não ilimitado. Limite não definido é omitido. Overrides de assinatura têm precedência sobre plano.

Webhook: `{"url_webhook":"https://propostas.livesun.com.br/webhooks/assinatura","webhook_secret":"segredo-aleatorio-com-pelo-menos-32-caracteres"}`. Host precisa estar autorizado pelo ambiente; porta 443, sem credencial/fragmento, resolução pública. Não há retorno do segredo.

## Entitlements

```json
{
  "cliente_id":"123",
  "produto":"PROPOSTAS",
  "assinatura_id":987,
  "status":"ATIVA",
  "plano":"PROPOSTAS",
  "acesso_produto":true,
  "modulos":[],
  "limites":{"usuarios":3,"propostas_mes":100},
  "versao":4,
  "gerado_em":"2026-11-12T18:30:00+00:00",
  "valido_ate":"2026-11-12T18:45:00+00:00"
}
```

Datas são UTC ISO 8601 com offset explícito. Somente ATIVA/TRIAL, com cliente/produto disponíveis e prazo contratual válido, permitem acesso. Demais estados retornam acesso false, módulos vazios e limites vazios. Excluir é lógico. A consulta escolhe a assinatura vigente; sem vigente retorna a última encerrada.

## Webhook assinado

POST HTTPS com os headers `Content-Type: application/json`, `X-LiveSun-Event`, `X-LiveSun-Timestamp` (Unix segundos) e `X-LiveSun-Signature`.

Assinatura exata:

```text
sha256=<hex HMAC-SHA256(secret, timestamp ASCII + '.' + bytes exatos do corpo)>
```

Não normalize/reencode JSON antes de verificar. Compare com tempo constante. Rejeite timestamp com diferença absoluta maior que 300 segundos. Cada retry usa timestamp e assinatura novos, mantendo `evento_id` e snapshot.

```json
{
  "evento":"ASSINATURA_SUSPENSA",
  "evento_id":"evt_1234567890abcdef",
  "ocorrido_em":"2026-11-12T18:20:00+00:00",
  "cliente_id":"123",
  "produto":"PROPOSTAS",
  "assinatura_id":987,
  "versao":5,
  "status_anterior":"ATIVA",
  "status_novo":"SUSPENSA",
  "motivo":"Inadimplência",
  "dados":{"bloquear_login":true,"bloquear_recursos":true},
  "entitlements":{
    "cliente_id":"123","produto":"PROPOSTAS","assinatura_id":987,
    "versao":5,"status":"SUSPENSA","plano":"PROPOSTAS","acesso_produto":false,
    "modulos":[],"limites":{},"gerado_em":"2026-11-12T18:20:00+00:00","valido_ate":"2026-11-12T18:35:00+00:00"
  }
}
```

O snapshot `entitlements` completo é obrigatório no contrato do receptor implementado. Responda 200 após persistir atualização e `evento_id` atomicamente. Duplicatas respondem 200 sem repetir efeitos. Snapshots com par `(assinatura_id, versao)` anterior ao conhecido são registrados, mas não aplicados. Não assuma ordem de entrega.

Outbox: mudança, evento e entrega persistem na mesma transação. Worker reivindica entrega com lock e lease de 90 segundos; status PENDENTE → ENVIANDO → ENTREGUE/FALHA/ESGOTADA. Backoff `min(3600,5*2^tentativas)`; máximo automático 8 tentativas. Reenvio manual preserva histórico e agenda mais uma tentativa; se falhar após o limite, volta a ESGOTADA. Corpo HTTP retornado não é armazenado. Auditoria armazena snapshots de negócio e não credenciais.

Eventos: ASSINATURA_CRIADA, ASSINATURA_ATIVADA, ASSINATURA_SUSPENSA, ASSINATURA_BLOQUEADA, ASSINATURA_REATIVADA, ASSINATURA_CANCELADA, ASSINATURA_EXPIRADA, ASSINATURA_EXCLUIDA, PLANO_ALTERADO, MODULO_LIBERADO, MODULO_REMOVIDO, LIMITE_ALTERADO, COBRANCA_CRIADA, COBRANCA_PAGA e COBRANCA_ATRASADA. Eventos de plano/módulo nunca são gerados para PROPOSTAS com suas flags desabilitadas. Cobranças manuais podem gerar eventos financeiros; não alteram acesso por si mesmas.

## Reconciliação genérica

Produtos devem oferecer GET `{url_producao}/central/estado/{cliente_id}`, assinado com os mesmos headers HMAC, usando bytes do **path** como conteúdo assinado. Retorno: `{"cliente_id":"123","produto":"PROPOSTAS","assinatura_id":987,"versao":5,"entitlements":{...}}`. Requisições GET têm janela de replay de 300 segundos e são somente leitura.

`flask --app wsgi reconcile` compara ID, versão, status, plano, acesso, módulos e limites; registra divergências sem publicar payloads no console. `--repair` agenda snapshot de reconciliação com evento LIMITE_ALTERADO e flag `reconciliacao:true`, sem mudar o status contratual. O operador deve monitorar o resumo e a auditoria; indisponibilidade não é tratada como convergência.