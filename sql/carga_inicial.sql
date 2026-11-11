\set ON_ERROR_STOP on
BEGIN;
\copy origem.exercicio FROM 'dados/origem-validada/exercicio.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.orgao FROM 'dados/origem-validada/orgao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.unidade FROM 'dados/origem-validada/unidade.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.funcao FROM 'dados/origem-validada/funcao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.subfuncao FROM 'dados/origem-validada/subfuncao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.recurso FROM 'dados/origem-validada/recurso.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.elemento FROM 'dados/origem-validada/elemento.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.credor FROM 'dados/origem-validada/credor.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.empenho FROM 'dados/origem-validada/empenho.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.diaria FROM 'dados/origem-validada/diaria.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.emenda FROM 'dados/origem-validada/emenda.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.dotacao FROM 'dados/origem-validada/dotacao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.empenho_dotacao FROM 'dados/origem-validada/empenho_dotacao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.fonte_dotacao FROM 'dados/origem-validada/fonte_dotacao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy origem.suplementacao FROM 'dados/origem-validada/suplementacao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
COMMIT;
