# Fontes e limpeza

A entrada é o ZIP `despesas-criciuma-2023-a-2026.zip`, coletado em 07/11/2026 no [Portal da Transparência de Criciúma](https://transparencia.criciuma.sc.gov.br/#despesas). O inventário da coleta registrava 15 relatórios escolhidos e três descartados.

| Consulta usada | Tabela |
| --- | --- |
| 174485 — Despesas por classificação orçamentária | `empenho` |
| 90321 — Despesas de diárias e viagens agrupadas por órgão | `diaria` |
| 333327 — Emendas parlamentares | `emenda` |
| 34878 — Despesas por programas e ações | `dotacao`, `empenho_dotacao`, `fonte_dotacao`, `suplementacao` |

As consultas 34845 e 88579 são visões de execução com menos campos de classificação. A consulta de diárias por cargo 175444 cobre o mesmo tema com outras colunas. Somar essas visões ou combinar os níveis dos arquivos de agrupamentos pode contar despesas mais de uma vez. O leia-me do ZIP registra listagens por credor e de Diárias sem validação.

A exportação 34878 contém blocos de dotação seguidos por seções de fontes de recurso, empenhos e suplementações. O script descarta cabeçalhos, separadores e texto de planejamento. Cada seção carregada vira uma tabela filha. A chave da dotação é o exercício e um hash do registro normalizado, pois entidade e código de despesa podem se repetir com conteúdo distinto. Cada detalhe fica ligado à sua dotação e recebe um número de item. Repetições de conteúdo dentro da mesma dotação são removidas.

`empenho_dotacao` preserva o detalhamento por dotação. Pode haver sobreposição com o empenho geral da consulta 174485, sem ID compartilhado entre as exportações. Para medir a execução geral, consulte `empenho`. Para analisar os vínculos por dotação, consulte `empenho_dotacao`. Somar as duas tabelas pode contar a mesma despesa mais de uma vez.

| Relatório descartado no inventário | Motivo registrado |
| --- | --- |
| Informações sobre diárias e adiantamentos de viagem | Conteúdo informativo e decretos, sem registros de despesas |
| Empenhos a pagar por ordem cronológica | Data de posição dificulta uma série comparável por exercício |
| Empenhos pagos por ordem cronológica | Filtros dificultaram a extração no tempo disponível |

Os três descartes foram mantidos mesmo com arquivos correspondentes no ZIP.

## Executar

Na raiz, com Python 3.9 ou superior, indique o ZIP e um diretório de saída novo.

```powershell
python src/limpar.py "C:\caminho\despesas-criciuma-2023-a-2026.zip" dados/origem-validada
```

- Datas de empenho são interpretadas como datas ISO e conferidas contra o exercício. Emendas têm apenas exercício.
- Valores monetários são tratados com Decimal e exportados com duas casas. Campos vazios viram nulos e zeros são preservados.
- Textos usam Unicode NFC e espaços uniformes. Identificadores são preservados como texto.
- CPF/CNPJ das emendas fica com 11 ou 14 dígitos. Máscaras incompletas ou formatos inválidos viram nulo. A regra preserva zeros iniciais.
- Registros repetidos com o mesmo exercício, ID e conteúdo normalizado são deduplicados dentro de cada relatório. Divergências com a mesma chave interrompem o processamento.
- Dimensões são identificadas pelas descrições disponíveis. Unidade e subfunção incluem o identificador da dimensão pai. Homônimos podem compartilhar dimensão quando a fonte só oferece o nome.
- O script verifica PKs e FKs em SQLite antes de exportar os CSVs, gravar o banco local `origem.sqlite3` e imprimir as contagens.
