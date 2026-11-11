# Validação das premissas

Validação da coleta de 07/11/2026. O banco de teste gerado pelo script de limpeza contém **15 tabelas e 151.851 linhas**, com chaves primárias e estrangeiras conferidas localmente.

| Tabela | 2023 | 2024 | 2025 | 2026 parcial | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| `empenho` | 13.553 | 15.026 | 16.714 | 17.112 | 62.405 |
| `diaria` | 2.442 | 2.943 | 3.212 | 2.858 | 11.455 |
| `emenda` | 8 | 4 | 8 | 20 | 40 |
| `dotacao` | 332 | 331 | 414 | 405 | 1.482 |
| `empenho_dotacao` | 13.438 | 14.949 | 17.026 | 17.114 | 62.527 |
| `fonte_dotacao` | 652 | 668 | 872 | 803 | 2.995 |
| `suplementacao` | 1.051 | 1.052 | 1.710 | 1.577 | 5.390 |

| Dimensão compartilhada | Chaves distintas |
| --- | ---: |
| `exercicio` | 4 |
| `orgao` | 25 |
| `unidade` | 121 |
| `funcao` | 20 |
| `subfuncao` | 52 |
| `recurso` | 161 |
| `elemento` | 318 |
| `credor` | 4.856 |

As tabelas principais `empenho`, `diaria` e `empenho_dotacao` superam 10.000 linhas no período completo e têm datas em 2024, 2025 e 2026. Limitando a contagem aos três exercícios mais recentes, `diaria` tem 9.013 linhas. A cobertura de 2026 é parcial.

O total soma registros com granularidades diferentes. O detalhamento de empenhos por dotação pode incluir empenhos da listagem geral, por isso as duas fontes devem ser analisadas separadamente para calcular valores.

Foram removidos 35 registros repetidos de dotação e 522 detalhes repetidos. As três listagens com identificador do portal não tinham repetição de chave.

A carga e a validação no PostgreSQL do Supabase estão pendentes.
