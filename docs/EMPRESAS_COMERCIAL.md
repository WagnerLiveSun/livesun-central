# Empresas do Comercial: descoberta e migracao controlada

## Separacao

O Comercial permanece no MySQL da Hostinger. O Central usa seu proprio banco.
Nao cadastrar credenciais MySQL do Comercial no Environment do Central.
Este fluxo nao modifica lancamentos, baixas manuais ou cobrancas bancarias operacionais.

## Publicacao posterior (nao executada nesta implementacao)

1. Preservar backups separados dos bancos e arquivos e o estado de Environment.
2. Publicar primeiro o Comercial com as novas rotas de descoberta e callback legado.
3. Manter `CENTRAL_ENABLED=false` no Comercial e preencher a origem HTTPS do Central,
   token COMERCIAL e o mesmo HMAC cadastrado no produto COMERCIAL do Central.
4. Publicar o Central com menu Empresas do Comercial. Nao e necessaria migration
   adicional para esta funcionalidade: usa as tabelas de integracao ja existentes.
5. No Central, produto COMERCIAL ativo, URL de producao do Comercial correta e
   `WEBHOOK_ALLOWED_HOSTS` contendo seu host, preservando o host do Propostas.
6. Manter o worker do Central configurado para confirmar os vinculos.

## Operacao

- Primeiro abra **Empresas do Comercial > 1. Conferir e migrar planos**. A API
  assinada `/central/planos?apos=N` exporta ofertas ativas ou contratadas, com
  versao, preco, moeda, periodicidade e limite de usuarios. Nao exporta segredos.
- A previa percorre todas as paginas, sem gravar dados. Selecione os planos
  ausentes e confirme a conferencia para importa-los. Planos equivalentes ja
  existentes nao sao duplicados. Nenhuma assinatura ou cobranca e criada aqui.
- A importacao e transacional e auditada. Mudanca no catalogo apos a previa,
  divergencia de preco/limite, varias versoes com condicoes distintas, moeda nao
  BRL ou plano existente incompatível exigem revisao; nao sao sobrescritos.
- Depois siga **2. Conferir e migrar assinaturas**. A previa de cada empresa
  oferece somente os planos compativeis e exige selecao explicita. Se nenhum
  corresponder, informa isso antes de confirmar e permite trazer os da origem.
- Empresas do Comercial consulta `/central/empresas?apos=N` em paginas de 50.
- HMAC cobre timestamp e caminho completo, incluindo query. Sem redirecionamento HTTP.
- A consulta e somente leitura e funciona antes da ativacao. Nao expoe senhas,
  chaves bancarias, certificados ou IDs de recorrencias do gateway.
- Preparar migracao cria apenas uma solicitacao idempotente, nao cliente/assinatura.
- A previa consulta novamente a origem. Confirmar exige cliente de mesmo documento,
  plano equivalente, justificativa e aceite explicito. Nao une CNPJs automaticamente.
- Hash da origem auditado impede confirmar ou concluir callback com dados alterados.
- A confirmacao preserva inicio, vencimento, fim do trial, bonificacao e limite de
  usuarios. Trial vencido fica EXPIRADA; nao concede sete dias novos.
- Cancelada/suspensa nao vira ativa. Bonificacao vigente e preservada com o prazo
  original ou sem prazo, conforme a origem, sem criar cobranca.
- Se o preco existe na oferta legada, deve corresponder ao plano. Se esta ausente,
  a tela avisa e exige conferencia expressa do operador, sem inventar preco.
- Cliente com assinatura COMERCIAL existente exige revisao manual, sem duplicacao.
- Recorrencia externa existente, alteracao de plano agendada, restricao parcial
  sem equivalente, falta de assinatura ou dados invalidos bloqueiam a migracao.
- Bonificacao vencida exige regularizacao na origem; nao e prorrogada automaticamente.
- O worker envia callback autenticado para `/central/cadastros/vincular` e recebe
  confirmacao idempotente. Falha fica visivel e com retentativa; nao repete assinatura.
- O callback legado prepara o vinculo/cache, mas nao troca plano ou limites locais
  nem ativa a integracao. Webhooks operacionais continuam rejeitados enquanto inativa.
- Ativar o controle e uma decisao separada, somente apos conferir TODAS as empresas,
  assinaturas, bonificacoes, callbacks e acesso. Nao habilitar purga neste processo.

## Limites de validacao

Testes usam SQLite em memoria, requisicoes remotas simuladas e Chromium com recursos
locais. Nao houve acesso a bancos reais, migracao de assinaturas reais ou deploy.
Validar a comunicacao HTTPS/HMAC e a execucao do worker em homologacao antes da virada.

Backup local anterior: `D:\App_LiveSun\LiveSun_CentralControle\backups\empresas-comercial-local-20261116-190805`.