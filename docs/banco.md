# Banco de origem no Supabase

O DDL `sql/origem.sql` cria 15 tabelas no esquema `origem` em uma transação. As listagens com ID do portal usam exercício e ID como chave primária. A dotação usa uma chave derivada do conteúdo. Seus detalhes usam exercício, dotação e número do item. Chaves estrangeiras ligam os registros às dimensões e os detalhes às dotações.

1. Crie o projeto na organização Supabase da equipe e convide os integrantes.
2. Copie `.env.example` para `.env`. Em **Connect**, copie a conexão PostgreSQL direta ou selecione **Session pooler** para rede IPv4. Preencha `DATABASE_URL` localmente e mantenha SSL habilitado.
3. Gere os CSVs em `dados/origem-validada`. Na raiz, com `psql` instalado, execute os comandos abaixo.

```powershell
$env:DATABASE_URL = (Get-Content .env | Where-Object { $_ -like 'DATABASE_URL=*' }) -replace '^DATABASE_URL=', ''
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/origem.sql
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/carga_inicial.sql
Remove-Item Env:DATABASE_URL
```

Use a carga inicial em tabelas vazias, com arquivos gerados na mesma execução da limpeza. A carga é transacional e chaves duplicadas provocam reversão. Mantenha o esquema fora da lista de esquemas expostos pela Data API. A carga inclui identificadores de favorecidos das emendas.

A integridade relacional foi verificada localmente. Para inspecionar a base materializada, abra `origem.sqlite3`, gerado na pasta de saída pela limpeza. No Supabase, o provisionamento, os convites e a aplicação do DDL continuam pendentes.

[Conexões PostgreSQL no Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres)
