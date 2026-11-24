"""Gera databricks/referencia/elemento_grupo.csv: o grupo de natureza de despesa de cada elemento.

A base de origem guarda só o elemento (2 dígitos). O grupo (1 = Pessoal, 3 = Outras despesas correntes,
4 = Investimentos...) está no segundo dígito do `mascaraElemento` do Betha, que o tratamento descartou.
Este script lê os brutos do Betha, aplica os mesmos filtros do tratamento e calcula, para cada elemento,
o grupo predominante e quanto dos empenhos (e do valor) ele cobre. A Gold usa esse grupo para todos os
empenhos do elemento, inclusive os do Atende.net.

Uso, na raiz do repositório e com os brutos em dados/brutos/amrec/:
    python scripts/elemento_grupo.py
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRUTOS = RAIZ / "dados" / "brutos" / "amrec"
SAIDA = RAIZ / "databricks" / "referencia" / "elemento_grupo.csv"
LIMITE = 0.95  # mesma regra usada no tratamento para inferir o elemento do Atende.net


def ler_betha(consulta):
    """Mesma leitura do notebooks/tratamento.ipynb: só os registros ainda publicados no portal."""
    for arquivo in sorted(BRUTOS.glob(f"*/{consulta}.jsonl")):
        publicados = {
            i for ids in json.loads(arquivo.with_name(f"{consulta}_ids.json").read_text()).values() for i in ids
        }
        with arquivo.open(encoding="utf-8") as f:
            for linha in f:
                registro = json.loads(linha)
                if registro["_id"] in publicados:
                    yield registro


empenhos = defaultdict(Counter)
valores = defaultdict(Counter)
for r in ler_betha("execucao_detalhada"):
    if r["dataEmpenho"][:4] != str(r["anoExercicio"]):
        continue  # restos a pagar listados de novo: ficam fora, como no tratamento
    mascara = r["mascaraElemento"]
    elemento, grupo = mascara[4:6], mascara[1]
    empenhos[elemento][grupo] += 1
    valores[elemento][grupo] += float(r["valorEmpenho"] or 0)

if not empenhos:
    raise SystemExit(f"Nenhum empenho encontrado em {BRUTOS}. Rode antes o notebooks/coleta.ipynb.")

linhas = []
for elemento in sorted(empenhos):
    # O grupo escolhido é o que concentra mais valor, porque os KPIs são em reais.
    total_valor = sum(valores[elemento].values())
    grupo = valores[elemento].most_common(1)[0][0] if total_valor else empenhos[elemento].most_common(1)[0][0]
    qtd = empenhos[elemento][grupo]
    pct_empenhos = qtd / empenhos[elemento].total()
    pct_valor = valores[elemento][grupo] / total_valor if total_valor else 1.0
    linhas.append({
        "codigo_elemento": elemento,
        "grupo": grupo,
        "empenhos": empenhos[elemento].total(),
        "pct_empenhos_no_grupo": round(pct_empenhos * 100, 1),
        "pct_valor_no_grupo": round(pct_valor * 100, 1),
        "ambiguo": pct_empenhos < LIMITE or pct_valor < LIMITE,
        "distribuicao": " ".join(f"{g}:{n}" for g, n in empenhos[elemento].most_common()),
    })

SAIDA.parent.mkdir(parents=True, exist_ok=True)
with SAIDA.open("w", newline="", encoding="utf-8") as f:
    escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
    escritor.writeheader()
    escritor.writerows(linhas)

print(f"{len(linhas)} elementos gravados em {SAIDA.relative_to(RAIZ)}")
ambiguos = [l for l in linhas if l["ambiguo"]]
print(f"{len(ambiguos)} elemento(s) abaixo de {LIMITE:.0%} em um único grupo:")
for l in ambiguos:
    print(f"  {l['codigo_elemento']}: {l['distribuicao']}  "
          f"({l['pct_empenhos_no_grupo']}% dos empenhos, {l['pct_valor_no_grupo']}% do valor no grupo {l['grupo']})")
