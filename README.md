# Despesas públicas de Criciúma

Trabalho final de Engenharia de Dados.

## Descrição

O projeto organiza as despesas públicas do município de Criciúma (SC) de 2023 a 2026 em um banco PostgreSQL normalizado, hospedado no Supabase.

O fluxo tem três etapas:

1. **Coleta:** exportações do [Portal da Transparência de Criciúma](https://transparencia.criciuma.sc.gov.br/#despesas), feitas em 07/11/2026.
2. **Limpeza:** o script [src/limpar.py](src/limpar.py) normaliza os CSVs do portal, remove repetições e confere chaves primárias e estrangeiras em SQLite.
3. **Carga:** os scripts em [sql/](sql) criam o esquema `origem`, com 15 tabelas e 25 chaves estrangeiras, carregam os CSVs e validam o resultado.

A base pronta para carga está em [dados/origem-validada](dados/origem-validada). São 15 CSVs com 151.851 registros.

| Pasta ou arquivo | Conteúdo |
| --- | --- |
| [src/limpar.py](src/limpar.py) | Limpeza e normalização a partir do ZIP da coleta |
| [sql/origem.sql](sql/origem.sql) | DDL do esquema `origem` |
| [sql/carga_inicial.sql](sql/carga_inicial.sql) | Carga dos CSVs no banco |
| [sql/validacao_carga.sql](sql/validacao_carga.sql) | Conferência da carga (somente leitura) |
| [dados/origem-validada](dados/origem-validada) | Cópia pública da base normalizada |
| [docs/](docs) | Documentação em MkDocs |

## Avisos

- **O exercício de 2026 é parcial.** Ele cobre os dados disponíveis até a coleta de 07/11/2026.
- **Dados pessoais.** Na cópia pública, o campo `cpf_cnpj` de `emenda` está vazio e os identificadores encontrados em campos de texto estão mascarados. As chaves relacionais e as contagens foram preservadas. O `limpar.py` não aplica esse mascaramento, então **nunca grave a saída dele em `dados/origem-validada`**.
- **Não some `empenho` e `empenho_dotacao`.** As duas tabelas podem descrever a mesma despesa por ângulos diferentes. Veja [Fontes e limpeza](docs/fontes.md).
- **Credenciais.** A senha do banco fica só no arquivo `.env`, que está no `.gitignore`. Não commite esse arquivo nem compartilhe a `DATABASE_URL` fora da equipe.

## Pré-requisitos

| Ferramenta | Uso |
| --- | --- |
| Python 3.9 ou superior | Rodar o `limpar.py` e o MkDocs. O script usa só a biblioteca padrão. |
| MkDocs 1.6 ([requirements-docs.txt](requirements-docs.txt)) | Abrir a documentação localmente |
| Cliente `psql` (PostgreSQL Command Line Tools) | Aplicar o DDL, carregar e validar os dados |
| Projeto no Supabase (PostgreSQL 17) | Banco de destino |
| ZIP `despesas-criciuma-2023-a-2026.zip` | Opcional. Só é necessário para refazer a limpeza. |

## Instalação

Os comandos abaixo usam o PowerShell, na raiz do repositório.

1. Clone o repositório:

    ```powershell
    git clone https://github.com/02kamk/Trabalho_Final_Engenharia_de_Dados.git
    cd Trabalho_Final_Engenharia_de_Dados
    ```

2. Crie um ambiente virtual e instale as dependências da documentação:

    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements-docs.txt
    ```

3. Confirme que o `psql` está instalado:

    ```powershell
    psql --version
    ```

4. Configure a conexão com o banco. Copie o modelo e preencha a `DATABASE_URL` com a string do **Session pooler** do Supabase:

    ```powershell
    Copy-Item .env.example .env
    ```

    A criação do projeto no Supabase e os erros comuns na URL estão em [Banco de origem](docs/banco.md#passo-a-passo-da-implantacao).

5. Carregue a `DATABASE_URL` na sessão do terminal:

    ```powershell
    $env:DATABASE_URL = (Get-Content .env | Where-Object { $_ -like 'DATABASE_URL=*' }) -replace '^DATABASE_URL=', ''
    ```

## Como usar

### Criar o esquema e carregar os dados

Com a `DATABASE_URL` carregada, aplique o DDL e depois a carga. Os dois scripts rodam em uma única transação: se algo falhar, nada é gravado.

```powershell
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/origem.sql
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/carga_inicial.sql
```

A carga exige tabelas vazias. Uma chave repetida desfaz a transação inteira.

### Consultar os dados

Exemplo: quantidade de empenhos por exercício.

```powershell
psql --dbname="$env:DATABASE_URL" -X -c "SELECT ano, count(*) AS empenhos FROM origem.empenho GROUP BY ano ORDER BY ano;"
```

### Refazer a limpeza a partir do ZIP

Indique o ZIP da coleta e um diretório de saída que ainda não exista:

```powershell
python src/limpar.py "C:\caminho\despesas-criciuma-2023-a-2026.zip" dados/regerada
```

O script grava os CSVs e o banco local `origem.sqlite3` e imprime as contagens por tabela e exercício. A saída contém CPF e CNPJ sem máscara e fica fora do Git.

### Abrir a documentação

```powershell
python -m mkdocs serve
```

A documentação fica em http://127.0.0.1:8000.

## Testes

O projeto não tem testes automatizados de unidade. A integridade dos dados é conferida em dois pontos.

**Na limpeza.** O `limpar.py` verifica as chaves primárias e estrangeiras em SQLite antes de exportar. Se encontrar uma chave repetida com conteúdo diferente ou uma chave órfã, ele interrompe o processamento.

**Depois da carga.** O [sql/validacao_carga.sql](sql/validacao_carga.sql) só faz leitura:

```powershell
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/validacao_carga.sql
Remove-Item Env:DATABASE_URL
```

Ele mostra quatro conferências, cada uma com `OK` ou o tipo de problema:

1. Contagem de linhas de cada tabela contra o número de registros do CSV.
2. Registros órfãos em cada uma das 25 chaves estrangeiras. O esperado é 0.
3. Chaves e restrições no catálogo do PostgreSQL, todas validadas.
4. Linhas por exercício, para comparar com [Validação](docs/validacao.md).

O resultado da carga de 11/11/2026 está em [Verificação da carga no Supabase](docs/banco.md#verificacao-da-carga-no-supabase).

## Documentação

A documentação completa começa em [docs/index.md](docs/index.md):

- [Fontes e limpeza](docs/fontes.md): relatórios usados, critérios de limpeza e reprodução.
- [Validação](docs/validacao.md): contagens e cobertura por exercício.
- [Modelagem](docs/modelagem.md): diagrama e decisões de normalização.
- [Banco de origem](docs/banco.md): Supabase, carga e verificações.
