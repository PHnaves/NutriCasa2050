# Como rodar o NutriCasa2050

Duas formas de rodar o projeto: **com Docker** (mais simples, é exatamente o que
o CI usa) ou **sem Docker** (Python local, mais rápido para iterar, mas você
mesmo cuida das dependências de sistema). Escolha uma — não precisa das duas.

## 0. Estado atual do projeto

O projeto está completo até o Sprint 5: modelo de otimização, simulação Monte
Carlo, análise, tela em Streamlit e CI. Os arquivos que este guia menciona
(`requirements.txt`, `pyproject.toml`, `app.py`, `data/`, `tests/`) existem
todos. Se um comando falhar, é problema de ambiente (Python, Docker, porta) —
veja a seção 6.

## 1. Antes de tudo (vale para os dois caminhos)

```bash
git clone <url-do-repo>
cd NutriCasa2050
cp .env.example .env
```

O `.env` é o seu arquivo local de variáveis de ambiente — nunca vai para o Git
(está no `.gitignore`). Detalhes de cada variável estão comentados no próprio
`.env.example`.

## 2. Rodando com Docker (recomendado)

Pré-requisito: [Docker](https://docs.docker.com/get-docker/) com o plugin
Compose (`docker compose version` para conferir).

### Subir o app

```bash
docker compose up --build
```

Abre em **http://localhost:8501**. O `--build` só é necessário na primeira vez
ou depois de mudar `Dockerfile`/`requirements.txt` — no dia a dia, `docker
compose up` sozinho já basta.

O código (`src/`, `app.py`, `data/`, `tests/`) é montado como volume: editar um
arquivo no seu editor reflete no container na hora, sem rebuild. Rebuild só é
necessário quando muda dependência (`requirements.txt`) ou o próprio
`Dockerfile`.

> **Nota:** quando o app roda via `docker compose`, os valores de
> `NUTRICASA2050_DB_URL` etc. vêm do bloco `environment:` do
> `docker-compose.yml` (caminhos absolutos, tipo `/app/var/...`) — **não** do
> seu `.env`. O `.env` local só é lido de fato no caminho sem Docker (seção 3).

### Rodar os testes

O serviço de testes tem `profile: tools`, então ele **não** sobe junto com
`docker compose up` — precisa ser chamado explicitamente:

```bash
docker compose --profile tools run --rm tests
```

Isso builda (se preciso), roda `ruff check` + `pytest` dentro de um banco de
teste isolado, e remove o container ao final (`--rm`). O código de saída reflete
se passou ou não — útil para colar num script.

### Abrir um terminal dentro do container

Com o `app` já rodando (`docker compose up` em outro terminal):

```bash
docker compose exec app bash
```

Sem precisar do serviço já estar de pé:

```bash
docker compose run --rm app bash
```

### Parar

```bash
docker compose down
```

Isso para e remove os containers, **mas mantém os volumes** (os bancos SQLite
continuam guardados). Para apagar os dados também (recomeçar do zero):

```bash
docker compose down -v
```

⚠️ `-v` apaga os dois bancos (principal e teste) permanentemente — use com
cuidado.

## 3. Rodando sem Docker (Python local)

Pré-requisitos:

- Python 3.11
- O solver **CBC**, instalado no sistema operacional (dentro do Docker isso é
  automático via `apt-get`; local, você instala uma vez):

  ```bash
  # Ubuntu / Debian
  sudo apt-get install coinor-cbc

  # macOS (Homebrew)
  brew install cbc

  # Windows
  # mais simples usar o Docker (seção 2) ou rodar dentro do WSL2
  ```

### Passo a passo

```bash
# 1. Criar e ativar um ambiente virtual
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt -r requirements-dev.txt

# 3. Instalar o proprio projeto em modo editavel
pip install -e . --no-deps

# 4. Carregar as variaveis do .env na sessao do terminal
export $(grep -v '^#' .env | xargs)

# 5. Rodar o app
streamlit run app.py
```

Abre em **http://localhost:8501**, igual ao caminho com Docker.

O passo 4 (`export ...`) precisa ser repetido a cada terminal novo, porque é só
uma variável de shell — não é mágica automática do Python. Se preferir não
repetir isso toda hora, dá pra adicionar a lib `python-dotenv` ao
`requirements.txt` e chamar `load_dotenv()` no início do `app.py`, que lê o
`.env` sozinho; isso é uma escolha de código, não algo que este guia decide por
você.

### Rodar os testes (sem Docker)

```bash
NUTRICASA2050_ENVIRONMENT=test pytest
ruff check src tests
```

Aqui é só isso — sobrescrever a variável de ambiente na hora do comando garante
que o `pytest` nunca acaba usando o banco principal por engano, mesmo que o
`.env` esteja configurado como `development`.

## 4. Sobre os bancos SQLite

O projeto usa dois arquivos SQLite (principal e teste), escolhidos pela
variável `NUTRICASA2050_ENVIRONMENT`. Como conectar, criar tabelas e por que
existem dois bancos separados está todo explicado em [SQLITE.md](SQLITE.md) —
esse aqui é só sobre *como subir o projeto*, não sobre o banco em si.

## 5. Onde ver isso funcionando "de verdade"

O workflow `.github/workflows/ci.yml` roda, a cada push, basicamente os mesmos
comandos da seção 2 (build da imagem, lint, testes, e um teste de que o
container sobe e responde). Se algo aqui parecer não bater, o CI é a referência
mais atualizada.

## 6. Problemas comuns

- **`port is already allocated` / porta 8501 em uso** — outro processo (ou
  outro container) já está usando a porta. Pare o outro processo, ou mude o
  mapeamento em `docker-compose.yml` (ex: `"8502:8501"`) e acesse pela nova
  porta.
- **`coinor-cbc: command not found` / solver indisponível** (só no caminho sem
  Docker) — o CBC não foi instalado no sistema; veja os comandos de instalação
  na seção 3.
- **`permission denied` ao rodar `docker`** (Linux) — seu usuário não está no
  grupo `docker`; rode com `sudo` ou adicione o usuário ao grupo
  (`sudo usermod -aG docker $USER`, depois relogar).
- **Editei o código mas o app não atualizou (Docker)** — confirme que o
  container `app` está de pé via `docker compose up` (não um `run` avulso) e
  que o arquivo editado está dentro de uma das pastas montadas
  (`src/`, `app.py`, `data/`, `tests/`).
- **Quero apagar os bancos e recomeçar do zero** — com Docker:
  `docker compose down -v` (apaga os dois volumes). Sem Docker: apague os
  arquivos `var/*.db` / `var-test/*.db` diretamente.
