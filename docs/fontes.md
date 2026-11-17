# Fontes e inventário

Inventário dos arquivos brutos da coleta da AMREC (12 municípios, 2023 a 2026), feita em 16 e 17/11/2026. Como os arquivos foram obtidos, e os problemas encontrados no caminho, estão em [Coleta da AMREC](coleta-amrec.md).

Os arquivos ficam em `dados/brutos/amrec/<ibge>_<município>/`, fora do Git, porque contêm CPF e CNPJ de credores.

## Consultas usadas

| Fonte | Consulta | Arquivo | Uso no modelo |
| --- | --- | --- | --- |
| Betha | Execução detalhada de despesas | `execucao_detalhada.jsonl` | empenho, item, material, documento fiscal, anulação, liquidação, retenção, pagamento, credor, elemento, função |
| Betha | Diárias | `diarias.jsonl` | diária, credor |
| Betha | Receitas e despesas extraorçamentárias | `extraorcamentarias.jsonl` | pagamento extraorçamentário, credor |
| Betha | Despesas orçamentárias | `despesas_orcamentarias.jsonl` | não entra no modelo (dotação removida); usada só para conferência |
| Atende.net | Empenhos | `empenho_emitido_<ano>.csv` | empenho, credor, elemento |
| Atende.net | Liquidações | `liquidacao_<ano>.csv` | liquidação |
| Atende.net | Pagamentos | `pagamentos_<ano>.csv` | pagamento e retenção (tipo "Retenção") |
| Atende.net | Diárias | `diarias_<ano>.csv` | diária |
| Atende.net | Orçamento da despesa | `orcamento_despesa_<ano>.csv` | não entra no modelo; usada só para conferir os anos dos arquivos |

## Consultas descartadas

| Consulta | Motivo |
| --- | --- |
| Diárias e Viagens – Cargo (Betha) | Repete a consulta de diárias: 11.277 de 11.416 registros em Criciúma |
| Despesas com pessoal (Betha) | Subconjunto da execução detalhada: 9.713 de 9.715 empenhos |
| Movimentos extraorçamentários (Betha) | São as retenções vistas pelo lado contábil: 62.510 de 62.513 apontam para uma liquidação |
| Emendas parlamentares (Betha) | 40 registros em Criciúma; não há volume nem paralelo no Atende.net |
| Ordens de Compra (Atende.net) | Página publicada vazia |

## Betha

Um registro por linha, com os campos do portal mais `_id` (ID do registro no portal), `_ano` (exercício), `_ibge` (código do município, texto) e `_consulta` (ID da consulta no portal). Há uma pasta por município e quatro arquivos por pasta, com o `manifesto.json` da coleta.

### Execução detalhada de despesas

389.612 empenhos. Granularidade: um registro por empenho, com as fases da despesa em listas internas.

- **Campos do empenho:**
  - identificação: `numeroEmpenho`, `anoExercicio`, `dataEmpenho`, `nomeEntidade`, `tipoEmpenho`, `categoriaEmpenho`;
  - valores: `valorEmpenhado`, `valorLiquidadoEmpenho`, `valorPagoEmpenho`, saldos e restos a pagar;
  - classificação: `descricaoOrgao`, `descricaoUnidade`, `descricaoFuncao`, `descricaoSubfuncao`, `descricaoPrograma`, `descricaoProjetoAtividade`, `mascaraElemento`, `descricaoElemento`, `descricaoRecurso`;
  - credor: `credor` (nome, CPF/CNPJ, natureza jurídica);
  - outros: `historicoEmpenho`, `licitacao`, `contrato`, `convenio`, `dotacaoOrcamentaria`.
- **Chave candidata:** (município, `_id`). O número do empenho não serve: dentro do mesmo município, entidade e ano, ele se repete 15.880 vezes em empenhos diferentes. Em Urussanga, a numeração recomeça por categoria de empenho.

| Lista interna | Registros | Campos | Chave candidata |
| --- | ---: | --- | --- |
| `itens` | 422.141 | descrição, unidade, quantidade, valor unitário, valor total | (empenho, posição) |
| `documentosFiscais` | ~441 mil vínculos, 364.868 documentos distintos | emitente, tipo, número, data, valor, chave de autenticação | documento: (CPF/CNPJ do emitente, tipo, número) |
| `anulacoes` | 47.020 | data, tipo, motivo, valor | (empenho, posição) |
| `liquidacoes` | 452.133 | `idLiquidacao`, data, valor, anulações, retenções | (empenho, `idLiquidacao`) |
| `liquidacoes.retencoesLiquidacao` | 251.431 | ano, data, valor retido | (liquidação, posição) |
| `pagamentos` | 482.142 | data, valor, tipo, banco, histórico, parcela | (empenho, posição) |
| `pagamentos.retencoesPagamento` | 24.182 | ano, data, valor retido | só Içara e Urussanga; repetem as da liquidação |

Particularidades:

- Içara e Urussanga também têm `parcelas`, `liquidacoes.parcela` e `pagamentos.idLiquidacao`. Os demais municípios não têm esses campos.
- 7 liquidações aparecem duas vezes no mesmo empenho com conteúdo idêntico. Outras 12 repetem o `idLiquidacao` com data ou valor diferente e são parcelas distintas.
- Em 1.465 empenhos, o ano da data do empenho é diferente do exercício. Isso precisa ser conferido no tratamento.

### Diárias

21.684 registros, em 9 municípios (Urussanga não publica). Granularidade: uma diária, ou seja, um deslocamento.

- **Campos:**
  - credor: `credor`, `cnpjCpfCredor`, `cargoCredor`, `matriculaCredor`;
  - identificação: `nomeEntidade`, `ano`, `numeroDiaria`;
  - viagem: `dataInicial`, `dataFinal`, `periodoDiarias`, `localOrigem`, `localDestino`, `finalidade`, `historico`;
  - valores: `quantidade`, `valorUnitario`, `valorTotal`;
  - veículo: `veiculo`, `tipoVeiculo`, `placaVeiculo`, `custoVeiculo`;
  - outros: `fundamentoLegal`.
- **Chave candidata:** (município, `_id`). O `numeroDiaria` se repete em deslocamentos diferentes (datas e destinos distintos). Só 7 registros são cópias idênticas.

### Receitas e despesas extraorçamentárias

10.091 registros, em 7 municípios (Balneário Rincão, Lauro Müller e Urussanga não publicam). Granularidade: uma conta extraorçamentária por exercício.

- **Campos:** `numero`, `mascara`, `classificacao`, `fonteRecurso`, `movimentos` e `pagamentos`.
- **Chave candidata:** (município, `_id`).

| Lista interna | Registros | Campos | Chave candidata |
| --- | ---: | --- | --- |
| `pagamentos` | 153.235 | número, data, valor, beneficiário (nome, CPF/CNPJ), histórico | (registro, posição); o número se repete 63 vezes |
| `movimentos` | 234.464 | id, número, documento, data, valor, histórico | não usada (ver descartes) |

### Despesas orçamentárias

8.608 dotações nos 10 municípios, com `empenhos`, `suplementacoes` e `fontesRecursos` internos. Granularidade: uma dotação por exercício. Chave candidata: (município, `_id`). Não entra no modelo.

## Atende.net

CSV em latin-1, separado por `;`, com todo campo entre aspas. Um arquivo por consulta e por ano. Os registros quebrados em várias linhas são remontados no tratamento (ver [Coleta da AMREC](coleta-amrec.md#defeitos-encontrados-nos-csvs)).

| Arquivo | Treviso | Morro da Fumaça | Granularidade | Chave candidata |
| --- | ---: | ---: | --- | --- |
| `empenho_emitido` | 27.612 | 43.004 | empenho | (município, entidade, número, ano do empenho) |
| `liquidacao` | 28.400 | 66.181 | liquidação | (município, entidade, empenho, número da liquidação) |
| `pagamentos` | 34.636 | 83.841 | ordem de pagamento ou retenção | (município, entidade, empenho, número da ordem) |
| `diarias` | 489 | 4.635 | diária vinculada a empenho | sem identificador próprio |
| `orcamento_despesa` | 253 | 371 | conta de despesa por entidade | (município, entidade, conta, ano do arquivo) |

Colunas:

- **Empenhos (14 colunas):**
  - identificação: Entidade, Empenho, Emissão;
  - credor: Credor (nome), Credor (CPF/CNPJ);
  - despesa: Descrição Despesa (elemento por extenso), Histórico/Objeto;
  - licitação: número, ano, modalidade e fundamentação;
  - valores: empenhado, liquidado e pago.
- **Liquidações (7 colunas):** Entidade, Credor, Empenho, Liquidação, Data, Valor Liquidação, Espécie.
- **Pagamentos (14 colunas):**
  - identificação: Entidade, Credor, Tipo Pessoa, Nº Ordem de Pagamento, Empenho, Data;
  - licitação: número do processo, modalidade, bem ou serviço;
  - pagamento: Histórico, Tipo Pagamento, Valor Pago;
  - Ordem de Compra (número e ano).
- **Diárias:** o layout muda entre os municípios.
  - Treviso tem 8 colunas: Entidade, Credor, Cargo, Espécie, Empenho, Emissão, Valor Transporte, Valor Diárias.
  - Morro da Fumaça tem 15: as de Treviso mais Objetivo, datas de início e fim, Destino, número de diárias, valor unitário e valor total.
- **Orçamento da despesa (6 colunas):** Entidade, Conta, Descrição da Conta, Desdobramento, Elemento, Categoria Econômica. O valor fica na coluna do nível da conta.

Particularidades:

- Nos números de empenho, o sufixo `-0` aparece só em Morro da Fumaça.
- Em Morro da Fumaça, a chave se repete em 9 liquidações e 28 pagamentos, sem que as linhas sejam idênticas. Há também 53 diárias idênticas. Esses casos são resolvidos no tratamento (#37).
- Em Treviso nenhuma chave se repete.

## CPF e CNPJ na origem

O Betha publica a maior parte dos documentos mascarados, e a máscara muda de um município para outro:

| Formato publicado | Registros de empenho |
| --- | ---: |
| CNPJ só com a raiz (`99.999.999/****-**`) | 292.026 |
| CNPJ completo | 104.299 |
| CPF com os 6 primeiros dígitos (`999.999.***-**`) | 31.471 |
| CPF completo | 14.824 |
| CPF com os 6 dígitos do meio (`***.999.999-**`) | 14.232 |
| CPF com os 3 primeiros dígitos (`999.***.***-**`) | 2.261 |

Por isso o documento sozinho não identifica o credor. Em 1.485 casos, o mesmo documento mascarado pertence a pessoas diferentes no mesmo município. O credor é identificado pelo par (documento como publicado, nome normalizado).

## Base anterior

A base anterior vinha do ZIP de relatórios de Criciúma coletado em 07/11/2026 e era tratada pelo `src/limpar.py`. Ela foi substituída por esta coleta porque não permitia cumprir o requisito de 80% das tabelas com 10 mil linhas ou mais. O motivo está em [Coleta da AMREC](coleta-amrec.md#por-que-a-base-mudou).
