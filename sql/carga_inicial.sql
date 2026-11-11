\set ON_ERROR_STOP on
BEGIN;
\copy origem.exercicio FROM 'dados/normalizados/exercicio.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.orgao FROM 'dados/normalizados/orgao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.unidade FROM 'dados/normalizados/unidade.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.funcao FROM 'dados/normalizados/funcao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.subfuncao FROM 'dados/normalizados/subfuncao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.recurso FROM 'dados/normalizados/recurso.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.elemento FROM 'dados/normalizados/elemento.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.credor FROM 'dados/normalizados/credor.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.empenho FROM 'dados/normalizados/empenho.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.diaria FROM 'dados/normalizados/diaria.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.emenda FROM 'dados/normalizados/emenda.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
COMMIT;
