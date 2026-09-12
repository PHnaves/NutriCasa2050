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
