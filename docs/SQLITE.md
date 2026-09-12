# Guia de SQLite para o NutriCasa2050

Este documento existe porque o projeto usa SQLite e é a primeira vez que você mexe
nisso. A ideia é responder direto às perguntas práticas: como conectar, como criar
uma tabela, e como tudo isso se encaixa nos arquivos que já existem no repositório
(`.env.example`, `docker-compose.yml`, `Dockerfile`).

Como o projeto **não tem ambiente de produção**, este guia deliberadamente ignora
tudo que só faz sentido em produção (ferramentas de migração como Alembic, pool de
conexões, backups automatizados, etc.). Aqui o objetivo é o mínimo que funciona bem
para um app local/Streamlit.

## 1. O que é o SQLite, na prática

SQLite não é um "servidor de banco de dados" como Postgres ou MySQL. Não existe um
processo rodando esperando conexões numa porta. **O banco inteiro é um único
arquivo** no disco (ex: `nutricasa2050.db`). Quando seu código Python "conecta" no
banco, ele só está abrindo esse arquivo.

Consequências práticas:

- Não precisa instalar nem subir nenhum serviço de banco de dados. O suporte a
  SQLite já vem embutido no Python (módulo `sqlite3` da biblioteca padrão).
- "Fazer backup do banco" = copiar o arquivo `.db`.
- Só um processo por vez consegue *escrever* no arquivo (leituras concorrentes são
  ok). Isso é perfeitamente adequado para um app Streamlit local — não é
  adequado para um site com muitos usuários simultâneos escrevendo ao mesmo tempo,
  mas isso não é o seu caso.

## 2. Duas formas de falar com o SQLite em Python

### Opção A — `sqlite3` puro (biblioteca padrão, zero dependências)

```python
import sqlite3

conexao = sqlite3.connect("var/nutricasa2050.db")
cursor = conexao.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS simulacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        resultado REAL,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute(
    "INSERT INTO simulacao (nome, resultado) VALUES (?, ?)",
    ("cenario-1", 42.5),
)
conexao.commit()

cursor.execute("SELECT id, nome, resultado FROM simulacao")
for linha in cursor.fetchall():
    print(linha)

conexao.close()
```

Pontos importantes:

- `CREATE TABLE IF NOT EXISTS` é o suficiente para "criar o banco" — não existe um
  comando separado para criar o arquivo `.db`; ele é criado sozinho na primeira
  conexão, e a tabela é criada (ou ignorada, se já existir) nesse `execute`.
- Sempre use `?` como placeholder nos valores (nunca formate a string manualmente
  com f-string) — isso evita SQL injection e também lida com aspas/tipos por você.
- `conexao.commit()` é obrigatório depois de `INSERT`/`UPDATE`/`DELETE`, senão a
  mudança fica só na transação aberta e não é gravada no arquivo.
- Prefira usar `with sqlite3.connect(...) as conexao:` quando possível — fecha a
  conexão automaticamente mesmo se der erro.

### Opção B — SQLAlchemy

O `.env.example` já usa o formato `sqlite:///var/nutricasa2050.db` — essa é
justamente a convenção de URL do **SQLAlchemy**, não do módulo `sqlite3` puro (que
só recebe um caminho de arquivo comum). Se pretende usar essa variável de ambiente
diretamente, faz sentido adicionar `sqlalchemy` ao `requirements.txt` e usar:

```python
from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///var/nutricasa2050.db")

with engine.begin() as conexao:  # begin() já dá commit/rollback automático
    conexao.execute(text("""
        CREATE TABLE IF NOT EXISTS simulacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            resultado REAL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conexao.execute(
        text("INSERT INTO simulacao (nome, resultado) VALUES (:nome, :resultado)"),
        {"nome": "cenario-1", "resultado": 42.5},
    )

with engine.connect() as conexao:
    resultado = conexao.execute(text("SELECT id, nome, resultado FROM simulacao"))
    for linha in resultado:
        print(linha)
```

**Se você não tem preferência, use a Opção A (`sqlite3` puro).** É uma dependência
a menos, e para duas tabelas num projeto sem produção não traz benefício real usar
SQLAlchemy. Só vale a pena se você já sabe que vai crescer para várias tabelas
relacionadas e quer o ORM. O resto deste guia funciona com qualquer uma das duas —
o que muda é só a sintaxe de conexão.

## 3. O formato `sqlite:///` explicado (3 barras vs 4 barras)

Isso já está comentado no `docker-compose.yml`, mas para reforçar:

```
sqlite:///caminho/relativo.db     -> 3 barras = caminho relativo ao diretório atual
sqlite:////caminho/absoluto.db    -> 4 barras = caminho absoluto (começa em "/")
```

O `.env.example` usa 3 barras (`sqlite:///var/nutricasa2050.db`, relativo, pensado
para rodar `python app.py` direto na sua máquina). Já o `docker-compose.yml` usa 4
barras (`sqlite:////app/var/nutricasa2050.db`, absoluto, porque dentro do container
o caminho sempre começa em `/app`). Essa string é só uma convenção — se você usar
`sqlite3` puro em vez de SQLAlchemy, seu código precisa remover o prefixo
`sqlite:///` (ou `sqlite:////`) antes de passar o caminho para `sqlite3.connect()`,
já que esse módulo espera só o caminho do arquivo, sem o prefixo.

## 4. Os dois bancos do projeto (principal e teste)

O projeto usa **dois arquivos `.db` completamente separados**, de propósito:

| Variável de ambiente         | Para que serve                          |
|-------------------------------|------------------------------------------|
| `NUTRICASA2050_DB_URL`        | banco principal, com dados "de verdade" |
| `NUTRICASA2050_TEST_DB_URL`   | banco descartável, usado pelo `pytest`  |

Isso existe para que rodar os testes nunca corrompa ou apague os resultados reais.
No código, a ideia é ler a variável de ambiente certa (dependendo de
`NUTRICASA2050_ENVIRONMENT`) para decidir qual arquivo abrir — nunca tenha o
caminho do banco escrito direto ("hardcoded") dentro do código.

Essa leitura já existe pronta no projeto, em
[`src/nutricasa2050/config.py`](../src/nutricasa2050/config.py):

```python
from nutricasa2050.config import database_path, environment

print(environment())      # "development" ou "test"
print(database_path())    # caminho do arquivo .db correspondente
```

O truque ali é que cortar só o prefixo `sqlite:///` já resolve os dois formatos
de uma vez: com 3 barras sobra `var/nutricasa2050.db` (relativo) e com 4 barras
sobra `/app/var/nutricasa2050.db` (absoluto, porque a quarta barra fica). Não
tente cortar a barra inicial "extra" — ela é justamente o que torna o caminho
absoluto dentro do container.

## 5. Onde os arquivos `.db` ficam de verdade (Docker)

Dentro do container, os bancos moram em `/app/var` (principal) e `/app/var-test`
(teste) — pastas criadas no `Dockerfile`. O `docker-compose.yml` monta essas pastas
como **volumes nomeados** (`database` e `database-test`), o que significa: mesmo
se você derrubar e recriar o container, o conteúdo do banco continua existindo
(fica guardado pelo Docker, fora do container). Se quiser apagar os dados de
verdade e recomeçar do zero: `docker volume rm nutricasa2050`.

Rodando fora do Docker (direto com `python app.py` na sua máquina), esses volumes
não existem — o banco simplesmente vai para a pasta relativa `var/` ou
`var-test/` no seu projeto, criada na hora se não existir.

## 6. Por que os `.db` não vão para o Git

Olhando o `.gitignore`, os arquivos `*.db` ficam de fora do controle de versão —
faz sentido, já que são dados gerados, não código, e podem crescer bastante. A
única exceção é `var/results.db`, que é versionado de propósito: é o banco lido
pela versão do app publicada na nuvem (ex: Streamlit Community Cloud), que não tem
como montar um volume persistente — então o arquivo precisa estar dentro do
repositório para o app hospedado conseguir lê-lo.

## 7. Inspecionar o conteúdo de um `.db` sem escrever código

Às vezes você só quer abrir o arquivo e olhar o que tem dentro, sem rodar Python.
Opções:

- **CLI que já vem com o SQLite** (se instalado no seu sistema):
  `sqlite3 var/nutricasa2050.db` e depois `.tables`, `.schema simulacao`,
  `SELECT * FROM simulacao;`.
- **Extensão do VS Code**: "SQLite Viewer" ou "SQLite" — abre o `.db` como uma
  tabela visual, sem precisar de terminal.
- **DB Browser for SQLite**: programa gráfico separado, útil se preferir uma
  interface tipo planilha.

## 8. Resumo do que você realmente precisa saber

1. Não existe "instalar o banco" — é só um arquivo, criado na primeira conexão.
2. `CREATE TABLE IF NOT EXISTS` no início do app já resolve a criação do schema;
   sem produção, não precisa de Alembic nem de scripts de migração.
3. Sempre use `?` (sqlite3) ou `:nome` (SQLAlchemy) para valores — nunca monte a
   query com f-string.
4. Não esqueça `commit()` (sqlite3 puro) ou use `engine.begin()` (SQLAlchemy) para
   commit automático.
5. Banco principal e banco de teste são arquivos diferentes de propósito — leia
   sempre a variável de ambiente certa, nunca fixe o caminho no código.
