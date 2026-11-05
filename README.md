# NutriCasa 2050

[![ci](https://github.com/PHnaves/NutriCasa2050/actions/workflows/ci.yml/badge.svg)](https://github.com/PHnaves/NutriCasa2050/actions/workflows/ci.yml)

Planeja a semana de comida de uma família como um problema de otimização:
dado o que há na despensa, o orçamento, o tempo de cozinha e a dieta de cada
pessoa, escolhe o cardápio, as porções e a lista de compras de menor custo
e **menor desperdício**. Ninguém programa "use primeiro o que vence antes" —
o modelo faz isso sozinho, porque jogar comida fora custa dinheiro.

Feito em Python com programação linear inteira mista
([PuLP](https://coin-or.github.io/pulp/) + solver CBC), interface em
Streamlit e resultados guardados em SQLite.

> **App publicado:** ainda não há link público. A publicação no Streamlit
> Cloud depende de autorização da coordenação para tornar o repositório
> público (card S5-08). O caminho garantido é a imagem Docker abaixo.

## Como rodar

### 1. Com Docker (recomendado — é exatamente o que o CI usa)

Pré-requisito: [Docker](https://docs.docker.com/get-docker/) com o plugin
Compose (`docker compose version` para conferir) e `make`.

```bash
git clone https://github.com/PHnaves/NutriCasa2050.git
cd NutriCasa2050
cp .env.example .env
make dev                       # = docker compose up   →  http://localhost:8501
```

Sem `make`: `docker compose up --build`.

### 2. Sem Docker (Python local)

Pré-requisito: **Python 3.11**. O CBC já vem embutido no PuLP; se ele falhar
na sua máquina, instale o do sistema (`sudo apt-get install coinor-cbc` no
Ubuntu, `brew install cbc` no macOS).

```bash
python3.11 -m venv .venv
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e . --no-deps
streamlit run app.py                       # →  http://localhost:8501
```

Detalhes e solução de problemas em [docs/RODANDO.md](docs/RODANDO.md).

### 3. A imagem publicada (um comando, sem clonar nada)

Cada versão marcada com tag (`git tag vX.Y && git push --tags`) é publicada
no GitHub Container Registry pelo workflow `.github/workflows/publicar.yml`:

```bash
docker run -p 8501:8501 ghcr.io/phnaves/nutricasa2050:latest
```

## Os dois bancos de dados

São **dois arquivos SQLite separados, de propósito**: rodar os testes nunca
pode apagar nem sujar os resultados da simulação de verdade.

| | Principal | Teste |
|---|---|---|
| Para que serve | simulação e app | `pytest` (descartável) |
| Variável de ambiente | `NUTRICASA2050_DB_URL` | `NUTRICASA2050_TEST_DB_URL` |
| Caminho no `.env.example` | `sqlite:///var/nutricasa2050.db` | `sqlite:///var-test/nutricasa2050_test.db` |
| Caminho no Docker | `/app/var/nutricasa2050.db` | `/app/var-test/nutricasa2050_test.db` |
| Volume Docker | `nutricasa2050` | `nutricasa2050_test` |
| Qual é usado | `NUTRICASA2050_ENVIRONMENT=development` | `NUTRICASA2050_ENVIRONMENT=test` |

Três barras = caminho relativo; quatro = absoluto. O serviço `tests` do
Compose **não monta** o volume do banco principal — um teste mal escrito não
tem como alcançá-lo. Guia completo em [docs/SQLITE.md](docs/SQLITE.md).

## Estrutura de pastas

```
app.py                       a tela (Streamlit) — só liga widgets a funções de src/
src/nutricasa2050/
  dominio.py                 dataclasses: Ingrediente, Receita, Membro, Lote, Catalogo, Parametros...
  dados/                     leitura e validação dos CSV/JSON de data/
  otimizacao/                o modelo: variaveis.py, restricoes.py (R1–R12), objetivo.py, modelo.py, solver.py
  serializacao.py            Solucao → dicionário simples (formato único de tela, banco e gráficos)
  persistencia/              SQLite: esquema, conexão, gravar/ler resultados
  simulacao/                 cenários, baselines (humano e guloso) e Monte Carlo
  analise/                   consultas SQL, preço-sombra, gráficos, grafo de ingredientes
data/                        dados de entrada (ingredientes, receitas, matriz A, estoque, perfis)
tests/                       unidade/ e integracao/ (pytest)
notebooks/                   00_stigler (protótipo) e 01_analise (todos os gráficos e consultas)
docs/                        formulação, relatório, resultados, guias
var/  var-test/              bancos SQLite (arquivos .db não vão para o Git)
figures/                     gráficos gerados (não vão para o Git)
```

## As doze restrições

Detalhe completo — o que cada uma faz **e o que acontece se ela sair** — em
[docs/formulacao.md](docs/formulacao.md). Cada uma é uma função em
`src/nutricasa2050/otimizacao/restricoes.py` com o número no nome.

| Bloco | Restrição | Em uma frase |
|---|---|---|
| **A — Cardápio** | R1 cobertura | cada pessoa come exatamente uma porção por refeição |
| | R2 vínculo | ninguém come de um prato que não foi cozinhado |
| | R3 limite de pratos | no máximo 2 pratos por refeição |
| | R4 variedade | nenhuma receita mais de 2× na semana, nem em dias seguidos |
| **B — Nutrição** | R5 faixas com folga | nutrientes dentro da faixa de cada pessoa, com válvula de escape |
| | R6 restrição individual | tag proibida para uma pessoa não vai para o prato dela (mas pode ir para os outros) |
| | R7 desvio do alvo | mede a distância do valor prescrito (valor absoluto linearizado) |
| **C — Estoque** | R8 consumo derivado | liga o que se come ao que sai da despensa |
| | R9 balanço por lote | estoque de hoje = ontem + chegada − consumo − descarte |
| | R10 validade | não se come o vencido; o que vence sai por descarte (**o coração do projeto**) |
| **D — Operacional** | R11 tempo de preparo | o tempo de cozinha do dia cabe no tempo disponível |
| | R12 orçamento | o gasto com compras não passa do orçamento |

## Base acadêmica

O ponto de partida é o **problema da dieta de Stigler (1945)**: escolher, entre
77 alimentos, a combinação de menor custo que atenda 9 nutrientes — a origem
histórica da programação linear (resolvido depois pelo método simplex). O
protótipo está em [`notebooks/00_stigler.ipynb`](notebooks/00_stigler.ipynb).
O NutriCasa acrescenta **três dimensões** que o problema original não tinha:

1. **Tempo** — restrição e custo de preparo (R11).
2. **Perecibilidade** — lotes com validade e descarte (R9, R10).
3. **Heterogeneidade** — cada pessoa com sua faixa, porção e restrições (R5–R7).

## Documentação

- [docs/formulacao.md](docs/formulacao.md) — a formulação matemática completa
  (conjuntos, variáveis, objetivo, as 12 restrições) como foi implementada.
- [docs/relatorio.md](docs/relatorio.md) — relatório final.
- [docs/resultados.md](docs/resultados.md) — números e achados de cada sprint:
  desempenho, redução de desperdício, economia, preço da prescrição.
- [docs/RODANDO.md](docs/RODANDO.md) — como rodar, com e sem Docker.
- [docs/SQLITE.md](docs/SQLITE.md) — como o SQLite funciona neste projeto.
- [docs/premissas.md](docs/premissas.md) e [docs/fontes.md](docs/fontes.md) —
  perfis da família, padrão de cadastro e fontes das validades.

## Desenvolvimento

### Rodar os testes

```bash
make test                    # = docker compose --profile tools run --rm tests
```

O serviço executa `ruff check src tests app.py && pytest`: primeiro o lint,
depois os testes (um erro de estilo interrompe tudo antes de qualquer teste —
é proposital). Ele sobe com `NUTRICASA2050_ENVIRONMENT=test` e monta **apenas**
o volume do banco de teste. Por isso não use `docker compose exec app pytest`:
funciona, mas roda com o banco principal montado.

Ciclo rápido, sem Docker (com o ambiente virtual da seção 2):

```bash
NUTRICASA2050_ENVIRONMENT=test pytest
ruff check src tests app.py
```

Alguns testes usam o catálogo real completo e levam alguns segundos cada
(`@pytest.mark.lento`); para pular: `pytest -m "not lento"`.

### Reproduzir os números do projeto

```bash
make resultados              # Monte Carlo: 500 cenários × 3 estratégias → banco principal
pip install jupyter          # só para abrir/rodar o notebook; não faz parte do requirements
jupyter nbconvert --to notebook --execute notebooks/01_analise.ipynb   # todos os gráficos e consultas
```

### Como contribuir

1. **Branch próprio** para cada card (`feat/...`); nada vai direto para a `main`.
2. **O teste vai no mesmo PR** que o código — sem teste, o PR não está pronto.
3. **Quem escreveu não aprova**: outra pessoa do grupo revisa e aprova.
4. Antes de abrir o PR: `make lint` e `make test` verdes.
5. Mudou uma restrição? Atualize a docstring "o que faz / o que acontece se sair"
   e a seção correspondente de `docs/formulacao.md`.

### Integração contínua

A cada push na `main` e em todo pull request, o CI (`.github/workflows/ci.yml`)
roda dois jobs: **qualidade** (`ruff`, `pytest` e a validação do catálogo de
dados) e **container** (constrói a imagem Docker e prova que o solver resolve
um modelo *dentro* dela). O selo no topo mostra o estado atual.
