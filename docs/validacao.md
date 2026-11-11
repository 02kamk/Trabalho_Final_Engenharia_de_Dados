# Validação das premissas

Validação executada sobre a coleta de 07/11/2026, após normalização.

| Tabela de registros | 2023 | 2024 | 2025 | 2026 parcial | Total | Total 2024–2026 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `empenho` | 13.553 | 15.026 | 16.714 | 17.112 | 62.405 | 48.852 |
| `diaria` | 2.442 | 2.943 | 3.212 | 2.858 | 11.455 | 9.013 |
| `emenda` | 8 | 4 | 8 | 20 | 40 | 32 |

| Dimensão compartilhada | Chaves distintas |
| --- | ---: |
| `exercicio` | 4 |
| `orgao` | 25 |
| `unidade` | 115 |
| `funcao` | 19 |
| `subfuncao` | 49 |
| `recurso` | 147 |
| `elemento` | 296 |
| `credor` | 4.856 |

- **Mínimo de 10 tabelas.** Atendido com 11 tabelas.
- **Mínimo de 10.000 linhas por tabela principal.** Empenhos e diárias atingem o mínimo no recorte completo. Emendas é complementar. Se o mínimo for exigido exclusivamente em 2024–2026, faltam 987 linhas na tabela de diárias.
- **Datas nos últimos três anos.** Empenhos e diárias têm datas validadas em cada exercício de 2024 a 2026. A coleta também contém 2023. Emendas permite validar apenas o exercício.
- **Duplicatas.** Nenhuma repetição de chave nas três listagens selecionadas.
