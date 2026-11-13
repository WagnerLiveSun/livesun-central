# Scripts SQL para instalação após homologação

Atualização desta etapa: para um Central já na revisão `20261112_01`, use somente `03_atualizar_20261112_01_para_head.sql` do dialeto correspondente, ou `flask db upgrade`. O script `01` passou a conter toda a cadeia e continua exclusivo de banco vazio. Nunca aplique o incremental em banco já na revisão `20261112_02`.

Arquivos gerados a partir das migrations, sem senha, token, cliente, assinatura de teste ou usuário administrativo:

- `D:\App_LiveSun\LiveSun_CentralControle\livesun-central\deploy\sql\mysql\01_estrutura_inicial.sql`
- `D:\App_LiveSun\LiveSun_CentralControle\livesun-central\deploy\sql\mysql\02_seed_propostas.sql`
- `D:\App_LiveSun\LiveSun_CentralControle\livesun-central\deploy\sql\postgresql\01_estrutura_inicial.sql`
- `D:\App_LiveSun\LiveSun_CentralControle\livesun-central\deploy\sql\postgresql\02_seed_propostas.sql`

## Aplicação

1. Faça backup e escolha banco **exclusivo e vazio** no provedor de destino. Os scripts não criam banco nem concedem privilégios.
2. Selecione o dialeto correto e aplique `01_estrutura_inicial.sql` uma única vez. O script inclui a revisão Alembic, permitindo migrations futuras sem `stamp` manual.
3. Aplique `02_seed_propostas.sql`: produto e plano único, sem módulos, valor inicial zero. O seed pode repetir sem duplicar e não sobrescreve configurações existentes.
4. Configure variáveis de ambiente do serviço para o banco de destino; execute `flask --app wsgi db current` e `flask --app wsgi db check`.
5. Execute `flask --app wsgi create-admin` e configure preço, limites e credenciais pelo ambiente/painel.

**Escolha SQL manual OU `flask db upgrade` para instalação inicial; não aplique ambos sobre o mesmo esquema.** Não reaplique o script 01 em banco já migrado. MySQL não oferece rollback completo de DDL: em falha, inspecione o estado antes de repetir. PostgreSQL inclui transação na estrutura gerada.

MySQL Hostinger: selecione no cliente SQL/phpMyAdmin o banco exclusivo já criado; importe em UTF-8. Não execute no banco de nenhum produto. PostgreSQL: selecione o banco/esquema dedicado e use ferramenta compatível com scripts PostgreSQL. A compatibilidade dos serviços de produção ainda exige homologação.

Os scripts instalam a estrutura, não transportam os dados dos testes locais. Se surgirem novas migrations após esta exportação, regenere os arquivos antes da instalação inicial; para bancos existentes, use somente migrations incrementais.

Para regenerar, na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe scripts\exportar_sql.py
```

O exportador é offline e nunca conecta aos bancos de produção.