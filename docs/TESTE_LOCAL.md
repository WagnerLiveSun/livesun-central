# Integração na mesma máquina

Central: `http://127.0.0.1:5001`. Propostas: `http://127.0.0.1:5000`.

No `.env` do Central:

```dotenv
APP_ENV=development
WEBHOOK_ALLOW_LOCAL_HTTP=true
WEBHOOK_ALLOWED_HOSTS=127.0.0.1,localhost,propostas.livesun.com.br
```

No cadastro do produto PROPOSTAS no Central:

- URL do produto: `http://127.0.0.1:5000`
- URL do webhook: `http://127.0.0.1:5000/webhooks/assinatura`
- Credencial HMAC: a mesma configurada no Propostas (não alterar nem publicar para testar).

No `.env` do Propostas:

```dotenv
FLASK_ENV=development
CENTRAL_ENABLED=true
CENTRAL_BASE_URL=http://127.0.0.1:5001
CENTRAL_ALLOW_LOCAL_HTTP=true
```

Token, segredo e vínculo empresa/cliente continuam obrigatórios. Reinicie os dois sistemas após alterar variáveis, incluindo o worker do Central. O `.bat` do Central inicia web e worker; não mantenha instâncias antigas abertas.

Teste suspensão e reativação pelo painel e confira entrega HTTP 200 em Webhooks. Não use dados reais para testes destrutivos. Falhas antigas conservam URL/snapshot original para auditoria; mudanças futuras usam o destino atual. Um evento de reconciliação pode atualizar o estado sem mudar o contrato: `flask --app wsgi reconcile --repair`.

HTTP é permitido somente com opt-in em desenvolvimento e para host loopback autorizado. HMAC, JWT, timestamp e idempotência não são desativados. Em produção, desligue ambas as flags HTTP, substitua URLs locais por HTTPS e mantenha allowlist restrita. Localhost significa a própria máquina: estes endereços não servem para conectar duas máquinas/containers distintos.