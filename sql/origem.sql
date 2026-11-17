-- Banco de origem: despesas dos 12 municípios da AMREC, 2023 a 2026.
-- Modelo descrito em docs/modelo.md. Recria o esquema do zero: todo o conteúdo anterior é apagado.
-- Uso: psql --dbname="$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/origem.sql

BEGIN;

DROP SCHEMA IF EXISTS origem CASCADE;
CREATE SCHEMA origem;
SET search_path TO origem;

-- Domínio

CREATE TABLE municipio (
    ibge        char(7)     PRIMARY KEY,
    nome        varchar     NOT NULL UNIQUE,
    fonte       varchar     NOT NULL CHECK (fonte IN ('Betha', 'Atende.net')),
    data_coleta date        NOT NULL
);

CREATE TABLE funcao (
    codigo      smallint    PRIMARY KEY,
    nome        varchar     NOT NULL UNIQUE
);

CREATE TABLE elemento_despesa (
    codigo      char(2)     PRIMARY KEY,
    nome        varchar     NOT NULL
);

-- Cadastros

CREATE TABLE credor (
    id_credor   integer     PRIMARY KEY,
    documento   varchar(14) CHECK (documento ~ '^[0-9*]{11}([0-9*]{3})?$'),
    nome        varchar     NOT NULL,
    CONSTRAINT credor_identificacao UNIQUE NULLS NOT DISTINCT (documento, nome)
);

CREATE TABLE material (
    id_material    integer  PRIMARY KEY,
    descricao      varchar  NOT NULL,
    unidade_medida varchar  NOT NULL
);
-- Algumas descrições passam do limite de tamanho de um índice comum; a unicidade é garantida pelo hash.
CREATE UNIQUE INDEX material_identificacao ON material (md5(descricao), unidade_medida);

CREATE TABLE documento_fiscal (
    id_documento bigint        PRIMARY KEY,
    id_emitente  integer       REFERENCES credor,
    tipo         varchar       NOT NULL,
    numero       varchar       NOT NULL,
    data_emissao date,
    chave_acesso varchar(60),
    CONSTRAINT documento_identificacao UNIQUE NULLS NOT DISTINCT (id_emitente, tipo, numero, data_emissao)
);

-- Execução da despesa

CREATE TABLE empenho (
    id_empenho        bigint        PRIMARY KEY,
    ibge              char(7)       NOT NULL REFERENCES municipio,
    id_origem         varchar       NOT NULL,
    entidade          varchar       NOT NULL,
    numero            integer       NOT NULL,
    ano               smallint      NOT NULL CHECK (ano BETWEEN 2023 AND 2026),
    data_emissao      date          NOT NULL,
    tipo              varchar       CHECK (tipo IN ('Ordinário', 'Estimativo', 'Global')),
    id_credor         integer       REFERENCES credor,
    codigo_elemento   char(2)       REFERENCES elemento_despesa,
    elemento_inferido boolean       NOT NULL,
    codigo_funcao     smallint      REFERENCES funcao,
    historico         text,
    valor             numeric(15,2) NOT NULL,
    CONSTRAINT empenho_origem UNIQUE (ibge, id_origem)
);

CREATE TABLE item_empenho (
    id_empenho     bigint        REFERENCES empenho,
    sequencia      smallint,
    id_material    integer       NOT NULL REFERENCES material,
    quantidade     numeric(18,4),
    valor_unitario numeric(18,4),
    valor_total    numeric(15,2),
    PRIMARY KEY (id_empenho, sequencia)
);

CREATE TABLE empenho_documento_fiscal (
    id_empenho   bigint        REFERENCES empenho,
    id_documento bigint        REFERENCES documento_fiscal,
    valor        numeric(15,2) NOT NULL,
    PRIMARY KEY (id_empenho, id_documento)
);

CREATE TABLE anulacao_empenho (
    id_empenho bigint        REFERENCES empenho,
    sequencia  smallint,
    data       date          NOT NULL,
    tipo       varchar       CHECK (tipo IN ('Parcial', 'Total')),
    motivo     text,
    valor      numeric(15,2) NOT NULL,
    PRIMARY KEY (id_empenho, sequencia)
);

CREATE TABLE liquidacao (
    id_liquidacao bigint        PRIMARY KEY,
    id_empenho    bigint        NOT NULL REFERENCES empenho,
    numero        varchar       NOT NULL,
    data          date          NOT NULL,
    valor         numeric(15,2) NOT NULL,
    valor_anulado numeric(15,2)
);

CREATE TABLE retencao (
    id_retencao   bigint        PRIMARY KEY,
    id_liquidacao bigint        REFERENCES liquidacao,
    id_empenho    bigint        REFERENCES empenho,
    data          date          NOT NULL,
    valor         numeric(15,2) NOT NULL,
    CONSTRAINT retencao_uma_ligacao CHECK (num_nonnulls(id_liquidacao, id_empenho) = 1)
);

CREATE TABLE pagamento (
    id_pagamento  bigint        PRIMARY KEY,
    id_empenho    bigint        NOT NULL REFERENCES empenho,
    numero_ordem  varchar,
    data          date          NOT NULL,
    valor         numeric(15,2) NOT NULL,
    valor_anulado numeric(15,2),
    historico     text
);

-- Outras despesas

CREATE TABLE diaria (
    id_diaria   bigint        PRIMARY KEY,
    ibge        char(7)       NOT NULL REFERENCES municipio,
    id_credor   integer       REFERENCES credor,
    entidade    varchar       NOT NULL,
    cargo       varchar,
    data_inicio date,
    data_fim    date,
    destino     varchar,
    finalidade  text,
    quantidade  numeric(8,2),
    valor       numeric(15,2) NOT NULL
);

CREATE TABLE pagamento_extraorcamentario (
    id_pagamento_extra bigint        PRIMARY KEY,
    ibge               char(7)       NOT NULL REFERENCES municipio,
    conta              varchar,
    id_credor          integer       REFERENCES credor,
    data               date          NOT NULL,
    valor              numeric(15,2) NOT NULL,
    historico          text
);

-- Índices nas chaves estrangeiras mais usadas em junções (o PostgreSQL não os cria sozinho)

CREATE INDEX ON empenho (id_credor);
CREATE INDEX ON empenho (codigo_elemento);
CREATE INDEX ON item_empenho (id_material);
CREATE INDEX ON empenho_documento_fiscal (id_documento);
CREATE INDEX ON liquidacao (id_empenho);
CREATE INDEX ON retencao (id_liquidacao);
CREATE INDEX ON retencao (id_empenho);
CREATE INDEX ON pagamento (id_empenho);

-- Controle de alteração para a ingestão incremental: toda tabela ganha atualizado_em, preenchido na
-- inserção e renovado por gatilho a cada UPDATE. A ingestão extrai só o que mudou desde a última execução.

CREATE FUNCTION marcar_atualizacao() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.atualizado_em := now();
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    tabela text;
BEGIN
    FOR tabela IN SELECT tablename FROM pg_tables WHERE schemaname = 'origem' LOOP
        EXECUTE format('ALTER TABLE origem.%I ADD COLUMN atualizado_em timestamptz NOT NULL DEFAULT now()', tabela);
        EXECUTE format('CREATE INDEX ON origem.%I (atualizado_em)', tabela);
        EXECUTE format('CREATE TRIGGER marcar_atualizacao BEFORE UPDATE ON origem.%I
                        FOR EACH ROW EXECUTE FUNCTION origem.marcar_atualizacao()', tabela);
    END LOOP;
END;
$$;

COMMIT;
