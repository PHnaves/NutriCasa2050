from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from nutricasa2050.persistencia.schema import (
    ORDEM_LIMPEZA_DADOS,
    SQL_CRIAR_INDICES,
    SQL_CRIAR_TABELAS,
    TABELAS,
)


class ErroDeBanco(RuntimeError):
    """Erros de seguranca e operacao da camada de persistencia."""


@dataclass(frozen=True)
class ConfiguracaoBanco:
    ambiente: str
    url_banco_principal: str
    url_banco_teste: str


@dataclass
class EngineSQLite:
    url: str
    caminho: str
    uri: bool = False
    conexao_compartilhada: sqlite3.Connection | None = None


def _url_eh_sqlite(url: str) -> bool:
    return url.startswith("sqlite:///")


def _caminho_sqlite(url: str) -> str:
    if not _url_eh_sqlite(url):
        raise ErroDeBanco(f"URL de banco nao suportada: {url}")

    return url.removeprefix("sqlite:///")


def _normalizar_sqlite_url(url: str) -> str:
    if not _url_eh_sqlite(url):
        return url.strip()

    caminho = _caminho_sqlite(url)
    if caminho == ":memory:":
        return "sqlite:///:memory:"

    return f"sqlite:///{Path(caminho).resolve()}"


def _validar_isolamento(cfg: ConfiguracaoBanco, url: str) -> None:
    if cfg.ambiente != "test":
        return

    if _normalizar_sqlite_url(url) == _normalizar_sqlite_url(cfg.url_banco_principal):
        raise ErroDeBanco(
            "Ambiente de teste nao pode usar a URL do banco principal. "
            "Revise NUTRICASA2050_TEST_DB_URL."
        )


def criar_engine(cfg: ConfiguracaoBanco, url: str) -> EngineSQLite:
    _validar_isolamento(cfg, url)

    if not _url_eh_sqlite(url):
        raise ErroDeBanco("A camada de persistencia suporta apenas SQLite.")

    caminho = _caminho_sqlite(url)
    if caminho == ":memory:":
        caminho_uri = "file:nutricasa2050_memoria?mode=memory&cache=shared"
        conexao_compartilhada = sqlite3.connect(caminho_uri, uri=True, check_same_thread=False)
        _configurar_pragmas(conexao_compartilhada)
        return EngineSQLite(
            url=url,
            caminho=caminho_uri,
            uri=True,
            conexao_compartilhada=conexao_compartilhada,
        )

    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    return EngineSQLite(url=url, caminho=caminho)


def _configurar_pragmas(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")


def _abrir_conexao(engine: EngineSQLite) -> tuple[sqlite3.Connection, bool]:
    if engine.conexao_compartilhada is not None:
        return engine.conexao_compartilhada, False

    conn = sqlite3.connect(engine.caminho, check_same_thread=False, uri=engine.uri)
    _configurar_pragmas(conn)
    return conn, True


def criar_schema(engine: EngineSQLite) -> None:
    with conexao(engine) as conn:
        for sql in SQL_CRIAR_TABELAS:
            conn.execute(sql)
        for sql in SQL_CRIAR_INDICES:
            conn.execute(sql)


def apagar_schema(engine: EngineSQLite) -> None:
    with conexao(engine) as conn:
        for tabela in reversed(TABELAS):
            conn.execute(f"DROP TABLE IF EXISTS {tabela}")


def limpar_dados(engine: EngineSQLite) -> None:
    with conexao(engine) as conn:
        for tabela in ORDEM_LIMPEZA_DADOS:
            conn.execute(f"DELETE FROM {tabela}")


@contextmanager
def conexao(engine: EngineSQLite):
    conn, deve_fechar = _abrir_conexao(engine)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if deve_fechar:
            conn.close()
