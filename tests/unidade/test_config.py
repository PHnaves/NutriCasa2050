from nutricasa2050.config import database_path, environment


def test_ambiente_de_teste_usa_o_banco_de_teste(monkeypatch):
    monkeypatch.setenv("NUTRICASA2050_ENVIRONMENT", "test")
    monkeypatch.setenv("NUTRICASA2050_TEST_DB_URL", "sqlite:///var-test/x.db")

    assert environment() == "test"
    assert database_path() == "var-test/x.db"


def test_quatro_barras_continuam_sendo_caminho_absoluto(monkeypatch):
    monkeypatch.setenv("NUTRICASA2050_ENVIRONMENT", "test")
    monkeypatch.setenv("NUTRICASA2050_TEST_DB_URL", "sqlite:////app/var-test/x.db")

    assert database_path() == "/app/var-test/x.db"
