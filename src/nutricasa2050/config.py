import os

# Valores iguais aos do .env.example: rodar sem exportar nada ainda funciona.
DEFAULT_DB_URL = os.environ.get("NUTRICASA2050_DB_URL")
DEFAULT_TEST_DB_URL = os.environ.get("NUTRICASA2050_TEST_DB_URL")


def environment() -> str:
    return os.environ.get("NUTRICASA2050_ENVIRONMENT", "development")


def database_path() -> str:
    if environment() == "test":
        url = os.environ.get("NUTRICASA2050_TEST_DB_URL", DEFAULT_TEST_DB_URL)
    else:
        url = os.environ.get("NUTRICASA2050_DB_URL", DEFAULT_DB_URL)
    # Tres barras viram caminho relativo, quatro viram absoluto: cortar o
    # prefixo resolve os dois casos de uma vez.
    return url.removeprefix("sqlite:///")


def solver_tempo_limite() -> int:
    # Era 30s (S2-09); baixado para 10s no S4-05 depois de medir que, com
    # os 4 membros reais, o CBC as vezes passava dos 30s de PAREDE so por
    # overhead de escrever/ler arquivo, mesmo com timeLimit=30 — e porque
    # rodar 500 cenarios (card S4-04) com 30s cada levaria horas. Para
    # lotes grandes, sobrescreva com um valor ainda menor (ex.: 2) via
    # esta variavel — ver Makefile, alvo `resultados`.
    return int(os.environ.get("NUTRICASA2050_SOLVER_TIMEOUT", "10"))


def solver_caminho_binario() -> str | None:
    # Vazio ou ausente usa o CBC embutido do PuLP. Troque so esta variavel
    # para apontar para outro binario (ou outro solver) sem tocar no resto.
    return os.environ.get("NUTRICASA2050_SOLVER_PATH") or None
