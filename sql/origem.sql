BEGIN;
CREATE SCHEMA IF NOT EXISTS origem;
SET LOCAL search_path TO origem;

CREATE TABLE IF NOT EXISTS exercicio (
    ano INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS orgao (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    UNIQUE (nome)
);

CREATE TABLE IF NOT EXISTS unidade (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    pai_id INTEGER NOT NULL REFERENCES orgao(id),
    UNIQUE (nome, pai_id),
    UNIQUE (id, pai_id)
);

CREATE TABLE IF NOT EXISTS funcao (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    UNIQUE (nome)
);

CREATE TABLE IF NOT EXISTS subfuncao (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    pai_id INTEGER NOT NULL REFERENCES funcao(id),
    UNIQUE (nome, pai_id),
    UNIQUE (id, pai_id)
);

CREATE TABLE IF NOT EXISTS recurso (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    UNIQUE (nome)
);

CREATE TABLE IF NOT EXISTS elemento (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    UNIQUE (nome)
);

CREATE TABLE IF NOT EXISTS credor (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    UNIQUE (nome)
);

CREATE TABLE IF NOT EXISTS empenho (
    ano INTEGER NOT NULL REFERENCES exercicio(ano),
    id_origem TEXT NOT NULL,
    data_empenho DATE NOT NULL,
    numero_empenho TEXT,
    orgao_id INTEGER REFERENCES orgao(id),
    unidade_id INTEGER,
    credor_id INTEGER REFERENCES credor(id),
    funcao_id INTEGER REFERENCES funcao(id),
    subfuncao_id INTEGER,
    recurso_id INTEGER REFERENCES recurso(id),
    elemento_id INTEGER REFERENCES elemento(id),
    historico TEXT,
    valor_empenhado NUMERIC(18,2),
    valor_liquidado NUMERIC(18,2),
    valor_pago NUMERIC(18,2),
    saldo_a_pagar NUMERIC(18,2),
    PRIMARY KEY (ano, id_origem),
    FOREIGN KEY (unidade_id, orgao_id) REFERENCES unidade(id, pai_id),
    FOREIGN KEY (subfuncao_id, funcao_id) REFERENCES subfuncao(id, pai_id)
);

CREATE TABLE IF NOT EXISTS diaria (
    ano INTEGER NOT NULL REFERENCES exercicio(ano),
    id_origem TEXT NOT NULL,
    data_empenho DATE NOT NULL,
    numero_empenho TEXT,
    orgao_id INTEGER REFERENCES orgao(id),
    unidade_id INTEGER,
    credor_id INTEGER REFERENCES credor(id),
    descricao_viagem TEXT,
    valor_pagamento NUMERIC(18,2),
    PRIMARY KEY (ano, id_origem),
    FOREIGN KEY (unidade_id, orgao_id) REFERENCES unidade(id, pai_id)
);

CREATE TABLE IF NOT EXISTS emenda (
    ano INTEGER NOT NULL REFERENCES exercicio(ano),
    id_origem TEXT NOT NULL,
    numero TEXT,
    origem TEXT,
    tipo TEXT,
    autoria TEXT,
    objeto TEXT,
    favorecido TEXT,
    cpf_cnpj TEXT CHECK (length(cpf_cnpj) IN (11, 14)),
    valor_previsto NUMERIC(18,2),
    valor_empenhado NUMERIC(18,2),
    valor_liquidado NUMERIC(18,2),
    valor_pago NUMERIC(18,2),
    PRIMARY KEY (ano, id_origem)
);
COMMIT;
