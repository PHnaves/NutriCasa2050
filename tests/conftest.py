from __future__ import annotations

import os

import pytest

from nutricasa2050.persistencia.banco import ConfiguracaoBanco, EngineSQLite, criar_engine


@pytest.fixture(scope="session", autouse=True)
def forcar_ambiente_teste() -> None:
    os.environ["NUTRICASA2050_ENVIRONMENT"] = "test"
    os.environ["NUTRICASA2050_DB_URL"] = "sqlite:///var/nutricasa2050.db"
    os.environ["NUTRICASA2050_TEST_DB_URL"] = "sqlite:///var-test/nutricasa2050_test.db"


@pytest.fixture
def cfg() -> ConfiguracaoBanco:
    return ConfiguracaoBanco(
        ambiente=os.environ["NUTRICASA2050_ENVIRONMENT"],
        url_banco_principal=os.environ["NUTRICASA2050_DB_URL"],
        url_banco_teste=os.environ["NUTRICASA2050_TEST_DB_URL"],
    )


@pytest.fixture
def engine_memoria(cfg: ConfiguracaoBanco) -> EngineSQLite:
    # O banco de memoria usa "shared cache" (banco.py: criar_engine) para
    # permitir multiplas conexoes no mesmo :memory:. Isso so e descartado
    # quando a ULTIMA conexao fecha — sem fechar aqui, o SQLite mantem o
    # banco (e os dados) vivo entre testes ate o GC decidir coletar o
    # objeto antigo, o que e nao-deterministico (passa local, falha no CI).
    engine = criar_engine(cfg, "sqlite:///:memory:")
    yield engine
    if engine.conexao_compartilhada is not None:
        engine.conexao_compartilhada.close()


@pytest.fixture
def engine_arquivo(cfg: ConfiguracaoBanco, tmp_path) -> EngineSQLite:
    caminho = tmp_path / "teste_nutricasa2050.db"
    return criar_engine(cfg, f"sqlite:///{caminho}")
