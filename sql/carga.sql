-- Carga dos CSVs gerados por notebooks/tratamento.ipynb em dados/tratados/.
-- Rodar na raiz do repositório, depois de sql/origem.sql. Segue a ordem das chaves estrangeiras; tudo ou nada.
-- A coluna atualizado_em não vem nos CSVs: o banco a preenche. HEADER MATCH confere que o cabeçalho de cada
-- CSV é exatamente a lista de colunas, para que uma mudança no tratamento nunca desloque valores.
-- Uso: psql --dbname="$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/carga.sql

\set ON_ERROR_STOP on
BEGIN;
SET search_path TO origem;
\copy municipio (ibge,nome,fonte,data_coleta) FROM 'dados/tratados/municipio.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy funcao (codigo,nome) FROM 'dados/tratados/funcao.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy elemento_despesa (codigo,nome) FROM 'dados/tratados/elemento_despesa.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy credor (id_credor,documento,nome) FROM 'dados/tratados/credor.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy material (id_material,descricao,unidade_medida) FROM 'dados/tratados/material.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy documento_fiscal (id_documento,id_emitente,tipo,numero,data_emissao,chave_acesso) FROM 'dados/tratados/documento_fiscal.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy empenho (id_empenho,ibge,id_origem,entidade,numero,ano,data_emissao,tipo,id_credor,codigo_elemento,elemento_inferido,codigo_funcao,historico,valor) FROM 'dados/tratados/empenho.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy item_empenho (id_empenho,sequencia,id_material,quantidade,valor_unitario,valor_total) FROM 'dados/tratados/item_empenho.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy empenho_documento_fiscal (id_empenho,id_documento,valor) FROM 'dados/tratados/empenho_documento_fiscal.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy anulacao_empenho (id_empenho,sequencia,data,tipo,motivo,valor) FROM 'dados/tratados/anulacao_empenho.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy liquidacao (id_liquidacao,id_empenho,numero,data,valor,valor_anulado) FROM 'dados/tratados/liquidacao.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy retencao (id_retencao,id_liquidacao,id_empenho,data,valor) FROM 'dados/tratados/retencao.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy pagamento (id_pagamento,id_empenho,numero_ordem,data,valor,valor_anulado,historico) FROM 'dados/tratados/pagamento.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy diaria (id_diaria,ibge,id_credor,entidade,cargo,data_inicio,data_fim,destino,finalidade,quantidade,valor) FROM 'dados/tratados/diaria.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
\copy pagamento_extraorcamentario (id_pagamento_extra,ibge,conta,id_credor,data,valor,historico) FROM 'dados/tratados/pagamento_extraorcamentario.csv' WITH (FORMAT csv, HEADER MATCH, ENCODING 'UTF8')
COMMIT;
ANALYZE;
