# Webhooks: validação preventiva e recuperação

Salvar o receptor no painel/API agora realiza POST assinado de diagnóstico com nonce aleatório, sem efeito comercial. O produto devolve sua identidade e prova HMAC. Apenas HTTP 200, JSON válido, nonce e prova correspondentes permitem persistir a configuração. Página inicial, login HTML, produto errado, segredo incorreto ou serviço indisponível não substituem a configuração anterior.

Ao salvar uma configuração validada, as entregas sem sucesso do produto são reenfileiradas automaticamente com a URL confirmada. O evento e seu payload não são recriados; as tentativas anteriores continuam no histórico. Novas tentativas usam o destino atual configurado, com auditoria da atualização quando necessário.

Indisponibilidade temporária usa backoff. Depois do limite de tentativas, o worker verifica periodicamente o receptor antes de retomar. Erros 401/403/404/405/422 e semelhantes entram em CONFIGURACAO: não continua disparando eventos no endereço errado; a cada cinco minutos, um teste sem efeito comercial verifica se o receptor voltou/corrigiu. A entrega só é concluída quando o POST do evento é confirmado pelo receptor.

O contrato INTEGRACAO_TESTE foi adicionado aos receptores do Comercial e Propostas. É autenticado com timestamp/HMAC como os eventos reais e não exige cliente vinculado nem altera cache/assinatura. Propostas também reconhece os eventos de trial e cortesia adicionados ao Central.

Não existe garantia de falha zero em rede distribuída: portas conflitantes, processos parados e segredos divergentes precisam ser corrigidos. A mudança evita aceitar configuração incorreta e reduz reenvios manuais após a conexão voltar. Nenhum erro é escondido e nenhuma entrega é marcada como concluída sem resposta do produto.

Reinicie os três serviços e o worker após atualizar. Comercial e Propostas precisam de portas/endpoints distintos quando rodam simultaneamente. Não redirecione evento de um produto para outro.

Validação desta revisão: 94 testes Central, 32 selecionados Comercial e 12 testes de integração Propostas passaram. O teste no ambiente local em execução não foi concluído porque os serviços não estavam escutando nas portas locais na verificação final. Nenhuma configuração inválida foi persistida para contornar isso.