# Coleta da AMREC (2023–2026)

Registro de trabalho da nova coleta, feita entre 16 e 17/11/2026. Serve de base para a documentação final: guarda o que foi decidido, o que foi descartado e por quê, e os defeitos encontrados nos arquivos de origem. As contagens finais por tabela entram depois do tratamento (#37) e da validação (#38).

## Por que a base mudou

A base anterior cobria só Criciúma, com 15 tabelas. Ela não atendia os requisitos do trabalho:

- pelo menos 10 tabelas;
- pelo menos 80% de **todas** as tabelas com 10.000 linhas ou mais;
- modelo em 3FN;
- período obrigatório de 2023 a 2026, sem reduzir.

Com uma cidade só, as tabelas de cadastro (credor, dotação, elemento etc.) ficam pequenas. Não há como chegar a 80% sem quebrar a 3FN ou inflar tabelas artificialmente.

## Fontes avaliadas e descartadas

Antes de fechar a AMREC, outras fontes de despesa pública foram avaliadas:

| Fonte | O que foi visto | Por que ficou de fora |
| --- | --- | --- |
| Dados abertos do Estado de SC (dados.sc.gov.br) | Empenhos atualizados de 2021 a 2026 | Liquidações, pagamentos e diárias param em 2022; não cobre o período |
| Portal da Transparência federal (download diário de despesas) | ~8 MB por dia compactado; ~8 GB compactados e ~65 GB descompactados para 2023–2026. A tabela de UGs do Tesouro permite filtrar por UF | Mesmo filtrando, a Região Sul fica em 2–3 GB no banco e só SC em 0,5–1 GB, além de ser preciso baixar o país inteiro para filtrar |
| Arquivos em lote da Câmara dos Deputados | Cota parlamentar e afins | Chega a ~75–80% das tabelas acima de 10 mil linhas e fica perto de 500 MB |
| AMREC com 10 cidades (só as que usam Betha) | Coleta 100% automatizada | Rejeitada: deixaria Treviso e Morro da Fumaça de fora e não seria a AMREC completa |

## Escopo final

Os 12 municípios da AMREC, de 2023 a 2026 (2026 parcial).

| Município | IBGE | Fonte | Coleta |
| --- | --- | --- | --- |
| Balneário Rincão | 4220000 | Betha | Automatizada |
| Cocal do Sul | 4204251 | Betha | Automatizada |
| Criciúma | 4204608 | Betha | Automatizada (coleta anterior) |
| Forquilhinha | 4205456 | Betha | Automatizada |
| Içara | 4207007 | Betha | Automatizada |
| Lauro Müller | 4209607 | Betha | Automatizada |
| Morro da Fumaça | 4211207 | Atende.net (IPM) | Exportação manual |
| Nova Veneza | 4211603 | Betha | Automatizada |
| Orleans | 4211702 | Betha | Automatizada |
| Siderópolis | 4217600 | Betha | Automatizada |
| Treviso | 4218350 | Atende.net (IPM) | Exportação manual |
| Urussanga | 4219002 | Betha | Automatizada |

O modelo de tabelas está descrito na issue #36.

## Portais Betha (10 municípios)

### Como a API funciona

- O token é anônimo (OAuth público do portal), sem login.
- Cada requisição leva o cabeçalho `App-Context`, um JSON em base64 com o `hash` do portal.
- A lista de portais de SC sai da API de portais do Betha: 450 portais, de 165 municípios. Um município pode ter vários portais (prefeitura, câmara, autarquias). Para cada cidade foi usado o portal da prefeitura.
- Cada portal tem IDs próprios para as consultas. Os IDs mudam de uma cidade para outra, então o coletor localiza cada consulta pelo **título** no menu (`/api/menu`).
- Para cada consulta, o coletor:
  1. descobre o nome do filtro de ano (`ano` ou `anoExercicio`, conforme a consulta);
  2. lista os IDs de cada ano (`/api/busca-textual/{consulta}`);
  3. baixa o detalhe de cada registro (`/api/busca/{consulta}/detalhes/{id}`).

### Consultas coletadas

| Título no portal | Arquivo |
| --- | --- |
| Execução detalhada de despesas | `execucao_detalhada.jsonl` |
| Diárias | `diarias.jsonl` |
| Receitas e despesas extraorçamentárias | `extraorcamentarias.jsonl` |
| Despesas orçamentárias | `despesas_orcamentarias.jsonl` |

Nem todo portal publica todas as consultas. Quando a consulta não existe, o manifesto registra `AUSENTE`.

### Organização dos arquivos

```
dados/brutos/amrec/<ibge>_<nome>/
  <consulta>.jsonl          um registro por linha, com _id, _ano, _ibge e _consulta
  <consulta>_falhas.log     IDs que falharam e o motivo
  manifesto.json            total do portal por ano x total baixado, status OK/INCOMPLETO
```

`dados/` está no `.gitignore`: os brutos têm CPF e CNPJ de credores e não vão para o repositório.

### Como executar

A coleta está no notebook `notebooks/coleta.ipynb`. A primeira célula define o que coletar:

- `COLETAR`: lista de códigos IBGE (o padrão são os 10 municípios do Betha);
- `ANOS`: os exercícios (2023 a 2026);
- `PASSADAS`: quantas rodadas fazer para refazer o que falhou;
- `TELA_LIGADA`: se a tela também deve ficar acesa.

Como funciona:

- Os municípios são coletados ao mesmo tempo, com 2 conexões cada.
- Por padrão são feitas 2 passadas: a segunda refaz só os municípios com alguma consulta incompleta.
- Enquanto a célula de execução roda, o Windows não suspende.
- Ao reabrir um arquivo, o coletor descarta a última linha se ela ficou incompleta por uma queda no meio da gravação, e também remove registros repetidos.
- O progresso detalhado vai para `dados/brutos/amrec/coleta.log`. No notebook aparecem só o resultado de cada consulta, a tabela de conferência lida dos manifestos e a verificação dos arquivos do Atende.net.
- A célula de conferência falha se alguma consulta continuar incompleta.

O coletor foi testado numa cópia dos dados de Nova Veneza com uma linha cortada e uma linha repetida. Ele baixou só os 30 registros que faltavam, limpou as duas linhas e marcou as 4 consultas como `OK`.

!!! warning "Executar pelo terminal no Windows"
    O `jupyter execute` lê o notebook na codificação padrão do Windows e corrompe os acentos ao salvar (`já` vira `jÃ¡`). Pelo terminal, ative o modo UTF-8 antes: `$env:PYTHONUTF8 = "1"` no PowerShell. No VS Code e no Jupyter pelo navegador isso não acontece.

### Problemas durante o download

- **Velocidade limitada pelo servidor.** O Betha entrega de 4 a 23 registros por segundo no total, oscilando bastante. Mais conexões em paralelo não aumentam esse teto. Por isso o coletor usa 2 conexões por cidade, com pausa de 0,3 s, e as 9 cidades rodam ao mesmo tempo.
- **Quedas de rede.** Houve erros de DNS e conexão (`getaddrinfo failed`, entre outros) e, na madrugada de 16 para 17/11, o download ficou quase parado das ~01h10 às ~09h. A causa provável é a suspensão do computador ou a queda da internet. Cada execução detalhada perdeu de 100 a 115 registros, menos de 0,3%.
- **Como as falhas foram tratadas:**
  - o coletor é retomável: pula os IDs que já estão no arquivo;
  - uma segunda passada roda automaticamente ao fim da primeira e busca só o que falhou;
  - durante a coleta, um processo pede ao Windows para não suspender (`SetThreadExecutionState`), sem alterar a configuração de energia. Ele se encerra sozinho ao fim da segunda passada.
- **Conferência:** o `manifesto.json` de cada cidade compara o total informado pelo portal com o total baixado. Uma cidade só conta como concluída com status `OK` em todas as consultas.

### Resultado

Coleta concluída em 17/11/2026. Na conferência final do notebook, o total baixado é igual ao total do portal em todas as consultas.

| Município | Execução detalhada | Diárias | Extraorçamentárias | Despesas orçamentárias |
| --- | ---: | ---: | ---: | ---: |
| Balneário Rincão | 29.707 | 2.808 | ausente | 621 |
| Cocal do Sul | 46.340 | 1.181 | 1.159 | 754 |
| Criciúma | 62.739 | 11.447 | 1.574 | 1.518 |
| Forquilhinha | 43.076 | 909 | 2.119 | 873 |
| Içara | 59.672 | 3.575 | 2.616 | 1.389 |
| Lauro Müller | 31.396 | 1.207 | ausente | 629 |
| Nova Veneza | 14.903 | 56 | 701 | 515 |
| Orleans | 39.027 | 320 | 1.029 | 601 |
| Siderópolis | 25.999 | 181 | 893 | 643 |
| Urussanga | 36.753 | ausente | ausente | 1.065 |
| **Total** | **389.612** | **21.684** | **10.091** | **8.608** |

- "Ausente" significa que o portal do município não publica essa consulta.
- A primeira passada terminou com cerca de 900 registros faltando, perdidos nas quedas de rede. A segunda passada recuperou todos.
- Criciúma veio da coleta anterior (de 13/11, em `dados/brutos/detalhe/`), convertida para o mesmo formato. O notebook baixou só o que entrou no portal depois: 175 registros de execução e 32 diárias.
- Alguns registros baixados depois saíram do portal: 3 em Forquilhinha e 1 nas diárias de Criciúma. Eles continuam no arquivo, mas não entram na contagem do manifesto. A coleta grava a lista de IDs publicados em `<consulta>_ids.json`, e o tratamento usa só esses.
- O código IBGE (`_ibge`) é gravado como texto. Os arquivos baixados pelo coletor antigo, que o gravava como número, foram convertidos.

## Portais Atende.net (Treviso e Morro da Fumaça)

### Por que a coleta foi manual

O Atende.net (IPM) usa a verificação anti-robô Cloudflare Turnstile nas consultas da transparência. Contornar essa verificação não é aceitável, então os dados vieram da exportação manual em CSV, feita pelo próprio portal.

- Treviso: https://treviso.atende.net/transparencia/grupo/despesas
- Morro da Fumaça: https://morrodafumaca.atende.net/transparencia/grupo/despesas

### O que foi exportado

As mesmas 5 consultas nos dois municípios, um arquivo por ano, de 2023 a 2026 (20 arquivos por município):

| Consulta | Arquivo |
| --- | --- |
| Empenhos emitidos | `empenho_emitido_<ano>.csv` |
| Liquidações | `liquidacao_<ano>.csv` |
| Pagamentos | `pagamentos_<ano>.csv` |
| Diárias | `diarias_<ano>.csv` |
| Orçamento da despesa | `orcamento_despesa_<ano>.csv` |

A consulta "Ordens de Compra" aparece no menu, mas a página está vazia (não publicada) e foi ignorada.

Em Treviso, o portal baixou tudo como `Relatorio.csv`, `Relatorio (1).csv` etc. Os arquivos foram identificados pelo cabeçalho e pelo ano dos empenhos, e renomeados. Em Morro da Fumaça, eles já foram renomeados no download.

### Defeitos encontrados nos CSVs

- **Codificação e separador:** os arquivos vêm em latin-1 (não UTF-8), separados por `;`, com todos os campos entre aspas.
- **Registros quebrados em várias linhas:** campos de texto livre (histórico, objeto, objetivo da viagem) têm quebras de linha e aspas sem escape no meio do texto. Por isso, nem um leitor de CSV que respeita aspas consegue ler o arquivo direito.

  | Morro da Fumaça | Linhas físicas | Registros reais |
  | --- | ---: | ---: |
  | Empenhos | 43.590 | 43.004 |
  | Pagamentos | 89.601 | 83.841 |
  | Diárias | 4.641 | 4.635 |

  Em Treviso o mesmo problema aparece, principalmente nos pagamentos (1.774 linhas quebradas) e em 8 empenhos.

  **Correção:** todo registro começa pelo nome da entidade entre aspas, seguido de `";"`. O arquivo é dividido nesses pontos, e cada registro é separado pelos delimitadores `";"`. Testado nos 32 arquivos de movimento dos dois municípios: 100% dos registros ficaram com o número certo de colunas. A correção será aplicada no notebook de tratamento (#37).

- **Orçamento sem ano:** o arquivo de orçamento da despesa não tem coluna de ano. O ano vem do nome do arquivo, ou seja, da ordem em que o arquivo foi baixado.
  - Em Morro da Fumaça, o total orçado cresce a cada ano (R$ 65,6 mi → 68,3 → 77,9 → 89,0), coerente com os nomes.
  - Em Treviso, o total orçado é de R$ 54,7 mi → 66,5 → 65,5 → 76,9. A parte empenhada fica em 70%, 71% e 72% de 2023 a 2025, e em 55% em 2026, que ainda não terminou. Os dados não contradizem a ordem do download, confirmada por quem baixou. Só 2024 e 2025 são próximos demais para serem distinguidos apenas pelos valores.
- **Orçamento com valores em colunas diferentes:** o valor de cada linha fica em `Desdobramento`, `Elemento` ou `Categoria Econômica`, conforme o nível da conta. O detalhamento vai só até grupo e modalidade, sem chegar ao elemento.
- **Classificação incompleta nos empenhos:** não há função nem unidade. O elemento vem só pela descrição (por exemplo, "Material de Consumo"), sem código, e será mapeado para o código nacional no tratamento.
- **Sem itens, notas fiscais nem anulações detalhadas.** Por isso, os dois municípios não entram nas tabelas `item_empenho`, `documento_fiscal`, `empenho_documento_fiscal` e `anulacao_empenho`.
- **Ligações entre as consultas:** liquidações e pagamentos se ligam ao empenho por (entidade, número/ano do empenho), com os espaços removidos do número. Em Treviso, 99,9% dos registros se ligam. Os pagamentos com tipo "Retenção" (5.901 em Treviso) são retenções, não pagamentos ao credor.
- **Número do empenho em três formatos:** `1 / 2025` (empenhos), `129/2025` (liquidações e pagamentos de Treviso) e `824-0/2025` (liquidações e pagamentos de Morro da Fumaça; o sufixo é sempre `-0`). Depois de separar número e ano, a chave (município, entidade, número, ano) não se repete.
- **Restos a pagar:** algumas liquidações e pagamentos apontam para empenhos de 2020 a 2022, emitidos antes do período coletado. Todos os registros sem empenho correspondente são desse tipo: 170 liquidações e 330 pagamentos, somando os dois municípios. Como o empenho de origem não está na base, eles ficam fora do modelo.

### Volume

| Consulta | Treviso | Morro da Fumaça |
| --- | ---: | ---: |
| Empenhos | 27.612 | 43.004 |
| Liquidações | 28.400 | 66.181 |
| Pagamentos | 34.636 | 83.841 |
| Diárias | 489 | 4.635 |

## Contagem prévia do modelo

Contagem feita direto nos arquivos brutos, antes do tratamento, para confirmar o critério dos 80% antes de escrever o notebook. Os números finais saem do tratamento (#37) e da validação (#38).

| Tabela | Linhas (prévia) |
| --- | ---: |
| `pagamento` | ~576 mil |
| `liquidacao` | ~546 mil |
| `empenho` | ~460 mil |
| `empenho_documento_fiscal` | ~441 mil |
| `item_empenho` | ~422 mil |
| `documento_fiscal` | ~365 mil |
| `retencao` | ~275 mil |
| `pagamento_extraorcamentario` | ~153 mil |
| `material` | ~84 mil |
| `anulacao_empenho` | ~47 mil |
| `diaria` | ~27 mil |
| `credor` | ~23 mil |
| `elemento_despesa` | ~670 |
| `funcao` | ~36 |
| `municipio` | 12 |

12 de 15 tabelas (80%) ficam acima de 10 mil linhas, com folga: a menor delas, `credor`, tem mais que o dobro do mínimo. As três abaixo são tabelas de domínio.

## Decisões de modelagem tomadas a partir dos dados

Detalhadas na issue #36. Em resumo:

- **Diárias:** a consulta "Diárias e Viagens – Cargo" repete a de diárias (11.277 de 11.416 registros em Criciúma). Só a de diárias é usada.
- **Retenções:** os movimentos extraorçamentários são as retenções vistas pelo lado contábil (62.510 de 62.513 apontam para uma liquidação). Por isso entram na tabela `retencao` e não viram uma tabela própria.
- **Pessoal:** a consulta de despesas com pessoal repete a execução detalhada (9.713 de 9.715 empenhos) e não vira tabela.
- **Dotação:** fica fora do modelo. As 10 cidades do Betha somam só 8.608 dotações, e o Atende.net não publica dotação.
- **Unidade, subfunção, programa, ação e fonte:** ficam fora do modelo. Cada prefeitura nomeia suas unidades de um jeito, então elas não são comparáveis entre municípios. Função e elemento seguem o padrão nacional e ficam.
- **Tipos com poucos valores** (tipo de empenho, de anulação, de pagamento) viram restrição `CHECK`, sem tabela.
- **Chave do empenho:** é o ID do registro no portal, não o número do empenho. O número se repete 15.880 vezes em empenhos diferentes do mesmo município, entidade e ano; em Urussanga, a numeração recomeça por categoria. Nenhum empenho aparece de novo em outro exercício.
- **Retenções de Içara e Urussanga:** esses dois portais publicam a retenção na liquidação e de novo no pagamento. Quando o empenho tem retenções nos dois lugares, as listas são idênticas em 99% dos casos. A tabela usa as retenções da liquidação e acrescenta só as do pagamento que não têm correspondente nela.
- **Credor:** o Betha publica CPF e CNPJ mascarados, com máscaras diferentes por município, e o mesmo documento mascarado aparece com nomes diferentes 1.485 vezes. O credor é identificado pelo par (documento como publicado, nome normalizado). Uma mesma empresa publicada com máscaras diferentes em dois municípios fica como dois credores, porque não há como unificar com segurança.
- **Material:** catálogo único da AMREC, por (descrição, unidade de medida) normalizadas. Feito por município, teria quase o mesmo tamanho (86 mil contra 84 mil), então a separação não traria ganho.

## Pendências

- [x] Fim da primeira e da segunda passada do Betha; conferir todos os `manifesto.json`
- [x] Preencher a contagem final por município e por consulta
- [x] Levar a coleta para o repositório (`notebooks/coleta.ipynb`)
- [x] Executar o notebook de coleta depois do download, para registrar a conferência final nas saídas
- [x] Renomear as pastas baixadas para `<ibge>_<município>` e trazer Criciúma para o mesmo formato
- [x] Tratamento no notebook (#37), validação (#38), DDL (#39) e carga no Neon (#40)
