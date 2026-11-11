"""Normaliza os CSVs selecionados e valida PKs/FKs antes de exportar."""

import argparse
import csv
from collections import Counter
from datetime import date
from decimal import Decimal
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
from zipfile import ZipFile

ANOS = range(2023, 2027)
FONTES = {
    "empenho": "174485-despesas-por-classificacao-orcamentaria-listagem.csv",
    "diaria": "90321-despesas-de-diarias-e-viagens-agrupadas-por-orgao-listagem.csv",
    "emenda": "333327-emendas-parlamentares-execucao-orcamentaria-e-financeira-listagem.csv",
}
DIMENSOES = ("orgao", "unidade", "funcao", "subfuncao", "recurso", "elemento", "credor")
TABELAS_REGISTROS = (*FONTES, "dotacao", "empenho_dotacao", "fonte_dotacao", "suplementacao")


def texto(valor):
    if valor is None:
        return None
    return " ".join(unicodedata.normalize("NFC", valor).split()) or None


def moeda(valor):
    valor = texto(valor)
    if valor is None:
        return None
    valor = valor.removeprefix("R$").strip()
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    numero = Decimal(valor)
    if not numero.is_finite() or numero != numero.quantize(Decimal("0.01")):
        raise ValueError("Valor monetário inválido para duas casas decimais")
    if abs(numero) >= Decimal("10000000000000000"):
        raise ValueError("Valor monetário excede numeric(18,2)")
    return format(numero, ".2f")


def documento(valor):
    valor = texto(valor)
    if valor is None or re.fullmatch(r"[.*/\s-]+", valor):
        return None
    digitos = re.sub(r"[./\s-]", "", valor)
    if not re.fullmatch(r"(?:[0-9]{11}|[0-9]{14})", digitos):
        return None
    return digitos


def dimensao(conexao, tabela, valores):
    if None in valores:
        return None
    colunas = ("nome", "pai_id") if len(valores) == 2 else ("nome",)
    filtro = " AND ".join(f"{coluna} = ?" for coluna in colunas)
    existente = conexao.execute(
        f"SELECT id FROM {tabela} WHERE {filtro}", valores
    ).fetchone()
    if existente:
        return existente[0]
    parametros = ", ".join("?" for _ in valores)
    cursor = conexao.execute(
        f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({parametros})", valores
    )
    return cursor.lastrowid


def transformar(conexao, tabela, ano, linha):
    identificador = texto(linha["_id"])
    if not identificador:
        raise ValueError("Identificador de origem ausente")
    if tabela == "emenda":
        return (
            ano, identificador, texto(linha["numero"]), texto(linha["origem"]),
            texto(linha["tipo"]), texto(linha["autoria"]), texto(linha["objeto"]),
            texto(linha["favorecido"]), documento(linha["cpfCnpjFavorecido"]),
            *(moeda(linha[campo]) for campo in ("valorPrevisto", "valorEmpenhado", "liquidado", "pago")),
        )

    data = date.fromisoformat(linha["dataEmpenho"])
    if data.year != ano:
        raise ValueError("Data de empenho fora do exercício da exportação")
    orgao = dimensao(conexao, "orgao", (texto(linha["descricaoOrgao"]),))
    unidade = dimensao(conexao, "unidade", (texto(linha["descricaoUnidade"]), orgao))
    nome_credor = linha["credor" if tabela == "diaria" else "credor.nomeCredor"]
    credor = dimensao(conexao, "credor", (texto(nome_credor),))
    base = (ano, identificador, data.isoformat(), texto(linha["numeroEmpenho"]), orgao, unidade, credor)
    if tabela == "diaria":
        return (*base, texto(linha["descricaoViagem"]), moeda(linha["valorPagamento"]))

    funcao = dimensao(conexao, "funcao", (texto(linha["descricaoFuncao"]),))
    subfuncao = dimensao(conexao, "subfuncao", (texto(linha["descricaoSubfuncao"]), funcao))
    recurso = dimensao(conexao, "recurso", (texto(linha["descricaoRecurso"]),))
    elemento = dimensao(conexao, "elemento", (texto(linha["mascaraElemento"]),))
    return (
        *base, funcao, subfuncao, recurso, elemento, texto(linha["historicoEmpenho"]),
        *(moeda(linha[campo]) for campo in (
            "valorEmpenho", "valorLiquidadoEmpenho", "valorPagoEmpenho", "saldoAPagar"
        )),
    )


def importar_dotacoes(conexao, arquivo, ano, removidas):
    nome = f"{ano}/34878-despesas-por-programas-e-acoes-exportacao-original.csv"
    secoes = {
        "Fontes de recursos": ("fonte_dotacao", "Descrição do recurso"),
        "Empenhos": ("empenho_dotacao", "Ano do empenho"),
        "Suplementações": ("suplementacao", "Data da suplementação"),
        "informacaoPlanejamento": (None, "Público alvo"),
    }
    vistos = set()
    itens = Counter()
    dotacao_id = None
    secao = None
    with arquivo.open(nome) as bruto:
        leitor = csv.reader(io.TextIOWrapper(bruto, encoding="utf-8-sig", newline=""))
        for linha in leitor:
            try:
                if not linha or linha == ["- - - - -"]:
                    continue
                if linha[0] == "Entidade":
                    secao = None
                    continue
                if len(linha) == 1:
                    secao = linha[0]
                    if secao not in secoes:
                        raise ValueError("Seção desconhecida")
                    continue
                if secao is None:
                    if len(linha) != 37 or int(linha[1]) != ano:
                        raise ValueError("Cabeçalho ou exercício de dotação inesperado")
                    normalizada = tuple(map(texto, linha))
                    # Mantém versões distintas mesmo se entidade e código coincidirem.
                    dotacao_id = sha256(json.dumps(normalizada).encode("ascii")).hexdigest()
                    chave = ("dotacao", dotacao_id)
                    if chave in vistos:
                        removidas["dotacao", ano] += 1
                        continue
                    vistos.add(chave)
                    orgao = dimensao(conexao, "orgao", (normalizada[5],))
                    unidade = dimensao(conexao, "unidade", (normalizada[6], orgao))
                    funcao = dimensao(conexao, "funcao", (normalizada[7],))
                    subfuncao = dimensao(conexao, "subfuncao", (normalizada[8], funcao))
                    elemento = dimensao(conexao, "elemento", (normalizada[13],))
                    inserir(conexao, "dotacao", (
                        ano, dotacao_id, normalizada[0], normalizada[12], normalizada[2],
                        normalizada[9], normalizada[10], normalizada[3], orgao, unidade,
                        funcao, subfuncao, normalizada[11], elemento, normalizada[15],
                        normalizada[16], moeda(linha[17]), moeda(linha[19]),
                    ))
                    continue

                tabela, cabecalho = secoes[secao]
                if tabela is None or linha[0] == cabecalho:
                    continue
                if dotacao_id is None:
                    raise ValueError("Detalhe sem dotação")
                if tabela == "fonte_dotacao":
                    recurso, tipo, finalidade, percentual = map(texto, linha)
                    valores = (dimensao(conexao, "recurso", (recurso,)), tipo, finalidade,
                               format(Decimal(percentual), "f") if percentual else None)
                elif tabela == "empenho_dotacao":
                    ano_empenho, numero, data, valor = linha
                    data = date.fromisoformat(data)
                    if data.year != int(ano_empenho):
                        raise ValueError("Data incompatível com o ano do empenho")
                    valores = (data.year, texto(numero), data.isoformat(), moeda(valor))
                else:
                    data, documento_origem, valor = linha
                    valores = (date.fromisoformat(data).isoformat(), texto(documento_origem), moeda(valor))

                chave = (tabela, dotacao_id, valores)
                if chave in vistos:
                    removidas[tabela, ano] += 1
                    continue
                vistos.add(chave)
                itens[tabela, dotacao_id] += 1
                inserir(conexao, tabela, (ano, dotacao_id, itens[tabela, dotacao_id], *valores))
            except (ArithmeticError, TypeError, ValueError, sqlite3.IntegrityError) as erro:
                raise ValueError(f"{nome}, linha {leitor.line_num}: {erro}") from erro


def inserir(conexao, tabela, valores):
    parametros = ", ".join("?" for _ in valores)
    conexao.execute(f"INSERT INTO {tabela} VALUES ({parametros})", valores)


def importar(conexao, caminho):
    removidas = Counter()
    with ZipFile(caminho) as arquivo, conexao:
        for ano in ANOS:
            conexao.execute("INSERT INTO exercicio VALUES (?)", (ano,))
            for tabela, nome in FONTES.items():
                membro = f"{ano}/{nome}"
                vistos = {}
                with arquivo.open(membro) as bruto:
                    leitor = csv.DictReader(io.TextIOWrapper(bruto, encoding="utf-8-sig", newline=""))
                    for linha in leitor:
                        try:
                            if None in linha or None in linha.values():
                                raise ValueError("Quantidade inesperada de campos")
                            valores = transformar(conexao, tabela, ano, linha)
                            chave = valores[1]
                            if chave in vistos:
                                if vistos[chave] != valores:
                                    raise ValueError("Registros divergentes com o mesmo ID")
                                removidas[tabela, ano] += 1
                                continue
                            vistos[chave] = valores
                            inserir(conexao, tabela, valores)
                        except (ArithmeticError, KeyError, ValueError, sqlite3.IntegrityError) as erro:
                            raise ValueError(f"{membro}, linha {leitor.line_num}: {erro}") from erro
            importar_dotacoes(conexao, arquivo, ano, removidas)
    return removidas


def exportar(conexao, pasta, removidas):
    tabelas = ("exercicio", *DIMENSOES, *TABELAS_REGISTROS)
    pasta.mkdir(parents=True, exist_ok=False)
    for tabela in tabelas:
        consulta = conexao.execute(f"SELECT * FROM {tabela} ORDER BY 1, 2" if tabela != "exercicio"
                                   else "SELECT ano FROM exercicio ORDER BY ano")
        with (pasta / f"{tabela}.csv").open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(coluna[0] for coluna in consulta.description)
            escritor.writerows(consulta)
        total = conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        print(f"{tabela}: {total}")
        if tabela in TABELAS_REGISTROS:
            for ano, contagem in conexao.execute(
                f"SELECT ano, COUNT(*) FROM {tabela} GROUP BY ano ORDER BY ano"
            ):
                print(f"  {ano}: {contagem} ({removidas[tabela, ano]} duplicados removidos)")
    with sqlite3.connect(pasta / "origem.sqlite3") as banco:
        conexao.backup(banco)
    print(f"Total: {len(tabelas)} tabelas, {sum(conexao.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in tabelas)} linhas")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("saida", type=Path, help="Diretório novo para os CSVs")
    args = parser.parse_args()
    ddl = Path(__file__).resolve().parents[1] / "sql" / "origem.sql"
    # Reusa as definições relacionais sem a instrução de schema do PostgreSQL.
    sql_local = ddl.read_text(encoding="utf-8").split("SET LOCAL search_path TO origem;", 1)[1]
    with sqlite3.connect(":memory:") as conexao:
        conexao.execute("PRAGMA foreign_keys = ON")
        # Mantém o Decimal serializado sem conversão para ponto flutuante no SQLite.
        conexao.executescript("BEGIN;" + sql_local.replace("NUMERIC(18,2)", "TEXT"))
        removidas = importar(conexao, args.zip)
        exportar(conexao, args.saida, removidas)


if __name__ == "__main__":
    main()
