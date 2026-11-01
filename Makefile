# ---------------------------------------------------------------------------
# NutriCasa 2050 — atalhos de linha de comando.
#
# "make dev" e "make test" so chamam o que o docker-compose.yml ja sabe
# fazer (ver os comentarios la) — nao existia Makefile ate o Sprint 4
# (ver card S2-13); criado agora porque o card S4-04 pede um atalho
# `make resultados` para a simulacao Monte Carlo.
# ---------------------------------------------------------------------------

.PHONY: dev test lint resultados

dev:
	docker compose up

test:
	docker compose --profile tools run --rm tests

lint:
	ruff check src tests

# Card S4-04/S4-05: roda a simulacao Monte Carlo (500 cenarios por
# padrao). NUTRICASA2050_SOLVER_TIMEOUT mais agressivo que o padrao do
# config.py — necessario para os 500 cenarios rodarem num tempo
# razoavel (ver docs/resultados.md, secao S4-05, para a conta completa).
resultados:
	NUTRICASA2050_SOLVER_TIMEOUT=2 PYTHONPATH=src python -m nutricasa2050.simulacao.monte_carlo --n 500 --horizonte 5
