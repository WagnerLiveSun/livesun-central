# PostgreSQL local — LiveSun Central

## Ambiente preparado

- Host: `127.0.0.1`
- Porta: `55433`
- Banco exclusivo: `DbCentral` (respeitar maiúsculas no nome).
- Driver: `postgresql+psycopg`.
- Perfil local: `D:\App_LiveSun\LiveSun_CentralControle\livesun-central\.env.postgresql`.

A senha está somente no perfil local, ignorado pelo Git. Não copie credenciais para documentação ou scripts versionados. As variáveis `DB_ENGINE=postgresql` e `DATABASE_URL` desse perfil são as usadas pela aplicação; `POSTGRES_*` registra os parâmetros fornecidos.

O banco já existia e foi preservado. Aplicadas as migrations até `20261112_04`, criando a estrutura de 21 tabelas, inclusive `alembic_version`. `flask db check` executado contra PostgreSQL sem diferenças com os models.

## Como iniciar

1. Encerre o Central MySQL se estiver usando a porta 5001.
2. Abra `D:\App_LiveSun\LiveSun_CentralControle\Iniciar_LiveSun_Central_PostgreSQL.bat`.
3. No primeiro início, crie o superadmin quando solicitado. Não existe usuário/senha padrão.
4. Acesse `http://127.0.0.1:5001/login`.

O inicializador aplica migrations pendentes e inicia web e worker usando o mesmo perfil. O `.env` MySQL não é substituído. Para usar outra porta, execute o `.bat` com `--port 5003` e ajuste o endereço de consulta nos produtos que forem testar.

Para somente conferir/preparar, sem iniciar processos ou pedir usuário:

```powershell
& 'D:\App_LiveSun\LiveSun_CentralControle\Iniciar_LiveSun_Central_PostgreSQL.bat' --prepare-only
```

## Configuração separada, não cópia dos dados

Clientes, assinaturas, operadores, planos comerciais e credenciais cadastrados no MySQL **não foram copiados**. O seed cria apenas os registros iniciais de produtos e o plano único do Propostas. Configure os dados e as integrações deste banco antes de testar fluxos reais. Os vínculos dos produtos para IDs do MySQL não devem ser presumidos válidos no PostgreSQL.

O perfil reutiliza as chaves da aplicação local para permitir o mesmo formato de sessão/criptografia, mas isso não transfere registros. Ao alternar entre bancos, faça novo login. Não execute a suíte com `TEST_DATABASE_URL` apontando para `DbCentral`: os fixtures de teste removem tabelas. Use banco descartável para testes destrutivos.

Para preparar novamente com verificação de exclusividade, use `D:\App_LiveSun\LiveSun_CentralControle\livesun-central\scripts\preparar_postgresql_local.py`. O script recusa banco não vazio sem Alembic e tabelas externas ao Central; não usa `drop` nem redefine dados existentes.

Nenhum deploy, commit ou push foi realizado. Para produção, use credencial de runtime com privilégios reduzidos, TLS e segredos próprios; não exponha o usuário administrativo local.