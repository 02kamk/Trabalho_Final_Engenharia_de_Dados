# Validação

Resultado do tratamento (`notebooks/tratamento.ipynb`) e da carga no Neon (PostgreSQL 18.7) com `sql/carga.sql`, conferida por `sql/validacao.sql` em 17/11/2026. A mesma carga foi testada antes num PostgreSQL 18 local, com resultado idêntico. O banco tem **15 tabelas e 3.447.345 linhas** e ocupa 771 MB.

## Linhas por tabela

| Tabela | Linhas | 10 mil ou mais |
| --- | ---: | --- |
| `pagamento` | 575.084 | sim |
| `liquidacao` | 546.537 | sim |
| `empenho` | 458.797 | sim |
| `empenho_documento_fiscal` | 444.553 | sim |
| `item_empenho` | 422.161 | sim |
| `documento_fiscal` | 384.114 | sim |
| `retencao` | 275.193 | sim |
| `pagamento_extraorcamentario` | 153.235 | sim |
| `material` | 84.996 | sim |
| `anulacao_empenho` | 47.020 | sim |
| `credor` | 28.757 | sim |
| `diaria` | 26.808 | sim |
| `elemento_despesa` | 50 | não (domínio) |
| `funcao` | 28 | não (domínio) |
| `municipio` | 12 | não (domínio) |

**12 de 15 tabelas (80%) têm 10 mil linhas ou mais.** As três abaixo são tabelas de domínio, justificadas em [Modelo de dados](modelo.md).

## Empenhos por município e exercício

| Município | 2023 | 2024 | 2025 | 2026 | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Balneário Rincão | 6.677 | 6.637 | 8.872 | 7.523 | 29.709 |
| Cocal do Sul | 10.273 | 11.101 | 13.187 | 11.790 | 46.351 |
| Criciúma | 13.553 | 15.026 | 16.714 | 17.454 | 62.747 |
| Forquilhinha | 10.256 | 10.894 | 11.513 | 10.413 | 43.076 |
| Içara | 13.529 | 14.210 | 16.092 | 15.330 | 59.161 |
| Lauro Müller | 6.966 | 8.065 | 9.118 | 7.247 | 31.396 |
| Morro da Fumaça | 10.903 | 11.337 | 11.333 | 9.431 | 43.004 |
| Nova Veneza | 3.158 | 3.360 | 4.421 | 3.965 | 14.904 |
| Orleans | 10.479 | 9.110 | 9.757 | 9.681 | 39.027 |
| Siderópolis | 6.945 | 6.290 | 6.759 | 6.006 | 26.000 |
| Treviso | 6.753 | 6.950 | 7.154 | 6.755 | 27.612 |
| Urussanga | 9.901 | 9.516 | 11.866 | 4.527 | 35.810 |

O exercício de 2026 é parcial (coleta em novembro). Urussanga tem menos empenhos em 2026 que nos anos anteriores.

## Conferências do tratamento

O notebook só exporta os CSVs se todas passarem:

- chaves primárias sem nulos e sem repetição, nas 15 tabelas;
- chaves únicas sem repetição (`credor`, `material`, `documento_fiscal`, `empenho`, `municipio`, `funcao`);
- nenhuma das 18 chaves estrangeiras com registro órfão;
- toda retenção ligada a exatamente uma liquidação ou um empenho;
- todo empenho com data de emissão dentro do próprio exercício;
- tipos de empenho e de anulação dentro dos valores permitidos, e exercício entre 2023 e 2026;
- documento do credor com 11 ou 14 posições e nenhum CPF completo;
- pelo menos 80% das tabelas com 10 mil linhas ou mais.

## Conferências no banco

- As 15 tabelas carregaram com o mesmo número de linhas dos CSVs.
- 15 chaves primárias, 18 chaves estrangeiras, 5 restrições de unicidade, 6 checagens e 70 restrições de não nulo foram criadas e validadas pelo PostgreSQL.
- As 15 tabelas têm a coluna `atualizado_em` e o gatilho que a renova; testado alterando um registro e conferindo a nova data.
- Nenhum CPF completo na tabela `credor`.

## Registros descartados ou ajustados

| Situação | Quantidade | Tratamento |
| --- | ---: | --- |
| Registros baixados e depois retirados do portal | 4 | descartados (3 empenhos, 1 diária) |
| Restos a pagar que Urussanga e Içara listam de novo em cada exercício (ano do empenho diferente do exercício, valores do exercício zerados) | 1.465 empenhos (943 de Urussanga, 522 de Içara), com 1.440 pagamentos de valor zero, 313 retenções e 543 vínculos com notas | descartados com tudo o que está ligado a eles; os de 2023 em diante já estão na base pelo ano de emissão |
| Liquidações publicadas duas vezes no mesmo empenho, com conteúdo idêntico | 7 | entra uma vez |
| Liquidações e pagamentos do Atende.net de empenhos anteriores a 2023 | 500 | descartados (170 liquidações, 330 pagamentos) |
| Retenções de Içara e Urussanga repetidas no pagamento | 23.872 | descartadas, porque já estão na liquidação (das 24.182 publicadas no pagamento, 310 não tinham par e entraram) |
| Documentos fiscais com a mesma identificação e chave de acesso diferente | 142 | vale a primeira chave |
| Empenhos do Atende.net sem elemento deduzível | 1.443 (2% do valor) | elemento nulo |
| Empenhos do Betha publicados sem nome nem documento do credor | 1.118 | credor nulo |
| Pagamentos do Atende.net com valor zero no próprio CSV exportado | 455 (241 de Treviso, 214 de Morro da Fumaça) | mantidos como a fonte publica; não alteram nenhuma soma |
