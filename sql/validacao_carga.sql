-- Validação da carga do esquema origem (issue #8).
-- Uso: psql --dbname="$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/validacao_carga.sql
-- Somente leitura: nenhuma tabela é alterada.

SET search_path TO origem;

-- 1. Contagem de linhas por tabela contra os CSVs de dados/origem-validada.
--    O valor esperado é o número de registros de cada CSV, sem o cabeçalho.
\echo '== 1. Contagem de linhas =='
WITH esperado (tabela, linhas_csv) AS (
    VALUES
        ('exercicio', 4), ('orgao', 25), ('unidade', 121), ('funcao', 20),
        ('subfuncao', 52), ('recurso', 161), ('elemento', 318), ('credor', 4856),
        ('empenho', 62405), ('diaria', 11455), ('emenda', 40), ('dotacao', 1482),
        ('empenho_dotacao', 62527), ('fonte_dotacao', 2995), ('suplementacao', 5390)
),
carregado (tabela, linhas_banco) AS (
    SELECT 'exercicio', count(*) FROM exercicio
    UNION ALL SELECT 'orgao', count(*) FROM orgao
    UNION ALL SELECT 'unidade', count(*) FROM unidade
    UNION ALL SELECT 'funcao', count(*) FROM funcao
    UNION ALL SELECT 'subfuncao', count(*) FROM subfuncao
    UNION ALL SELECT 'recurso', count(*) FROM recurso
    UNION ALL SELECT 'elemento', count(*) FROM elemento
    UNION ALL SELECT 'credor', count(*) FROM credor
    UNION ALL SELECT 'empenho', count(*) FROM empenho
    UNION ALL SELECT 'diaria', count(*) FROM diaria
    UNION ALL SELECT 'emenda', count(*) FROM emenda
    UNION ALL SELECT 'dotacao', count(*) FROM dotacao
    UNION ALL SELECT 'empenho_dotacao', count(*) FROM empenho_dotacao
    UNION ALL SELECT 'fonte_dotacao', count(*) FROM fonte_dotacao
    UNION ALL SELECT 'suplementacao', count(*) FROM suplementacao
)
SELECT e.tabela, e.linhas_csv, c.linhas_banco,
       CASE WHEN e.linhas_csv = c.linhas_banco THEN 'OK' ELSE 'DIVERGENTE' END AS status
FROM esperado e
JOIN carregado c USING (tabela)
UNION ALL
SELECT 'TOTAL', sum(e.linhas_csv), sum(c.linhas_banco),
       CASE WHEN sum(e.linhas_csv) = sum(c.linhas_banco) THEN 'OK' ELSE 'DIVERGENTE' END
FROM esperado e
JOIN carregado c USING (tabela);

-- 2. Integridade referencial: registros cuja chave estrangeira não encontra o pai.
--    Uma chave com valor nulo não é verificada, como no PostgreSQL (MATCH SIMPLE).
--    As 25 chaves estrangeiras do DDL estão listadas abaixo.
\echo '== 2. Chaves órfãs (o esperado é 0 em todas) =='
WITH orfaos (chave, quantidade) AS (
    SELECT 'unidade.pai_id -> orgao', count(*) FROM unidade f
        WHERE NOT EXISTS (SELECT 1 FROM orgao p WHERE p.id = f.pai_id)
    UNION ALL SELECT 'subfuncao.pai_id -> funcao', count(*) FROM subfuncao f
        WHERE NOT EXISTS (SELECT 1 FROM funcao p WHERE p.id = f.pai_id)

    UNION ALL SELECT 'empenho.ano -> exercicio', count(*) FROM empenho f
        WHERE NOT EXISTS (SELECT 1 FROM exercicio p WHERE p.ano = f.ano)
    UNION ALL SELECT 'empenho.orgao_id -> orgao', count(*) FROM empenho f
        WHERE f.orgao_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM orgao p WHERE p.id = f.orgao_id)
    UNION ALL SELECT 'empenho.credor_id -> credor', count(*) FROM empenho f
        WHERE f.credor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM credor p WHERE p.id = f.credor_id)
    UNION ALL SELECT 'empenho.funcao_id -> funcao', count(*) FROM empenho f
        WHERE f.funcao_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM funcao p WHERE p.id = f.funcao_id)
    UNION ALL SELECT 'empenho.recurso_id -> recurso', count(*) FROM empenho f
        WHERE f.recurso_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM recurso p WHERE p.id = f.recurso_id)
    UNION ALL SELECT 'empenho.elemento_id -> elemento', count(*) FROM empenho f
        WHERE f.elemento_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM elemento p WHERE p.id = f.elemento_id)
    UNION ALL SELECT 'empenho.(unidade_id, orgao_id) -> unidade', count(*) FROM empenho f
        WHERE f.unidade_id IS NOT NULL AND f.orgao_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM unidade p WHERE p.id = f.unidade_id AND p.pai_id = f.orgao_id)
    UNION ALL SELECT 'empenho.(subfuncao_id, funcao_id) -> subfuncao', count(*) FROM empenho f
        WHERE f.subfuncao_id IS NOT NULL AND f.funcao_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM subfuncao p WHERE p.id = f.subfuncao_id AND p.pai_id = f.funcao_id)

    UNION ALL SELECT 'diaria.ano -> exercicio', count(*) FROM diaria f
        WHERE NOT EXISTS (SELECT 1 FROM exercicio p WHERE p.ano = f.ano)
    UNION ALL SELECT 'diaria.orgao_id -> orgao', count(*) FROM diaria f
        WHERE f.orgao_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM orgao p WHERE p.id = f.orgao_id)
    UNION ALL SELECT 'diaria.credor_id -> credor', count(*) FROM diaria f
        WHERE f.credor_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM credor p WHERE p.id = f.credor_id)
    UNION ALL SELECT 'diaria.(unidade_id, orgao_id) -> unidade', count(*) FROM diaria f
        WHERE f.unidade_id IS NOT NULL AND f.orgao_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM unidade p WHERE p.id = f.unidade_id AND p.pai_id = f.orgao_id)

    UNION ALL SELECT 'emenda.ano -> exercicio', count(*) FROM emenda f
        WHERE NOT EXISTS (SELECT 1 FROM exercicio p WHERE p.ano = f.ano)

    UNION ALL SELECT 'dotacao.ano -> exercicio', count(*) FROM dotacao f
        WHERE NOT EXISTS (SELECT 1 FROM exercicio p WHERE p.ano = f.ano)
    UNION ALL SELECT 'dotacao.orgao_id -> orgao', count(*) FROM dotacao f
        WHERE f.orgao_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM orgao p WHERE p.id = f.orgao_id)
    UNION ALL SELECT 'dotacao.funcao_id -> funcao', count(*) FROM dotacao f
        WHERE f.funcao_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM funcao p WHERE p.id = f.funcao_id)
    UNION ALL SELECT 'dotacao.elemento_id -> elemento', count(*) FROM dotacao f
        WHERE f.elemento_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM elemento p WHERE p.id = f.elemento_id)
    UNION ALL SELECT 'dotacao.(unidade_id, orgao_id) -> unidade', count(*) FROM dotacao f
        WHERE f.unidade_id IS NOT NULL AND f.orgao_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM unidade p WHERE p.id = f.unidade_id AND p.pai_id = f.orgao_id)
    UNION ALL SELECT 'dotacao.(subfuncao_id, funcao_id) -> subfuncao', count(*) FROM dotacao f
        WHERE f.subfuncao_id IS NOT NULL AND f.funcao_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM subfuncao p WHERE p.id = f.subfuncao_id AND p.pai_id = f.funcao_id)

    UNION ALL SELECT 'empenho_dotacao.(ano, dotacao_id) -> dotacao', count(*) FROM empenho_dotacao f
        WHERE NOT EXISTS (SELECT 1 FROM dotacao p WHERE p.ano = f.ano AND p.id_origem = f.dotacao_id)
    UNION ALL SELECT 'fonte_dotacao.recurso_id -> recurso', count(*) FROM fonte_dotacao f
        WHERE NOT EXISTS (SELECT 1 FROM recurso p WHERE p.id = f.recurso_id)
    UNION ALL SELECT 'fonte_dotacao.(ano, dotacao_id) -> dotacao', count(*) FROM fonte_dotacao f
        WHERE NOT EXISTS (SELECT 1 FROM dotacao p WHERE p.ano = f.ano AND p.id_origem = f.dotacao_id)
    UNION ALL SELECT 'suplementacao.(ano, dotacao_id) -> dotacao', count(*) FROM suplementacao f
        WHERE NOT EXISTS (SELECT 1 FROM dotacao p WHERE p.ano = f.ano AND p.id_origem = f.dotacao_id)
)
SELECT chave, quantidade, CASE WHEN quantidade = 0 THEN 'OK' ELSE 'ORFAOS' END AS status
FROM orfaos
UNION ALL
SELECT 'TOTAL (' || count(*) || ' chaves)', sum(quantidade),
       CASE WHEN sum(quantidade) = 0 THEN 'OK' ELSE 'ORFAOS' END
FROM orfaos;

-- 3. Restrições declaradas e validadas pelo PostgreSQL.
\echo '== 3. Restrições no catálogo =='
SELECT CASE contype WHEN 'p' THEN 'chave primária' WHEN 'f' THEN 'chave estrangeira'
                    WHEN 'u' THEN 'unicidade' WHEN 'c' THEN 'checagem' END AS tipo,
       count(*) AS quantidade,
       count(*) FILTER (WHERE NOT convalidated) AS nao_validadas
FROM pg_constraint
WHERE connamespace = 'origem'::regnamespace AND contype IN ('p', 'f', 'u', 'c')
GROUP BY contype
ORDER BY contype;

-- 4. Distribuição por exercício das tabelas de registros.
\echo '== 4. Linhas por exercício =='
SELECT tabela,
       count(*) FILTER (WHERE ano = 2023) AS "2023",
       count(*) FILTER (WHERE ano = 2024) AS "2024",
       count(*) FILTER (WHERE ano = 2025) AS "2025",
       count(*) FILTER (WHERE ano = 2026) AS "2026",
       count(*) AS total
FROM (
    SELECT 'empenho' AS tabela, ano FROM empenho
    UNION ALL SELECT 'diaria', ano FROM diaria
    UNION ALL SELECT 'emenda', ano FROM emenda
    UNION ALL SELECT 'dotacao', ano FROM dotacao
    UNION ALL SELECT 'empenho_dotacao', ano FROM empenho_dotacao
    UNION ALL SELECT 'fonte_dotacao', ano FROM fonte_dotacao
    UNION ALL SELECT 'suplementacao', ano FROM suplementacao
) registros
GROUP BY tabela
ORDER BY tabela;
