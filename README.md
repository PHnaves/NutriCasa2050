# NutriCasa 2050

[![ci](https://github.com/PHnaves/NutriCasa2050/actions/workflows/ci.yml/badge.svg)](https://github.com/PHnaves/NutriCasa2050/actions/workflows/ci.yml)

Simulação NutriCasa 2050 — app em Streamlit com otimização linear (PuLP) e
persistência em SQLite.

## Começando

```bash
cp .env.example .env
docker compose up --build      # http://localhost:8501
```

Sem Docker, ou para entender cada passo, veja o guia completo em
[docs/RODANDO.md](docs/RODANDO.md).

## Documentação

- [docs/RODANDO.md](docs/RODANDO.md) — como rodar o projeto, com e sem Docker.
- [docs/SQLITE.md](docs/SQLITE.md) — como o SQLite funciona neste projeto:
  conexão, criação de tabelas e por que existem dois bancos separados.
- [docs/formulacao.md](docs/formulacao.md) — a formulação matemática do
  problema de otimização: conjuntos, parâmetros, variáveis, função objetivo
  e as doze restrições.

## Estrutura

```
app.py              entrypoint do Streamlit
src/nutricasa2050/  o pacote Python (o codigo de verdade mora aqui)
tests/              testes do pytest
data/               dados de entrada
var/                banco SQLite principal (arquivos .db nao vao para o Git)
var-test/           banco SQLite de teste, descartavel
docs/               documentacao
```

## Desenvolvimento

### Rodar os testes

```bash
docker compose --profile tools run --rm tests
```

Cada pedaço do comando:

- **`--profile tools`** — o serviço `tests` está marcado com o perfil `tools`,
  que é o que o mantém fora do `docker compose up`. Passar o perfil
  explicitamente é o que faz o Compose enxergá-lo.
- **`run`** — cria um container novo só para esta execução. É diferente de
  `exec`, que entra num container que já está de pé.
- **`--rm`** — apaga esse container ao terminar, em vez de deixar o cadáver
  acumulando na lista do `docker ps -a`.
- **`tests`** — o nome do **serviço** no `docker-compose.yml`. Os serviços aqui
  são `app` e `tests`; `nutricasa-app` e `nutricasa2050-tests` são nomes de
  *container*, que o `docker compose` não entende.

O serviço executa `ruff check src tests && pytest`: primeiro o lint, depois os
testes. Como é `&&`, um erro de estilo interrompe tudo antes de qualquer teste
rodar — é proposital, mas vale saber quando nenhum resultado de teste aparecer
na tela. O código de saída reflete o resultado, então o comando serve direto
num script.

O isolamento é o motivo de existir um segundo serviço: ele sobe com
`NUTRICASA2050_ENVIRONMENT=test` e monta **apenas** o volume do banco de teste.
O banco principal não está montado ali — um teste mal escrito não tem como
alcançá-lo. Por isso não use `docker compose exec app pytest`: funciona, mas
roda dentro do container de desenvolvimento, com o banco principal montado.

Para passar argumentos ao pytest, basta acrescentar o comando no final, que
substitui o padrão do serviço (e, com ele, o passo do ruff):

```bash
docker compose --profile tools run --rm tests pytest -k config -vv
```

### Ciclo rápido, sem Docker

Subir um container a cada rodada custa alguns segundos — pouco antes de um
commit, muito quando se está escrevendo teste atrás de teste. Com o ambiente
virtual montado (seção 3 do [RODANDO.md](docs/RODANDO.md)), o retorno é
imediato:

```bash
NUTRICASA2050_ENVIRONMENT=test pytest
ruff check src tests
```

Definir a variável na própria linha do comando garante o banco de teste mesmo
que o seu `.env` esteja em `development`.

A recomendação prática é usar os dois: o caminho sem Docker enquanto o código
está sendo escrito, e o serviço `tests` antes de publicar — é ele que reproduz
o ambiente que o CI vai usar.

### Integração contínua

O CI roda `ruff check src tests` e `pytest` a cada push na `main` e em todo pull
request, e ainda constrói a imagem Docker para conferir que o solver CBC
funciona dentro dela (`.github/workflows/ci.yml`).
