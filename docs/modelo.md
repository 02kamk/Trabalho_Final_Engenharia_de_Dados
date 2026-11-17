# Modelo de dados

Modelo da issue #36. São 15 tabelas em 3FN, criadas por `sql/origem.sql` e preenchidas pelo notebook `notebooks/tratamento.ipynb`. As contagens entre parênteses são as linhas geradas pelo tratamento.

Convenções:

- **PK** é a chave primária e **FK** a chave estrangeira.
- **Única** indica outra restrição de unicidade além da chave primária.
- `id_*` gerados pelo tratamento são números sequenciais.
- Valores em reais são `numeric(15,2)`.

## Visão geral

```
municipio ─┬─< empenho >─┬── credor
           │             ├── elemento_despesa
           │             ├── funcao
           │             ├─< item_empenho >── material
           │             ├─< empenho_documento_fiscal >── documento_fiscal >── credor (emitente)
           │             ├─< anulacao_empenho
           │             ├─< liquidacao ─< retencao
           │             ├─< retencao            (Atende.net: retenção ligada direto ao empenho)
           │             └─< pagamento
           ├─< diaria >── credor
           └─< pagamento_extraorcamentario >── credor
```

## Coluna de controle

Todas as 15 tabelas têm, além das colunas listadas abaixo, `atualizado_em timestamptz NOT NULL`. O banco a preenche com o momento da inserção, e um gatilho (`marcar_atualizacao`) a renova a cada `UPDATE`. Ela não vem dos CSVs e existe para a ingestão incremental do pipeline (#12, #18): cada execução extrai só as linhas com `atualizado_em` posterior à anterior, e os testes de SCD tipo 2 (#17) enxergam as alterações feitas na origem. Cada tabela tem um índice nessa coluna.

## Tabelas de domínio

### `municipio` (12)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `ibge` | `char(7)` | PK | código IBGE |
| `nome` | `varchar` | não nulo, única | nome oficial |
| `fonte` | `varchar` | `CHECK` em ('Betha', 'Atende.net') | portal de origem |
| `data_coleta` | `date` | não nulo | dia em que os dados do município foram coletados |

### `funcao` (28)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `codigo` | `smallint` | PK | código nacional da função (Portaria MOG 42/1999), como 10 = Saúde |
| `nome` | `varchar` | não nulo, única | nome oficial |

O Betha publica só o nome da função, às vezes com os acentos perdidos na origem (`Sade`, `Educao`). O código é obtido comparando o nome com a tabela oficial. O Atende.net não publica a função.

### `elemento_despesa` (50)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `codigo` | `char(2)` | PK | elemento de despesa nacional (Portaria 163/2001), como 30 = Material de Consumo |
| `nome` | `varchar` | não nulo | nome oficial |

No Betha, o elemento corresponde aos dígitos 5 e 6 do código de 14 dígitos. Os dígitos seguintes são o desdobramento de cada prefeitura e não são comparáveis entre municípios.

O Atende.net publica só a descrição do subelemento. Ela é convertida para o elemento assim:

1. pela correspondência entre descrição e elemento observada no Betha, quando um elemento responde por 95% ou mais dos casos (~90% dos empenhos);
2. entre 36 (serviço de pessoa física) e 39 (pessoa jurídica), pelo tipo do documento do credor (CPF ou CNPJ);
3. pelas descrições abreviadas de Morro da Fumaça, por uma tabela manual de cerca de 12 linhas, documentada no notebook.

O que não se resolver fica com elemento nulo, e a quantidade é registrada.

## Cadastros

### `credor` (28.814)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_credor` | `integer` | PK | gerado |
| `documento` | `varchar(18)` | | CPF/CNPJ como publicado, só dígitos e `*` |
| `nome` | `varchar` | não nulo | nome normalizado, em maiúsculas |
| | | única (`documento`, `nome`) | |

CPF nunca é gravado completo. Quando a fonte publica o CPF inteiro, ele é mascarado no padrão `***XXXXXX**` (os seis dígitos do meio, como vários portais já fazem). Isso também faz a mesma pessoa coincidir entre municípios que publicam o CPF completo e os que publicam mascarado.

O documento vem mascarado de formas diferentes em cada município, e o mesmo documento mascarado pertence a pessoas diferentes 1.485 vezes. Por isso a identificação usa o par.

O tipo de pessoa não é guardado: ele se deduz do formato do documento (11 ou 14 posições). Guardá-lo criaria uma dependência de parte da chave.

Os emitentes de documentos fiscais e os beneficiários de pagamentos extraorçamentários também entram nesta tabela.

### `material` (84.996)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_material` | `integer` | PK | gerado |
| `descricao` | `varchar` | não nulo | descrição do item, normalizada |
| `unidade_medida` | `varchar` | não nulo | unidade, normalizada |
| | | única (`descricao`, `unidade_medida`) | |

Algumas descrições passam do tamanho máximo de um índice comum do PostgreSQL (2,7 KB). A unicidade é garantida por um índice sobre o hash `md5` da descrição.

### `documento_fiscal` (384.546)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_documento` | `bigint` | PK | gerado |
| `id_emitente` | `integer` | FK → `credor` | emitente |
| `tipo` | `varchar` | não nulo | Nota Fiscal, Recibo, Fatura... |
| `numero` | `varchar` | não nulo | número do documento |
| `data_emissao` | `date` | | |
| `chave_acesso` | `varchar(60)` | | chave de autenticação, só dígitos, quando houver |
| | | única (`id_emitente`, `tipo`, `numero`, `data_emissao`) | |

Recibos, guias e documentos "Outros" reutilizam números, e só a data de emissão os separa: sem ela, 10.966 documentos distintos seriam fundidos. O valor fica no vínculo com o empenho (`empenho_documento_fiscal`), porque uma nota dividida entre empenhos aparece em cada um com a parte que lhe cabe (6.506 casos).

## Execução da despesa

### `empenho` (460.262)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_empenho` | `bigint` | PK | gerado |
| `ibge` | `char(7)` | FK → `municipio` | |
| `id_origem` | `varchar` | não nulo | Betha: ID do registro no portal. Atende.net: entidade, número e ano |
| `entidade` | `varchar` | não nulo | prefeitura, fundo, câmara, autarquia |
| `numero` | `integer` | não nulo | número do empenho |
| `ano` | `smallint` | não nulo | exercício |
| `data_emissao` | `date` | não nulo | |
| `tipo` | `varchar` | `CHECK` em ('Ordinário', 'Estimativo', 'Global') | Atende.net: espécie, tirada das liquidações |
| `id_credor` | `integer` | FK → `credor` | nulo em 1.118 empenhos do Betha publicados sem nome nem documento do credor |
| `codigo_elemento` | `char(2)` | FK → `elemento_despesa` | |
| `elemento_inferido` | `boolean` | não nulo | verdadeiro quando o elemento foi deduzido da descrição (Atende.net) e não informado pela fonte |
| `codigo_funcao` | `smallint` | FK → `funcao` | nulo no Atende.net |
| `historico` | `text` | | |
| `valor` | `numeric(15,2)` | não nulo | valor original do empenho, sem descontar anulações |
| | | única (`ibge`, `id_origem`) | |

Os valores liquidado, pago e anulado não ficam no empenho: eles são a soma das tabelas filhas, e guardá-los criaria dados derivados que podem divergir. O Betha também publica um `valorEmpenhado`, mas ele não tem o mesmo significado em todos os municípios (às vezes já desconta as anulações) e vem vazio em 8.164 empenhos; por isso o valor é o original.

### `item_empenho` (422.161, só Betha)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_empenho` | `bigint` | PK, FK → `empenho` | |
| `sequencia` | `smallint` | PK | posição do item no empenho |
| `id_material` | `integer` | FK → `material` | |
| `quantidade` | `numeric(18,4)` | | |
| `valor_unitario` | `numeric(18,4)` | | |
| `valor_total` | `numeric(15,2)` | | |

O valor total é guardado porque não é derivado: em 10.852 itens (2,6%) o total publicado difere de quantidade × valor unitário.

### `empenho_documento_fiscal` (445.096, só Betha)

| Coluna | Tipo | Restrição |
| --- | --- | --- |
| `id_empenho` | `bigint` | PK, FK → `empenho` |
| `id_documento` | `bigint` | PK, FK → `documento_fiscal` |
| `valor` | `numeric(15,2)` | não nulo; parte do documento atribuída ao empenho |

### `anulacao_empenho` (47.020, só Betha)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_empenho` | `bigint` | PK, FK → `empenho` | |
| `sequencia` | `smallint` | PK | posição da anulação no empenho |
| `data` | `date` | não nulo | |
| `tipo` | `varchar` | `CHECK` em ('Parcial', 'Total') | |
| `motivo` | `text` | | |
| `valor` | `numeric(15,2)` | não nulo | |

### `liquidacao` (546.537)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_liquidacao` | `bigint` | PK | gerado |
| `id_empenho` | `bigint` | FK → `empenho` | |
| `numero` | `varchar` | não nulo | Betha: `idLiquidacao`. Atende.net: número da liquidação |
| `data` | `date` | não nulo | |
| `valor` | `numeric(15,2)` | não nulo | |
| `valor_anulado` | `numeric(15,2)` | | soma das anulações da liquidação; nulo no Atende.net, que não publica |

### `retencao` (275.506)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_retencao` | `bigint` | PK | gerado |
| `id_liquidacao` | `bigint` | FK → `liquidacao` | Betha |
| `id_empenho` | `bigint` | FK → `empenho` | Atende.net, que só informa o empenho |
| `data` | `date` | não nulo | |
| `valor` | `numeric(15,2)` | não nulo | |
| | | `CHECK`: exatamente uma das duas FKs preenchida | |

As duas ligações nunca são preenchidas juntas. Quando a retenção pertence a uma liquidação, o empenho se obtém por ela, e repeti-lo criaria dependência transitiva.

### `pagamento` (576.524)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_pagamento` | `bigint` | PK | gerado |
| `id_empenho` | `bigint` | FK → `empenho` | |
| `numero_ordem` | `varchar` | | ordem de pagamento (Atende.net) |
| `data` | `date` | não nulo | |
| `valor` | `numeric(15,2)` | não nulo | |
| `valor_anulado` | `numeric(15,2)` | | soma das anulações do pagamento; nulo no Atende.net |
| `historico` | `text` | | |

## Outras despesas

### `diaria` (26.808)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_diaria` | `bigint` | PK | gerado |
| `ibge` | `char(7)` | FK → `municipio` | |
| `id_credor` | `integer` | FK → `credor` | servidor |
| `entidade` | `varchar` | não nulo | |
| `cargo` | `varchar` | | |
| `data_inicio` | `date` | | |
| `data_fim` | `date` | | |
| `destino` | `varchar` | | |
| `finalidade` | `text` | | |
| `quantidade` | `numeric(6,2)` | | número de diárias |
| `valor` | `numeric(15,2)` | não nulo | valor total das diárias |

O valor unitário não é guardado, porque é valor ÷ quantidade. Treviso só publica o valor total.

### `pagamento_extraorcamentario` (153.235, só Betha)

| Coluna | Tipo | Restrição | Origem |
| --- | --- | --- | --- |
| `id_pagamento_extra` | `bigint` | PK | gerado |
| `ibge` | `char(7)` | FK → `municipio` | |
| `conta` | `varchar` | | classificação da conta extraorçamentária (vazia em 375 contas) |
| `id_credor` | `integer` | FK → `credor` | beneficiário |
| `data` | `date` | não nulo | |
| `valor` | `numeric(15,2)` | não nulo | |
| `historico` | `text` | | |

## Decisões de normalização

- **Entidade como texto, sem tabela própria.** Prefeitura, fundos e câmara de cada município somam poucas dezenas de linhas. Uma tabela `entidade` seria a 16ª, abaixo de 10 mil linhas, e derrubaria a proporção para 75%. A entidade não determina nenhum outro atributo do empenho, então mantê-la como texto não fere a 3FN.
- **Sem valores derivados.** Os totais liquidado e pago do empenho e o valor unitário da diária são calculáveis a partir de outras colunas (o unitário da diária é sempre valor ÷ quantidade, conferido nos 21.684 registros do Betha).
- **Sem dados bancários.** Banco, agência e conta dos pagamentos são da prefeitura, não do credor, e não entram em nenhuma análise.
- **Tipo de pagamento e categoria do empenho ficam fora.** Ambos têm grafias diferentes em cada município (27 variações para o tipo de pagamento) e não acrescentam informação comparável.
- **Restos a pagar anteriores a 2023.** Liquidações e pagamentos de empenhos emitidos antes do período ficam fora, porque o empenho de origem não está na base.

## O que mudou em relação ao modelo anterior

O [modelo anterior](modelagem.md) usava só Criciúma e também tinha 15 tabelas, mas só 3 delas passavam de 10 mil linhas.

| Modelo anterior (Criciúma) | Modelo atual (AMREC) | Motivo |
| --- | --- | --- |
| `exercicio` | coluna `ano` | 4 linhas; o ano não determina nenhum outro atributo |
| `orgao`, `unidade`, `subfuncao`, `recurso` | fora do modelo | não comparáveis entre municípios e abaixo de 10 mil linhas |
| `elemento` (desdobramento local) | `elemento_despesa` (elemento nacional, 2 dígitos) | comparável entre os 12 municípios e deduzível no Atende.net |
| `dotacao`, `empenho_dotacao`, `fonte_dotacao`, `suplementacao` | fora do modelo | 8.608 dotações nas 10 cidades do Betha; o Atende.net não publica dotação |
| `emenda` | fora do modelo | 40 registros |
| `empenho`, `diaria`, `credor`, `funcao` | mantidas, com novas colunas | |
| — | `municipio`, `material`, `item_empenho`, `documento_fiscal`, `empenho_documento_fiscal`, `anulacao_empenho`, `liquidacao`, `retencao`, `pagamento`, `pagamento_extraorcamentario` | fases da despesa (liquidação, pagamento) e detalhes do empenho publicados pelo portal |

Também mudaram três regras do modelo anterior:

- **Valores derivados.** O modelo anterior guardava no empenho os valores liquidado e pago, como o portal publica. O atual os obtém das tabelas de liquidação e pagamento.
- **Chave do empenho.** Antes era `(ano, id_origem)`; agora é um ID gerado, com `(ibge, id_origem)` como chave única, porque o ID do portal só é único dentro de cada município.
- **Proteção de dados.** Antes, a cópia pública esvaziava o documento das emendas. Agora, CPF nunca é gravado completo em nenhuma tabela, e CNPJ é mantido, por ser dado público de empresa.

## Diferenças em relação à prática de mercado

Duas escolhas deste modelo vêm do requisito do trabalho (pelo menos 80% das tabelas com 10 mil linhas ou mais), e não seriam feitas num banco de produção:

- **Entidade sem tabela própria.** Num sistema real, `entidade` seria uma tabela, mesmo pequena.
- **Unidade, subfunção, programa, ação e fonte de recurso fora do modelo.** Num sistema real, elas ficariam como tabelas de domínio. Aqui, além de pequenas, não são comparáveis entre municípios (cada prefeitura nomeia suas unidades) e não entram nas análises previstas.

Nenhuma das duas fere a 3FN.

Este é o modelo de **origem**, normalizado para garantir integridade. Para análise, o padrão é montar depois um modelo dimensional (fatos e dimensões), que desnormaliza de propósito a partir deste.
