# ---------------------------------------------------------------------------
# NutriCasa 2050 — atalhos de linha de comando.
#
# "make dev" e "make test" so chamam o que o docker-compose.yml ja sabe
# fazer (ver os comentarios la) — nao existia Makefile ate o Sprint 4
# (ver card S2-13); criado agora porque o card S4-04 pede um atalho
# `make resultados` para a simulacao Monte Carlo.
# ---------------------------------------------------------------------------

.PHONY: dev test lint resultados publicar-resultados

# Muitas maquinas (Ubuntu, por exemplo) so tem `python3`. Sobrescreva se
# precisar: make resultados PYTHON=python
PYTHON ?= python3

dev:
	docker compose up

test:
	docker compose --profile tools run --rm tests

lint:
	ruff check src tests app.py

# Card S4-04, refeito no Sprint 6: a rodada que gerou os numeros oficiais
# (100 cenarios, tempo limite 30 s, ~55 min). O antigo "500 cenarios com
# 2 s" era invalido: com 2 s o CBC quase nunca acha solucao INTEIRA e o
# solver agora descarta a relaxacao linear (ver docs/resultados.md, topo).
# Mude N/TIMEOUT na linha de comando: make resultados N=500 TIMEOUT=30
N ?= 100
TIMEOUT ?= 30
resultados:
	NUTRICASA2050_SOLVER_TIMEOUT=$(TIMEOUT) PYTHONPATH=src $(PYTHON) -m nutricasa2050.simulacao.monte_carlo --n $(N) --horizonte 5 --orcamento 500

# Copia o banco principal para var/results.db — o unico .db versionado,
# lido pela aba "Resultados da simulacao" do app hospedado.
publicar-resultados:
	cp var/nutricasa2050.db var/results.db
