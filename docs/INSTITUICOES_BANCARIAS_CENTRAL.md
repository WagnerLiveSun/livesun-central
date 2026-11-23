# Instituições bancárias e integração de pagamento no Central

O catálogo é uma cópia estática dos 461 códigos e nomes do arquivo de referência
`D:\App_LiveSun\LiveSun_Comercial_X\migrations\mysql\042_create_instituicoes_bancarias.sql`.
Não é uma consulta ao vivo ao Banco Central; atualizações futuras exigem revisão.
Os códigos são strings de três caracteres: `001` não deve virar o número `1`.

O cadastro de integrações do Central permite associar um código do catálogo ou
deixá-lo vazio para provedores que não sejam instituições bancárias. Registros
anteriores não são vinculados por nome automaticamente. O vínculo identifica o
provedor, mas não implementa protocolo ou emissão de cobrança.

## Atualização PostgreSQL controlada

O arquivo de atualização é
`D:\App_LiveSun\LiveSun_CentralControle\livesun-central\deploy\sql\postgresql\07_instituicoes_e_gateway_20261119_03_para_20261123_02.sql`.
Foi gerado offline pelas duas migrations `20261123_01` e `20261123_02` e vale
**somente** para o banco e esquema exclusivos do Central na revisão `20261119_03`.
Não aplicar no banco do Comercial. É uma atualização única; não é reexecutável.

1. Antes de qualquer alteração, faça backup verificado e confirme conexão, banco,
   esquema e revisão Alembic com o responsável pela operação. Não presuma a
   revisão do banco a partir do commit da aplicação.
2. Planeje a janela de publicação: a aplicação em produção exige que a revisão
   do banco corresponda exatamente à versão do código. Atualizar o banco antes
   do deploy pode impedir a inicialização do código antigo; publicar o código
   antes da atualização também impede a inicialização.
3. Em cliente PostgreSQL configurado para parar em erro, execute o arquivo
   integralmente no esquema dedicado do Central, após revisão do SQL. Ele cria
   `gateways_alternativos`, `instituicoes_bancarias`, carrega o catálogo, cria
   chave estrangeira e atualiza `alembic_version` em uma transação. Uma revisão
   diferente provoca erro e a transação deve ser desfeita. Se interromper, faça
   `ROLLBACK` e inspecione o estado antes de tentar novamente.
4. As consultas finais devem retornar revisão `20261123_02` e 461 instituições.
   Publique o código correspondente e verifique a saúde da aplicação e o log
   de preparação. O Render não aplica migrations em produção.

Escolha **uma única abordagem**: o SQL acima ou as migrations Alembic
equivalentes, nunca ambos. Não executar seed separado. O SQL não contém
credenciais e não altera tabelas Asaas, clientes ou assinaturas. Não modifica o
Comercial. PostgreSQL real deve ser homologado em cópia descartável antes da
execução em produção; o teste local da migration foi feito em SQLite e a saída
SQL foi gerada offline para PostgreSQL.

Para regenerar o SQL sem conexão ao banco, na raiz do Central:

```powershell
.\.venv\Scripts\python.exe scripts\gerar_sql_instituicoes_bancarias.py
```