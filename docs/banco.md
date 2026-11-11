# Banco de origem no Supabase

Esta página documenta a criação do banco de origem (issue #7) e a carga dos dados limpos (issue #8).

## Visão geral

| Arquivo | Função |
| --- | --- |
| `sql/origem.sql` | DDL. Cria o esquema `origem` e as 15 tabelas com chaves primárias e estrangeiras, em uma única transação. |
| `sql/carga_inicial.sql` | Carga. Copia os CSVs de `dados/origem-validada/` para as tabelas, em uma única transação. |
| `.env.example` | Modelo da variável de conexão `DATABASE_URL`. |
| `.env` | Cópia local com a senha real. Está no `.gitignore` e nunca vai para o repositório. |

## Modelo

O esquema `origem` tem 15 tabelas:

- **Dimensões (8):** `exercicio`, `orgao`, `unidade`, `funcao`, `subfuncao`, `recurso`, `elemento`, `credor`.
- **Registros (4):** `empenho`, `diaria`, `emenda`, `dotacao`.
- **Detalhes da dotação (3):** `empenho_dotacao`, `fonte_dotacao`, `suplementacao`.

Regras de chave:

- As listagens com ID do portal (`empenho`, `diaria`, `emenda`) usam `(ano, id_origem)` como chave primária.
- A `dotacao` usa uma chave derivada do conteúdo, porque o portal não fornece identificador.
- Os detalhes usam `(ano, dotacao_id, item)` e referenciam `dotacao(ano, id_origem)`.
- As hierarquias órgão → unidade e função → subfunção são garantidas por chaves estrangeiras compostas (`unidade(id, pai_id)` e `subfuncao(id, pai_id)`). Assim, um registro não pode apontar para uma unidade de outro órgão.

## Passo a passo da implantação

### 1. Criar o projeto no Supabase

1. Acesse o [painel do Supabase](https://supabase.com/dashboard) e entre na organização da equipe.
2. Clique em **New project** e preencha:
    - **Name:** `despesas-criciuma` (sugestão)
    - **Database password:** gere uma senha forte e guarde-a. Ela vai para o `.env`.
    - **Region:** `South America (São Paulo)`, a mais próxima.
3. Aguarde o provisionamento, que leva alguns minutos.

### 2. Convidar os integrantes

Em **Organization settings → Team → Invite**, convide o e-mail de cada integrante do grupo com o papel **Developer** ou superior.

### 3. Configurar a conexão local

1. No painel do projeto, clique em **Connect** e abra a aba **Connection String**.
2. Selecione **Session pooler**. Ele funciona em redes IPv4. A conexão direta exige IPv6.
3. Copie a URL e cole em `DATABASE_URL` no arquivo `.env`, na raiz do repositório. Se o arquivo não existir, copie `.env.example` para `.env`.
4. Troque `[YOUR-PASSWORD]` pela senha do passo 1 e mantenha `?sslmode=require` no final.

```text
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<SENHA>@aws-0-<REGIAO>.pooler.supabase.com:5432/postgres?sslmode=require
```

!!! warning "Erros comuns na URL"
    - **Colchetes:** ao trocar `[YOUR-PASSWORD]`, apague também os colchetes `[ ]`. Se eles ficarem, o login falha com `password authentication failed for user "postgres"`.
    - **Caracteres especiais:** se a senha tiver `@ : / ? # % & [ ]`, codifique esses caracteres na URL. Por exemplo, `@` vira `%40`, `#` vira `%23`, `[` vira `%5B` e `]` vira `%5D`. Sem isso, a URL é lida errado, e um `#` faz tudo o que vem depois dele ser ignorado.
    - **Conexão direta:** o host `db.<PROJECT_REF>.supabase.co` só responde por IPv6. Em rede IPv4, o `psql` mostra `não foi possível traduzir o nome de hospedeiro`. Nesse caso, use a URL do **Session pooler**.

### 4. Instalar o cliente `psql`

O `psql` acompanha o instalador do PostgreSQL. No Windows, instale o PostgreSQL ou apenas as **Command Line Tools** e confirme:

```powershell
psql --version
```

### 5. Aplicar o DDL

Na raiz do repositório, no PowerShell:

```powershell
$env:DATABASE_URL = (Get-Content .env | Where-Object { $_ -like 'DATABASE_URL=*' }) -replace '^DATABASE_URL=', ''
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/origem.sql
```

O script roda dentro de `BEGIN ... COMMIT`. Se algum comando falhar, nada é criado. Ele usa `CREATE ... IF NOT EXISTS` e pode ser executado de novo sem erro.

### 6. Conferir a criação

```powershell
psql --dbname="$env:DATABASE_URL" -X -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'origem' ORDER BY 1;"
```

O resultado deve listar as **15 tabelas** da seção [Modelo](#modelo). Elas também aparecem no **Table Editor** do painel, escolhendo o esquema `origem`.

### 7. Carregar os dados (issue #8)

1. Gere os CSVs em `dados/origem-validada/` com o script de limpeza. Veja [Fontes e limpeza](fontes.md).
2. Com as tabelas vazias, execute:

```powershell
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/carga_inicial.sql
Remove-Item Env:DATABASE_URL
```

A carga segue a ordem das chaves estrangeiras: primeiro as dimensões, depois os registros e por último os detalhes. Ela é transacional, então uma chave duplicada ou órfã desfaz tudo. Use sempre arquivos gerados na mesma execução da limpeza.

## Segurança

- A senha fica só no `.env` local, que está no `.gitignore`. Antes de cada commit, confira com `git status` que o `.env` não aparece.
- O esquema `origem` não deve ser adicionado aos esquemas expostos pela Data API (**Project settings → Data API → Exposed schemas**). Assim os dados só são acessíveis por conexão PostgreSQL autenticada.
- A tabela `emenda` inclui identificadores de favorecidos. Não compartilhe a string de conexão fora da equipe.

## Situação

| Etapa | Status |
| --- | --- |
| DDL versionado (`sql/origem.sql`) | Concluído |
| `.env.example` e `.env` fora do Git | Concluído |
| Integridade relacional validada localmente (`origem.sqlite3`) | Concluído |
| Projeto criado no Supabase | Concluído |
| Integrantes convidados para o projeto | A confirmar |
| DDL aplicado no Supabase (11/11/2026) | Concluído |
| Carga e validação no Supabase (issue #8) | Pendente |

### Verificação do DDL no Supabase

Conferência feita em 11/11/2026 pelo Session pooler, em PostgreSQL 17.11. O esquema `origem` tem as 15 tabelas, todas com chave primária, e 25 chaves estrangeiras. As tabelas estão vazias e aguardam a carga da issue #8. O esquema `origem` não está exposto na Data API, que continua com a configuração padrão.

| Tabela | Colunas | Chaves estrangeiras |
| --- | ---: | ---: |
| `exercicio` | 1 | 0 |
| `orgao` | 2 | 0 |
| `unidade` | 3 | 1 |
| `funcao` | 2 | 0 |
| `subfuncao` | 3 | 1 |
| `recurso` | 2 | 0 |
| `elemento` | 2 | 0 |
| `credor` | 2 | 0 |
| `empenho` | 16 | 8 |
| `diaria` | 9 | 4 |
| `emenda` | 13 | 1 |
| `dotacao` | 18 | 6 |
| `empenho_dotacao` | 7 | 1 |
| `fonte_dotacao` | 7 | 2 |
| `suplementacao` | 6 | 1 |

Consulta usada para conferir:

```sql
SELECT table_name, constraint_type, count(*)
FROM information_schema.table_constraints
WHERE table_schema = 'origem' AND constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
GROUP BY 1, 2
ORDER BY 1, 2;
```

Referência: [Conexões PostgreSQL no Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).
