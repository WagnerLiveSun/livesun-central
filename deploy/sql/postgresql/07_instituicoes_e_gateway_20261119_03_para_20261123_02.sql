-- Central PostgreSQL: 20261119_03 -> 20261123_02. Banco exclusivo do Central.

-- Catálogo: snapshot do Comercial 042; não consulta a internet nem altera o Comercial.

-- Backup obrigatório. Executar em cliente SQL com parada em erro.

-- Atualiza Alembic somente após criar a estrutura e inserir os dados.

BEGIN;

DO $$ BEGIN IF (SELECT COUNT(*) FROM alembic_version) <> 1 OR NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = '20261119_03') THEN RAISE EXCEPTION 'Revisão divergente: esperado 20261119_03'; END IF; END $$;

CREATE TABLE gateways_alternativos (
    id SERIAL NOT NULL,
    produto_id INTEGER NOT NULL,
    nome VARCHAR(100) NOT NULL,
    ambiente VARCHAR(20) NOT NULL,
    url_api VARCHAR(500) NOT NULL,
    url_callback VARCHAR(500),
    credenciais_criptografadas TEXT NOT NULL,
    ativo BOOLEAN DEFAULT false NOT NULL,
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT pk_gateways_alternativos PRIMARY KEY (id),
    CONSTRAINT fk_gateways_alternativos_produto_id_produtos FOREIGN KEY(produto_id) REFERENCES produtos (id),
    CONSTRAINT uq_gateway_alternativo_produto_nome_ambiente UNIQUE (produto_id, nome, ambiente)
);

CREATE INDEX ix_gateways_alternativos_produto_id ON gateways_alternativos (produto_id);



CREATE TABLE instituicoes_bancarias (
    codigo_banco VARCHAR(3) NOT NULL,
    nome_banco VARCHAR(150) NOT NULL,
    criado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_instituicoes_bancarias PRIMARY KEY (codigo_banco)
);

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('001', 'Banco do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('070', 'BRB - BANCO DE BRASILIA S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('539', 'SANTINVEST S.A. - CREDITO, FINANCIAMENTO E INVESTIMENTOS');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('430', 'COOPERATIVA DE CREDITO RURAL SEARA - CREDISEARA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('272', 'AGK CORRETORA DE CAMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('136', 'COOPERATIVA CENTRAL DE CRÉDITO UNICRED DO BRASIL - UNICRED DO BRASIL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('407', 'SEFER INVESTIMENTOS DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('104', 'CAIXA ECONOMICA FEDERAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('009', 'Secretaria do Tesouro Nacional - STN');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('714', 'FINAMAX S.A. - CREDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('077', 'Banco Inter S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('423', 'COLUNA S/A DISTRIBUIDORA DE TITULOS E VALORES MOBILIÁRIOS');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('741', 'BANCO RIBEIRAO PRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('330', 'BANCO BARI DE INVESTIMENTOS E FINANCIAMENTOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('534', 'EWALLY INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('743', 'Banco Semear S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('100', 'Planner Corretora de Valores S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('541', 'FUNDO GARANTIDOR DE CREDITOS - FGC');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('096', 'Banco B3 S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('747', 'Banco Rabobank International Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('362', 'CIELO S.A. - INSTITUIÇÃO DE PAGAMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('322', 'Cooperativa de Crédito Rural de Abelardo Luz - Sulcredi/Crediluz');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('748', 'BANCO COOPERATIVO SICREDI S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('350', 'COOPERATIVA DE CRÉDITO POPULAR DO BRASIL - CREHNOR');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('752', 'Banco BNP Paribas Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('379', 'COOPERFORTE COOPERATIVA DE CRÉDITO E INVESTIMENTOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('399', 'Kirton Bank S.A. - Banco Múltiplo');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('378', 'BANCO BRASILEIRO DE CRÉDITO SOCIEDADE ANÔNIMA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('413', 'BANCO BV S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('756', 'BANCO COOPERATIVO SICOOB S.A. - BANCO SICOOB');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('360', 'TRINUS CAPITAL DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('757', 'BANCO KEB HANA DO BRASIL S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('102', 'XP INVESTIMENTOS CORRETORA DE CÂMBIO,TÍTULOS E VALORES MOBILIÁRIOS S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('084', 'SISPRIME DO BRASIL - COOPERATIVA DE CRÉDITO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('591', 'BANVOX DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('555', 'PAN FINANCEIRA S.A. - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTOS');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('180', 'CM CAPITAL MARKETS CORRETORA DE CÂMBIO, TÍTULOS E VALORES MOBILIÁRIOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('066', 'BANCO MORGAN STANLEY S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('015', 'UBS BB CORRETORA DE CÂMBIO, TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('143', 'INTEX BANK BANCO DE CÂMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('074', 'Banco J. Safra S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('099', 'UNIPRIME CENTRAL NACIONAL - CENTRAL NACIONAL DE COOPERATIVA DE CREDITO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('387', 'Banco Toyota do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('326', 'MEUTUDO S.A - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('025', 'Banco Alfa S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('075', 'BANCO ABN AMRO CLEARING S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('040', 'Banco Cargill S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('307', 'Terra Investimentos Distribuidora de Títulos e Valores Mobiliários Ltda.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('517', 'PAGUEVELOZ INSTITUIÇÃO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('385', 'COOPERATIVA DE ECONOMIA E CREDITO MUTUO DOS TRABALHADORES PORTUARIOS DA GRANDE VITORIA - CREDESTIVA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('425', 'SOCINAL S.A. - CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('190', 'SERVICOOP - COOPERATIVA DE CRÉDITO DOS SERVIDORES PÚBLICOS ESTADUAIS E MUNICIPAIS DO RIO GRANDE DO SUL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('296', 'OZ SOCIEDADE CORRETORA DE CÂMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('063', 'Banco Bradescard S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('191', 'Nova Futura Corretora de Títulos e Valores Mobiliários Ltda.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('764', 'INDEPENDÊNCIA COOPERATIVA DE CRÉDITO E INVESTIMENTO - INDEPENDÊNCIA COOPERATIVA DE CRÉDITO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('382', 'FIDÚCIA SOCIEDADE DE CRÉDITO AO MICROEMPREENDEDOR E À EMPRESA DE PEQUENO PORTE LIMITADA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('064', 'GOLDMAN SACHS DO BRASIL BANCO MULTIPLO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('097', 'CREDISIS - CENTRAL DE COOPERATIVAS DE CRÉDITO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('016', 'COOPERATIVA DE CRÉDITO MÚTUO DOS DESPACHANTES DE TRÂNSITO DE SANTA CATARINA E RIO GRANDE DO SUL - SICOOB CREDITRAN');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('299', 'BANCO AFINZ S.A. - BANCO MÚLTIPLO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('540', 'HBI SOCIEDADE DE CRÉDITO DIRETO S/A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('468', 'PORTOSEG S.A. - CREDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('012', 'Banco Inbursa S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('003', 'BANCO DA AMAZONIA S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('060', 'CONFIDENCE SOCIEDADE CORRETORA DE CAMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('037', 'Banco do Estado do Pará S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('411', 'Via Certa Financiadora S.A. - Crédito, Financiamento e Investimentos');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('359', 'ZEMA CRÉDITO, FINANCIAMENTO E INVESTIMENTO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('159', 'Casa do Crédito S.A. Sociedade de Crédito ao Microempreendedor');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('085', 'Cooperativa Central de Crédito - Ailos');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('400', 'COOPERATIVA DE CRÉDITO, POUPANÇA E SERVIÇOS FINANCEIROS - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('410', 'PLANNER SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('548', 'RPW S/A SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('036', 'Banco Bradesco BBI S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('469', 'PICPAY INVEST DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('394', 'Banco Bradesco Financiamentos S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('004', 'Banco do Nordeste do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('458', 'HEDGE INVESTMENTS DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('320', 'BANK OF CHINA (BRASIL) BANCO MÚLTIPLO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('189', 'HS FINANCEIRA S/A CREDITO, FINANCIAMENTO E INVESTIMENTOS');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('105', 'Lecca Crédito, Financiamento e Investimento S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('076', 'Banco KDB do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('082', 'BANCO TOPÁZIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('312', 'HSCM - SOCIEDADE DE CRÉDITO AO MICROEMPREENDEDOR E À EMPRESA DE PEQUENO PORTE LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('195', 'VALOR S/A SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('093', 'PÓLOCRED   SOCIEDADE DE CRÉDITO AO MICROEMPREENDEDOR E À EMPRESA DE PEQUENO PORTE LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('391', 'COOPERATIVA DE CREDITO RURAL DE IBIAM - SULCREDI/IBIAM');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('273', 'COOPERATIVA DE CREDITO SULCREDI AMPLEA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('368', 'Banco CSF S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('673', 'COOPERATIVA DE CRÉDITO RURAL DO AGRESTE ALAGOANO - COOPERAGRE');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('290', 'PAGSEGURO INTERNET INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('259', 'MONEYCORP BANCO DE CÂMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('395', 'F.D''GOLD - DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('364', 'EFÍ S.A. - INSTITUIÇÃO DE PAGAMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('157', 'ICAP do Brasil Corretora de Títulos e Valores Mobiliários Ltda.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('183', 'SOCRED S.A. - SOCIEDADE DE CRÉDITO AO MICROEMPREENDEDOR E À EMPRESA DE PEQUENO PORTE');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('014', 'STATE STREET BRASIL S.A. - BANCO COMERCIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('130', 'CARUANA S.A. - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('358', 'MIDWAY S.A. - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('127', 'Codepe Corretora de Valores e Câmbio S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('079', 'PICPAY BANK - BANCO MÚLTIPLO S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('141', 'BANCO MASTER DE INVESTIMENTO S.A. - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('081', 'BancoSeguro S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('475', 'Banco Yamaha Motor do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('133', 'CONFEDERAÇÃO NACIONAL DAS COOPERATIVAS CENTRAIS DE CRÉDITO E ECONOMIA FAMILIAR E SOLIDÁRIA - CRESOL CONFEDERAÇÃO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('703', 'GETNET ADQUIRÊNCIA E SERVIÇOS PARA MEIOS DE PAGAMENTO S.A. INSTITUIÇÃO DE PAGAMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('323', 'MERCADO PAGO INSTITUIÇÃO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('577', 'DESENVOLVE SP - AGÊNCIA DE FOMENTO DO ESTADO DE SÃO PAULO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('121', 'Banco Agibank S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('083', 'Banco da China Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('787', 'ATTRUS INSTITUIÇÃO DE PAGAMENTO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('138', 'GET MONEY SOCIEDADE CORRETORA DE CÂMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('024', 'Banco Bandepe S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('384', 'GLOBAL FINANÇAS SOCIEDADE DE CRÉDITO AO MICROEMPREENDEDOR E À EMPRESA DE PEQUENO PORTE LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('426', 'NEON FINANCEIRA - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('576', 'MERCADO BITCOIN INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('670', 'BSN PAGAMENTOS INSTITUIÇÃO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('319', 'OM DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('274', 'BMP SOCIEDADE DE CRÉDITO AO MICROEMPREENDEDOR E A EMPRESA DE PEQUENO PORTE LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('095', 'BANCO TRAVELEX S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('094', 'Banco Finaxis S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('478', 'GAZINCRED S.A. SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('276', 'BANCO SENFF S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('780', 'SAFETYPAY BRASIL INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('447', 'MIRAE ASSET (BRASIL) CORRETORA DE CÂMBIO, TÍTULOS  E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('569', 'CONTA PRONTA INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('686', 'BIZ INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('047', 'Banco do Estado de Sergipe S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('144', 'EBURY BANCO DE CÂMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('332', 'ACESSO SOLUÇÕES DE PAGAMENTO S.A. - INSTITUIÇÃO DE PAGAMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('450', 'FITS INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('126', 'BR Partners Banco de Investimento S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('301', 'DOCK INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('173', 'APEX GROUP DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('331', 'OSLO CAPITAL DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('119', 'Banco Western Union do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('396', 'MAGALUPAY INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('509', 'CELCOIN INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('254', 'PARANÁ BANCO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('268', 'BARI COMPANHIA HIPOTECÁRIA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('401', 'IUGU INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('107', 'Banco Bocom BBM S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('334', 'BANCO BESA S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('412', 'SOCIAL BANK BANCO MÚLTIPLO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('124', 'Banco Woori Bank do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('149', 'Facta Financeira S.A. - Crédito Financiamento e Investimento');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('197', 'STONE INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('439', 'ID CORRETORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('690', 'BK INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('142', 'Broker Brasil Corretora de Câmbio Ltda.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('529', 'PINBANK BRASIL INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('415', 'BANCO NACIONAL S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('389', 'Banco Mercantil do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('634', 'BANCO TRIANGULO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('132', 'ICBC do Brasil Banco Múltiplo S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('298', 'VIPS CORRETORA DE CÂMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('377', 'BMS SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('321', 'CREFAZ SOCIEDADE DE CRÉDITO AO MICROEMPREENDEDOR E A EMPRESA DE PEQUENO PORTE S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('542', 'CLOUDWALK INSTITUIÇÃO DE PAGAMENTO E SERVICOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('260', 'NU PAGAMENTOS S.A. - INSTITUIÇÃO DE PAGAMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('573', 'OXY COMPANHIA HIPOTECÁRIA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('470', 'CDC SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('129', 'UBS BB BANCO DE INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('562', 'AZIMUT BRASIL DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('128', 'BRAZA BANK S.A. BANCO DE CÂMBIO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('416', 'LAMARA SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('595', 'IFOOD PAGO INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('461', 'ASAAS GESTÃO FINANCEIRA INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('665', 'STARK BANK S.A. - INSTITUICAO DE PAGAMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('194', 'UNIDA DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('538', 'SUDACRED SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('588', 'AVANCARD PROVER INSTITUIÇÃO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('768', 'BECKER FINANCEIRA S.A. - CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('561', 'PAY4FUN INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('772', 'COOPERATIVA DE CRÉDITO MÚTUO DOS EMPREGADOS DO CENTRO UNIVERSITÁRIO NEWTON PAIVA LTDA. - CREDIPAIVA - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('536', 'NEON PAGAMENTOS S.A. - INSTITUIÇÃO DE PAGAMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('383', 'EBANX INSTITUICAO DE PAGAMENTOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('324', 'CARTOS SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('560', 'MAG INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('533', 'SRM BANK INSTITUIÇÃO DE PAGAMENTO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('310', 'VORTX DISTRIBUIDORA DE TITULOS E VALORES MOBILIARIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('380', 'PICPAY INSTITUIçãO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('566', 'FLAGSHIP INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('280', 'WILL FINANCEIRA S.A. CRÉDITO, FINANCIAMENTO E INVESTIMENTO - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('146', 'GUITTA CORRETORA DE CAMBIO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('769', '99PAY INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('803', 'DLOCAL BRASIL INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('651', 'PAGARE INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('671', 'ZERO INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('685', 'TYCOON TECHNOLOGY INSTITUICAO DE PAGAMENTO S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('593', 'TRANSFEERA INSTITUIÇÃO DE PAGAMENTO S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('335', 'Banco Digio S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('349', 'AL5 S.A. SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('427', 'COOPERATIVA DE CRÉDITO DOS SERVIDORES DA UNIVERSIDADE FEDERAL DO ESPIRITO SANTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('374', 'REALIZE SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('271', 'BPY CORRETORA DE CÂMBIO, TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('674', 'HINOVA PAY INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('021', 'BANESTES S.A. BANCO DO ESTADO DO ESPIRITO SANTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('246', 'Banco ABC Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('292', 'GALAPAGOS CAPITAL DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('000', 'Sistema do Balcão B3');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('554', 'BANCO STONEX S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('751', 'Scotiabank Brasil S.A. Banco Múltiplo');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('352', 'SANTANDER CORRETORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('208', 'Banco BTG Pactual S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('683', 'BRASIL CASH INSTITUICAO DE PAGAMENTO S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('386', 'NU FINANCEIRA S.A. - Sociedade de Crédito, Financiamento e Investimento');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('675', 'CASAS BAHIA PAY INSTITUIÇÃO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('557', 'PAGPRIME INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('546', 'OKTO INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('241', 'BANCO CLASSICO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('783', 'SWAP INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('398', 'IDEAL CORRETORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('336', 'Banco C6 S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('612', 'Banco Guanabara S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('604', 'Banco Industrial do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('505', 'BANCO UBS (BRASIL) S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('550', 'BEETELLER INSTITUIÇÃO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('552', 'UZZIPAY INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('804', 'MÊNTORE INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('329', 'QI Sociedade de Crédito Direto S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('196', 'FAIR SOCIEDADE CORRETORA DE CÂMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('662', 'WE PAY OUT INSTITUICAO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('693', 'EFEX INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('342', 'Creditas Sociedade de Crédito Direto S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('567', 'MERCANTIL FINANCEIRA S.A. - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('300', 'Banco de la Nacion Argentina');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('477', 'Citibank N.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('266', 'BANCO CEDULA S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('122', 'Banco Bradesco BERJ S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('376', 'BANCO J.P. MORGAN S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('348', 'Banco XP S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('473', 'Banco Caixa Geral - Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('745', 'Banco Citibank S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('708', 'BANCO INDUSCRED DE INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('120', 'BANCO RODOBENS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('677', 'GOWD INSTITUIÇÃO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('265', 'Banco Fator S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('007', 'BANCO NACIONAL DE DESENVOLVIMENTO ECONOMICO E SOCIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('188', 'ATIVA INVESTIMENTOS S.A. CORRETORA DE TÍTULOS, CÂMBIO E VALORES');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('134', 'BGC LIQUIDEZ DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('719', 'BANCO MASTER MÚLTIPLO S.A. - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('467', 'MASTER S/A CORRETORA DE CÂMBIO, TÍTULOS E VALORES MOBILIÁRIOS - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('243', 'BANCO MASTER S/A - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('774', 'MOVA SOCIEDADE DE EMPRÉSTIMO ENTRE PESSOAS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('397', 'LISTO SOCIEDADE DE CREDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('078', 'Haitong Banco de Investimento do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('760', 'EMCASH SERVIÇOS FINANCEIROS SOCIEDADE DE EMPRÉSTIMO ENTRE PESSOAS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('355', 'ÓTIMO SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('531', 'BMP SOCIEDADE DE CRÉDITO DIRETO S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('660', 'PAGME INSTITUIÇÃO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('597', 'ISSUER INSTITUICAO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('528', 'CBSF DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.- EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('659', 'ONEKEY PAYMENTS INSTITUICAO DE PAGAMENTO SA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('687', 'INCO SOCIEDADE DE EMPRÉSTIMO ENTRE PESSOAS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('676', 'DUFRIO FINANCEIRA, CRÉDITO, FINANCIAMENTO E INVESTIMENTOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('695', 'BEES INSTITUICAO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('445', 'PLANTAE S.A. - CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('788', 'PROTOTYPE INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('586', 'Z1 INSTITUIÇÃO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('373', 'UP.P SOCIEDADE DE EMPRÉSTIMO ENTRE PESSOAS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('111', 'OLIVEIRA TRUST DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIARIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('512', 'FINVEST DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('599', 'AGORACRED S/A SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('516', 'PLACARPAY S.A. - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('408', 'BONUSPAGO SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('679', 'PAY INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('484', 'APEX DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('402', 'COBUCCIO S/A - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTOS');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('507', 'SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO EFÍ S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('404', 'SUMUP SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('418', 'ZIPDIN SOLUÇÕES DIGITAIS SOCIEDADE DE CRÉDITO DIRETO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('615', 'SMART SOLUTIONS GROUP INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('414', 'LEND SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('449', 'DM SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('587', 'FIDD DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('518', 'MERCADO CRÉDITO SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('406', 'ACCREDITO - SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('765', 'PAGSMILE INSTITUIÇÃO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('403', 'CORA SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('419', 'NUMBRS SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('435', 'DELFINANCE SOCIEDADE DE CREDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('770', 'V3 INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('805', 'BANCO DE DESENVOLVIMENTO DE MINAS GERAIS S.A.-BDMG');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('544', 'MULTICRED SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('421', 'LAR COOPERATIVA DE CRÉDITO - LAR CREDI');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('443', 'OCTA SOCIEDADE DE CRÉDITO DIRETO S.A. - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('535', 'OPEA SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('457', 'UY3 SOCIEDADE DE CRÉDITO DIRETO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('428', 'CREDSYSTEM SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('448', 'HEMERA DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('452', 'CREDIFIT SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('596', 'CACTVS INSTITUICAO DE PAGAMENTO S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('510', 'FFCRED SOCIEDADE DE CRÉDITO DIRETO S.A..');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('462', 'STARK SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('465', 'CAPITAL CONSIG SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('636', 'GIRO - SOCIEDADE DE CRÉDITO DIRETO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('563', 'PROTEGE CASH INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('556', 'SAYGO SOCIEDADE CORRETORA DE CÂMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('305', 'FOURTRADE CORRETORA DE CÂMBIO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('463', 'AZUMI DISTRIBUIDORA DE TíTULOS E VALORES MOBILIáRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('590', 'REPASSES FINANCEIROS E SOLUCOES TECNOLOGICAS INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('451', 'J17 - SOCIEDADE DE CRÉDITO DIRETO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('444', 'TRINUS SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('519', 'LIONS TRUST DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('454', 'MÉRITO DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('460', 'UNAVANTI SOCIEDADE DE CRÉDITO DIRETO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('506', 'RJI CORRETORA DE TITULOS E VALORES MOBILIARIOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('482', 'ARTTA SOCIEDADE DE CRÉDITO DIRETO S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('017', 'BNY Mellon Banco S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('759', 'BANSUR JM SOCIEDADE DE CRÉDITO DIRETO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('174', 'PEFISA S.A. - CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('481', 'SUPERLÓGICA SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('688', 'KIKAI SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('521', 'PEAK SOCIEDADE DE EMPRÉSTIMO ENTRE PESSOAS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('433', 'BR-CAPITAL DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('495', 'Banco de La Provincia de Buenos Aires');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('523', 'HR DIGITAL - SOCIEDADE DE CRÉDITO DIRETO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('794', 'ATUAL SOCIEDADE CORRETORA DE CÂMBIO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('527', 'ATICCA - SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('704', 'FESTOR INSTITUIÇÃO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('511', 'MAGNUM SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('520', 'SOMAPAY SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('513', 'ATF SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('663', 'ACTUAL DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('792', 'NIXFIN SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('697', 'JM CORRETORA DE CÂMBIO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('125', 'BANCO GENIAL S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('496', 'BBVA BRASIL BANCO DE INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('547', 'BNK DIGITAL SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('592', 'INSTITUIÇÃO DE PAGAMENTOS MAPS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('678', 'FIDEM SOCIEDADE DE CRÉDITO DIRETO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('532', 'FUTURO SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('537', 'SELECT CREDIT SOCIEDADE DE CRÉDITO AO MICROEMPREENDEDOR E À EMPRESA DE PEQUENO PORTE LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('524', 'WNT CAPITAL DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('476', 'IDEA MAKER INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('526', 'MONETARIE SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('682', 'MONERY INSTITUICAO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('488', 'JPMorgan Chase Bank, National Association');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('669', 'TRANSFERO INSTITUICAO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('775', 'CONTAAZUL INSTITUICAO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('522', 'RED SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('530', 'SER FINANCE SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('575', 'DGBK CREDIT S.A. - SOCIEDADE DE CRÉDITO DIRETO.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('668', 'CELCOIN SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('594', 'ASA SOCIEDADE DE CRÉDITO FINANCIAMENTO E INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('553', 'PERCAPITAL SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('574', 'A55 SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('065', 'Banco AndBank (Brasil) S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('551', 'VERT DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('559', 'KANASTRA FINANCEIRA S.A, CREDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('579', 'QUADRA SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('619', 'TRIO INSTITUICAO DE PAGAMENTO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('696', 'LOAN BRASIL SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('571', 'MONTE BRAVO CORRETORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('145', 'LEVYCAM - CORRETORA DE CAMBIO E VALORES LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('250', 'BANCO BMG CONSIGNADO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('598', 'KONECT SOCIEDADE DE CRÉDITO DIRETO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('681', 'MT INSTITUICAO DE PAGAMENTO SA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('585', 'SETHI SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('701', 'INTEGRAÇÃO DE CRÉDITO E COBRANÇA SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('589', 'G5 SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('620', 'REVOLUT SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('572', 'ALL IN CRED SOCIEDADE DE CREDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('795', 'BANCO TRATON BRASIL S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('786', 'AWX BRASIL  INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('614', 'SANTS SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('632', 'Z-ON SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('766', 'LB PAY INSTITUIÇÃO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('785', 'LA FINTECA INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('672', 'STONE SOCIEDADE DE CREDITO, FINANCIAMENTO E INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('269', 'BANCO HSBC S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('023', 'CONTA SIMPLES SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('700', 'MW INSTITUICAO DE PAGAMENTO LTDA - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('761', 'URBANO S.A. - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('773', 'KIWIFY INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('790', 'MAX INSTITUIÇÃO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('213', 'Banco Arbi S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('644', '321 SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('694', 'WOOVI INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('139', 'Intesa Sanpaolo Brasil S.A. - Banco Múltiplo');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('661', 'FREEX SOCIEDADE CORRETORA DE CÂMBIO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('680', 'DELTA GLOBAL SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('763', 'VUE INSTITUIÇÃO DE PAGAMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('692', 'ZYDI SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('684', 'HARMOS S.A. - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('789', 'APUSDIGITAL INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('771', 'WX INSTITUICAO DE PAGAMENTO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('018', 'Banco Tricury S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('781', 'BASE DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('422', 'Banco Safra S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('698', 'BIT SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('630', 'BANCO LETSBANK S.A. - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('224', 'Banco Fibra S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('778', 'PB SOCIEDADE DE CREDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('393', 'Banco Volkswagen S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('600', 'Banco Luso Brasileiro S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('390', 'BANCO GM S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('623', 'Banco Pan S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('699', 'BFC SOCIEDADE DE CRÉDITO DIRETO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('655', 'Banco Votorantim S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('479', 'Banco ItauBank S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('456', 'Banco MUFG Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('464', 'Banco Sumitomo Mitsui Brasileiro S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('341', 'ITAÚ UNIBANCO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('237', 'Banco Bradesco S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('381', 'BANCO MERCEDES-BENZ DO BRASIL S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('613', 'Omni Banco S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('637', 'BANCO SOFISA S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('793', 'MAGALUPAY - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('653', 'BANCO PLENO S.A. - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('069', 'Banco Crefisa S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('370', 'Banco Mizuho do Brasil S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('249', 'Banco Investcred Unibanco S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('318', 'Banco BMG S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('626', 'BANCO C6 CONSIGNADO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('508', 'AVENUE SECURITIES BANCO DE INVESTIMENTO S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('366', 'BANCO SOCIETE GENERALE BRASIL S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('113', 'NEON CORRETORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('131', 'TULLETT PREBON BRASIL CORRETORA DE VALORES E CÂMBIO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('011', 'UBS (BRASIL) CORRETORA DE VALORES S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('611', 'Banco Paulista S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('755', 'Bank of America Merrill Lynch Banco Múltiplo S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('089', 'CREDISAN COOPERATIVA DE CRÉDITO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('643', 'Banco Pine S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('140', 'NU INVESTIMENTOS S.A. - CORRETORA DE TÍTULOS E VALORES MOBILIÁRIOS');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('707', 'Banco Daycoval S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('288', 'CAROL DISTRIBUIDORA DE TITULOS E VALORES MOBILIARIOS LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('767', 'QORE DISTRIBUIDORA DE TITULOS E VALORES MOBILIÁRIOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('363', 'QI CORRETORA DE TÍTULOS E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('101', 'WARREN RENA DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('487', 'DEUTSCHE BANK S.A. - BANCO ALEMAO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('233', 'BANCO BMG SOLUÇÕES FINANCEIRAS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('791', 'MULTIPLIKE FINANCEIRA S.A. SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('564', 'ANKOR CAPITAL - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO S/A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('438', 'TRUSTEE DISTRIBUIDORA DE TÍTULOS E VALORES MOBILIÁRIOS LTDA. - EM LIQUIDAÇÃO EXTRAJUDICIAL');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('365', 'BINANCE BRASIL CORRETORA DE CÂMBIO E VALORES MOBILIÁRIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('633', 'Banco Rendimento S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('218', 'Banco BS2 S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('293', 'Lastro RDV Distribuidora de Títulos e Valores Mobiliários Ltda.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('514', 'EXIM SOCIEDADE CORRETORA DE CÂMBIO LTDA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('080', 'BT CORRETORA DE CÂMBIO LTDA.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('565', 'ÁGORA CORRETORA DE TITULOS E VALORES MOBILIARIOS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('753', 'Novo Banco Continental S.A. - Banco Múltiplo');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('222', 'BANCO CRÉDIT AGRICOLE BRASIL S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('281', 'Cooperativa de Crédito Rural Coopavel');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('754', 'Banco Sistema S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('610', 'Banco VR S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('712', 'OURIBANK S.A. BANCO MÚLTIPLO');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('010', 'CREDICOAMO CREDITO RURAL COOPERATIVA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('440', 'CREDI&GENTE - COOPERATIVA DE CRÉDITO E INVESTIMENTOS');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('283', 'RB INVESTIMENTOS DISTRIBUIDORA DE TITULOS E VALORES MOBILIARIOS LIMITADA');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('033', 'BANCO SANTANDER (BRASIL) S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('646', 'DM SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO S.A');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('217', 'Banco John Deere S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('041', 'Banco do Estado do Rio Grande do Sul S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('543', 'COOPERATIVA DE ECONOMIA E CRÉDITO MÚTUO DOS ELETRICITÁRIOS E DOS TRABALHADORES DAS EMPRESAS DO SETOR DE ENERGIA - COOPCRECE');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('654', 'BANCO DIGIMAIS S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('212', 'Banco Original S.A.');

INSERT INTO instituicoes_bancarias (codigo_banco, nome_banco) VALUES ('289', 'EFX CORRETORA DE CÂMBIO LTDA.');

ALTER TABLE gateways_alternativos ADD COLUMN codigo_banco VARCHAR(3);

ALTER TABLE gateways_alternativos ADD CONSTRAINT fk_gateways_alternativos_codigo_banco_instituicoes_bancarias FOREIGN KEY(codigo_banco) REFERENCES instituicoes_bancarias (codigo_banco);

CREATE INDEX ix_gateways_alternativos_codigo_banco ON gateways_alternativos (codigo_banco);



UPDATE alembic_version SET version_num='20261123_02' WHERE version_num='20261119_03';

COMMIT;

-- Conferência após COMMIT:

SELECT version_num FROM alembic_version;

SELECT COUNT(*) AS instituicoes FROM instituicoes_bancarias;
