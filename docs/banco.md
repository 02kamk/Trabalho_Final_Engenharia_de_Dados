# Banco de origem

Esta página documenta como criar o banco de origem e carregar os dados tratados. O modelo está em [Modelo de dados](modelo.md).

O banco fica no [Neon](https://neon.com), um PostgreSQL gerenciado. A primeira versão do projeto usava o Supabase, cujo plano gratuito limita o banco a 500 MB; a base nova ocupa cerca de 770 MB, e o plano gratuito do Neon permite 1 GB por projeto.

## Visão geral

| Arquivo | Função |
| --- | --- |
| `notebooks/coleta.ipynb` | Coleta os dados brutos em `dados/brutos/amrec/`. |
| `notebooks/tratamento.ipynb` | Gera um CSV por tabela em `dados/tratados/`. |
| `sql/origem.sql` | DDL. Recria do zero o esquema `origem`, com as 15 tabelas, chaves, restrições, índices e a coluna de controle `atualizado_em`, em uma única transação. |
| `sql/carga.sql` | Carga. Copia os CSVs de `dados/tratados/` para as tabelas, em uma única transação. |
| `sql/validacao.sql` | Validação. Mostra as contagens, o critério de 10 mil linhas, as restrições, a distribuição por ano, a proteção de CPF e o tamanho do esquema. Só faz leitura. |
| `.neon` | Liga a pasta ao projeto Neon (organização, projeto e branch). Fora do Git. |
| `.env.neon` | Strings de conexão do Neon (`DATABASE_URL` e `DATABASE_URL_UNPOOLED`). Fora do Git. |

Os CSVs de `dados/tratados/` não ficam no Git: somam cerca de 400 MB, acima do limite de arquivo do GitHub. Eles são reproduzidos rodando os dois notebooks.

## Passo a passo

### 1. Acesso ao projeto Neon

O projeto é `aged-dawn-21484247` (branch `production`). Há duas formas de obter a conexão:

- **Pela CLI do Neon** (recomendado para quem tem acesso à organização): instale com `npm i -g neon`, entre com `neon login` e, na raiz do repositório, rode `neon link --project-id aged-dawn-21484247 --no-env-pull -y` e depois `neon env pull --file .env.neon`.
- **Pela string de conexão**: o responsável pelo projeto envia a URL por um canal privado da equipe, nunca pelo GitHub, e cada integrante a grava em `.env.neon` como `DATABASE_URL_UNPOOLED=...`.

O Neon fornece duas conexões para o mesmo banco:

| Variável | Tipo | Quando usar |
| --- | --- | --- |
| `DATABASE_URL_UNPOOLED` | direta | DDL, carga, `pg_dump` e leituras grandes do pipeline (Spark) |
| `DATABASE_URL` | com pool (PgBouncer, host com `-pooler`) | aplicações com muitas conexões curtas |

Use a direta para tudo o que está nesta página e para o pipeline: comandos de sessão e leituras longas podem falhar pela conexão com pool.

### 2. Instalar o cliente `psql`

O `psql` acompanha o instalador do PostgreSQL. No Windows, instale o PostgreSQL ou apenas as **Command Line Tools** e confirme:

```powershell
psql --version
```

### 3. Gerar os CSVs

Rode `notebooks/tratamento.ipynb` do início ao fim (no VS Code ou Jupyter, **Restart & Run All**). Ele termina gravando os 15 CSVs em `dados/tratados/` e só exporta se todas as conferências passarem: chaves primárias e únicas, chaves estrangeiras sem órfãos, regras de domínio e o critério de 80% das tabelas com 10 mil linhas ou mais.

### 4. Criar as tabelas, carregar e validar

Na raiz do repositório, no PowerShell:

```powershell
$env:DATABASE_URL = (Get-Content .env.neon | Where-Object { $_ -like 'DATABASE_URL_UNPOOLED=*' }) -replace '^DATABASE_URL_UNPOOLED=', '' -replace '^"|"$', ''
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/origem.sql
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/carga.sql
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/validacao.sql
Remove-Item Env:DATABASE_URL
```

!!! danger "O DDL apaga o esquema `origem`"
    O `origem.sql` começa com `DROP SCHEMA IF EXISTS origem CASCADE`: tudo o que estiver no esquema é apagado e recriado. Como o banco é inteiramente reproduzido a partir dos CSVs, isso garante que cada carga parte de um estado limpo. Não guarde no esquema `origem` nada que não venha da carga.

A carga segue a ordem das chaves estrangeiras e é transacional: qualquer erro desfaz tudo. Cada `\copy` lista as colunas e usa `HEADER MATCH`, então um CSV com colunas diferentes do esperado interrompe a carga em vez de deslocar valores. Ao final, roda `ANALYZE`.

## Limites do plano gratuito do Neon

| Limite (por projeto, por mês) | Cota | Uso atual |
| --- | --- | --- |
| Armazenamento | 1 GB | 771 MB |
| Processamento | 100 CU-horas | carga completa em pouco mais de 1 minuto |
| Transferência de dados para fora | 5 GB | uma extração completa de todas as tabelas transfere cerca de 0,5 GB |

Se o processamento ou a transferência acabarem, o Neon suspende o banco até o início do mês seguinte. Os dados não se perdem, mas nenhuma conexão funciona. Por isso:

- no desenvolvimento do pipeline, teste a ingestão com poucas tabelas ou com `LIMIT`, e rode a extração completa só quando necessário;
- use a ingestão incremental pela coluna `atualizado_em` nas execuções agendadas;
- acompanhe o consumo no painel do projeto no Neon.

O banco suspende sozinho depois de 5 minutos sem uso e volta na conexão seguinte, com uma espera de frações de segundo.

## Tamanho por tabela

| Tabela | Total | Dados | Índices |
| --- | ---: | ---: | ---: |
| `empenho` | 226 MB | 170 MB | 56 MB |
| `pagamento` | 170 MB | 147 MB | 23 MB |
| `documento_fiscal` | 64 MB | 32 MB | 32 MB |
| `liquidacao` | 58 MB | 36 MB | 22 MB |
| `item_empenho` | 46 MB | 27 MB | 19 MB |
| `empenho_documento_fiscal` | 45 MB | 23 MB | 22 MB |
| demais 9 tabelas | ~100 MB | | |

Medição feita antes da inclusão de `atualizado_em`, que acrescentou cerca de 55 MB (coluna e índice) ao total.

## Segurança

- `.env`, `.env.neon` e `.neon` estão no `.gitignore`. Antes de cada commit, confira com `git status` que nenhum deles aparece.
- CPF nunca é gravado completo: o tratamento mascara no padrão `***XXXXXX**` os CPFs publicados inteiros, inclusive dentro de textos livres. A validação confere que não há CPF completo na tabela `credor`.
- Não compartilhe a string de conexão fora da equipe.

## Situação

| Etapa | Status |
| --- | --- |
| DDL versionado (`sql/origem.sql`) | Concluído |
| CSVs gerados pelo tratamento (`dados/tratados/`) | Concluído |
| Teste completo em PostgreSQL 18 local | Concluído |
| Carga no Neon (PostgreSQL 18.7), 17/11/2026: DDL em 8 s, carga em 67 s, validação sem pendências | Concluído |

Referências: [Planos do Neon](https://neon.com/docs/introduction/plans), [Conexões com e sem pool](https://neon.com/docs/connect/connection-pooling).
