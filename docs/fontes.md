# Fontes e limpeza

A entrada é o ZIP `despesas-criciuma-2023-a-2026.zip`, coletado em 07/11/2026 no [Portal da Transparência de Criciúma](https://transparencia.criciuma.sc.gov.br/#despesas). O inventário da coleta registrava 15 relatórios escolhidos e três descartados.

| Consulta usada | Tabela |
| --- | --- |
| 174485 — Despesas por classificação orçamentária | `empenho` |
| 90321 — Despesas de diárias e viagens agrupadas por órgão | `diaria` |
| 333327 — Emendas parlamentares | `emenda` |

O modelo desta etapa usa as listagens acima. As consultas 34845 e 88579 são visões de execução com menos campos de classificação. A consulta de diárias por cargo 175444 cobre o mesmo tema com outras colunas. Somar essas visões ou combinar os níveis dos arquivos de agrupamentos pode contar despesas mais de uma vez. O leia-me do ZIP registra listagens por credor e de Diárias sem validação.

| Relatório descartado no inventário | Motivo registrado |
| --- | --- |
| Informações sobre diárias e adiantamentos de viagem | Conteúdo informativo e decretos, sem registros de despesas |
| Empenhos a pagar por ordem cronológica | Data de posição dificulta uma série comparável por exercício |
| Empenhos pagos por ordem cronológica | Filtros dificultaram a extração no tempo disponível |

Os três descartes foram mantidos mesmo com arquivos correspondentes no ZIP.

## Executar

Na raiz, com Python 3.9 ou superior, indique o ZIP e um diretório de saída novo.

```powershell
python src/limpar.py "C:\caminho\despesas-criciuma-2023-a-2026.zip" dados/normalizados
```

- Datas de empenho são interpretadas como datas ISO e conferidas contra o exercício. Emendas têm apenas exercício.
- Valores monetários são tratados com Decimal e exportados com duas casas. Campos vazios viram nulos e zeros são preservados.
- Textos usam Unicode NFC e espaços uniformes. Identificadores são preservados como texto.
- CPF/CNPJ das emendas fica com 11 ou 14 dígitos. Máscaras incompletas ou formatos inválidos viram nulo. A regra preserva zeros iniciais.
- Registros repetidos com o mesmo exercício, ID e conteúdo normalizado são deduplicados dentro de cada relatório. Divergências com a mesma chave interrompem o processamento.
- Dimensões são identificadas pelas descrições disponíveis. Unidade e subfunção incluem o identificador da dimensão pai. Homônimos podem compartilhar dimensão quando a fonte só oferece o nome.
- O script verifica PKs e FKs em SQLite antes de exportar os CSVs e imprimir as contagens.
