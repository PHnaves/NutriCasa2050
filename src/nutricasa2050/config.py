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
    return int(os.environ.get("NUTRICASA2050_SOLVER_TIMEOUT", "30"))


def solver_caminho_binario() -> str | None:
    # Vazio ou ausente usa o CBC embutido do PuLP. Troque so esta variavel
    # para apontar para outro binario (ou outro solver) sem tocar no resto.
    return os.environ.get("NUTRICASA2050_SOLVER_PATH") or None
