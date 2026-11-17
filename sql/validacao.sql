-- Conferência do banco depois da carga. Só faz leitura.
-- Uso: psql --dbname="$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/validacao.sql

SET search_path TO origem;

\echo '1. Linhas por tabela e critério de 10 mil linhas'
WITH contagem AS (
    SELECT 'municipio' AS tabela, count(*) AS linhas FROM municipio
    UNION ALL SELECT 'funcao', count(*) FROM funcao
    UNION ALL SELECT 'elemento_despesa', count(*) FROM elemento_despesa
    UNION ALL SELECT 'credor', count(*) FROM credor
    UNION ALL SELECT 'material', count(*) FROM material
    UNION ALL SELECT 'documento_fiscal', count(*) FROM documento_fiscal
    UNION ALL SELECT 'empenho', count(*) FROM empenho
    UNION ALL SELECT 'item_empenho', count(*) FROM item_empenho
    UNION ALL SELECT 'empenho_documento_fiscal', count(*) FROM empenho_documento_fiscal
    UNION ALL SELECT 'anulacao_empenho', count(*) FROM anulacao_empenho
    UNION ALL SELECT 'liquidacao', count(*) FROM liquidacao
    UNION ALL SELECT 'retencao', count(*) FROM retencao
    UNION ALL SELECT 'pagamento', count(*) FROM pagamento
    UNION ALL SELECT 'diaria', count(*) FROM diaria
    UNION ALL SELECT 'pagamento_extraorcamentario', count(*) FROM pagamento_extraorcamentario
)
SELECT tabela, linhas, acima_de_10_mil
FROM (
    SELECT 1 AS ordem, tabela, linhas, CASE WHEN linhas >= 10000 THEN 'sim' ELSE 'não' END AS acima_de_10_mil
    FROM contagem
    UNION ALL
    SELECT 2, 'TOTAL: tabelas acima de 10 mil', count(*) FILTER (WHERE linhas >= 10000),
           round(100.0 * count(*) FILTER (WHERE linhas >= 10000) / count(*)) || '%'
    FROM contagem
) resultado
ORDER BY ordem, linhas DESC;

\echo '2. Restrições no catálogo (todas devem estar validadas)'
SELECT CASE contype WHEN 'p' THEN 'chave primária' WHEN 'f' THEN 'chave estrangeira'
                    WHEN 'u' THEN 'unicidade' WHEN 'c' THEN 'checagem' WHEN 'n' THEN 'não nulo' END AS tipo,
       count(*) AS quantidade,
       count(*) FILTER (WHERE NOT convalidated) AS nao_validadas
FROM pg_constraint
WHERE connamespace = 'origem'::regnamespace
GROUP BY contype
ORDER BY 1;

\echo '3. Empenhos por município e exercício'
SELECT m.nome AS municipio,
       count(*) FILTER (WHERE e.ano = 2023) AS "2023",
       count(*) FILTER (WHERE e.ano = 2024) AS "2024",
       count(*) FILTER (WHERE e.ano = 2025) AS "2025",
       count(*) FILTER (WHERE e.ano = 2026) AS "2026",
       count(*) AS total
FROM empenho e JOIN municipio m USING (ibge)
GROUP BY m.nome
ORDER BY m.nome;

\echo '4. Proteção de dados: CPF completo gravado (esperado 0)'
SELECT count(*) AS cpf_completo FROM credor WHERE documento ~ '^[0-9]{11}$';

\echo '5. Tamanho do esquema'
SELECT pg_size_pretty(sum(pg_total_relation_size(c.oid))) AS tamanho
FROM pg_class c
WHERE c.relnamespace = 'origem'::regnamespace AND c.relkind = 'r';
