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
    return criar_engine(cfg, "sqlite:///:memory:")


@pytest.fixture
def engine_arquivo(cfg: ConfiguracaoBanco, tmp_path) -> EngineSQLite:
    caminho = tmp_path / "teste_nutricasa2050.db"
    return criar_engine(cfg, f"sqlite:///{caminho}")
