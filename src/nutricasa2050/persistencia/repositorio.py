"""Grava o resultado de uma execucao do solver no banco (schema do S1-14) e
le de volta. gravar_resultado_completo roda tudo numa unica transacao: se
qualquer parte falhar, a funcao `conexao` do banco.py faz rollback e NADA
fica gravado — e o que o teste test_falha_no_meio_nao_grava_nada protege.
"""
from __future__ import annotations

import json
import sqlite3

from nutricasa2050.persistencia.banco import EngineSQLite, conexao


def gravar_cenario(engine: EngineSQLite, cenario: dict) -> int:
    with conexao(engine) as conn:
        return _inserir_cenario(conn, cenario)


def _inserir_cenario(conn: sqlite3.Connection, cenario: dict) -> int:
    cursor = conn.execute(
        """
        INSERT INTO cenario (rodada, semente, dados_sorteados)
        VALUES (?, ?, ?)
        """,
        (
            cenario.get("rodada", 0),
            cenario.get("semente", 0),
            json.dumps(cenario.get("dados_sorteados")) if cenario.get("dados_sorteados") else None,
        ),
    )
    return cursor.lastrowid


def gravar_execucao(
    engine: EngineSQLite,
    resultado: dict,
    estrategia: str,
    parametros: dict,
    cenario_id: int | None = None,
) -> int:
    with conexao(engine) as conn:
        if cenario_id is None:
            cenario_id = _inserir_cenario(conn, {})
        return _inserir_execucao(conn, resultado, estrategia, parametros, cenario_id)


def _inserir_execucao(
    conn: sqlite3.Connection,
    resultado: dict,
    estrategia: str,
    parametros: dict,
    cenario_id: int,
) -> int:
    resumo = resultado["resumo"]
    pesos = parametros.get("pesos", {})
    parametros_sem_pesos = {chave: valor for chave, valor in parametros.items() if chave != "pesos"}

    cursor = conn.execute(
        """
        INSERT INTO execucao (
            cenario_id, estrategia, parametros, pesos, status,
            tempo_ms, total_custo, total_descarte, total_preparo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cenario_id,
            estrategia,
            json.dumps(parametros_sem_pesos),
            json.dumps(pesos),
            resumo["status"],
            int(resumo["tempo_segundos"] * 1000),
            resumo["custo_total"],
            resumo["valor_desperdicio"],
            resumo["tempo_cozinha_minutos"],
        ),
    )
    return cursor.lastrowid


def gravar_cardapio(engine: EngineSQLite, execucao_id: int, cardapio: list[dict]) -> None:
    with conexao(engine) as conn:
        _inserir_cardapio(conn, execucao_id, cardapio)


def _inserir_cardapio(conn: sqlite3.Connection, execucao_id: int, cardapio: list[dict]) -> None:
    for item in cardapio:
        conn.execute(
            """
            INSERT INTO cardapio (execucao_id, dia, refeicao, prato, puxado_por_validade)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                execucao_id,
                item["dia"],
                item["refeicao"],
                item["receita_id"],
                1 if item.get("puxado_por_validade") else 0,
            ),
        )


def _buscar_cardapio_id(
    conn: sqlite3.Connection, execucao_id: int, dia: int, refeicao: str, prato: str
) -> int:
    linha = conn.execute(
        """
        SELECT id FROM cardapio
        WHERE execucao_id = ? AND dia = ? AND refeicao = ? AND prato = ?
        """,
        (execucao_id, dia, refeicao, prato),
    ).fetchone()
    if linha is None:
        raise ValueError(
            f"Nenhum cardapio gravado para execucao {execucao_id}, dia {dia}, "
            f"refeicao {refeicao}, prato {prato} — grave o cardapio antes das porcoes."
        )
    return linha["id"]


def gravar_porcoes(engine: EngineSQLite, execucao_id: int, porcoes: list[dict]) -> None:
    with conexao(engine) as conn:
        _inserir_porcoes(conn, execucao_id, porcoes)


def _inserir_porcoes(conn: sqlite3.Connection, execucao_id: int, porcoes: list[dict]) -> None:
    for item in porcoes:
        cardapio_id = _buscar_cardapio_id(
            conn, execucao_id, item["dia"], item["refeicao"], item["receita_id"]
        )
        conn.execute(
            "INSERT INTO porcao (cardapio_id, membro, quantidade) VALUES (?, ?, ?)",
            (cardapio_id, item["membro_id"], item["fracao"]),
        )


def gravar_compras(engine: EngineSQLite, execucao_id: int, compras: list[dict]) -> None:
    with conexao(engine) as conn:
        _inserir_compras(conn, execucao_id, compras)


def _inserir_compras(conn: sqlite3.Connection, execucao_id: int, compras: list[dict]) -> None:
    for item in compras:
        conn.execute(
            """
            INSERT INTO compra (execucao_id, ingrediente, quantidade, unidade, custo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                execucao_id,
                item["ingrediente_id"],
                item["quantidade"],
                item["unidade"],
                item["custo"],
            ),
        )


def gravar_descartes(engine: EngineSQLite, execucao_id: int, descartes: list[dict]) -> None:
    with conexao(engine) as conn:
        _inserir_descartes(conn, execucao_id, descartes)


def _inserir_descartes(conn: sqlite3.Connection, execucao_id: int, descartes: list[dict]) -> None:
    for item in descartes:
        conn.execute(
            """
            INSERT INTO descarte (execucao_id, ingrediente, lote, quantidade, motivo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                execucao_id,
                item["ingrediente_id"],
                item["lote_id"],
                item["quantidade"],
                item.get("motivo"),
            ),
        )


def gravar_aderencia(engine: EngineSQLite, execucao_id: int, aderencia: list[dict]) -> None:
    with conexao(engine) as conn:
        _inserir_aderencia(conn, execucao_id, aderencia)


def _inserir_aderencia(conn: sqlite3.Connection, execucao_id: int, aderencia: list[dict]) -> None:
    for item in aderencia:
        conn.execute(
            """
            INSERT INTO aderencia (
                execucao_id, dia, membro, regra, valor, minimo, maximo, alvo, desvio, folga
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execucao_id,
                item["dia"],
                item["membro_id"],
                item["nutriente"],
                item["valor"],
                item["minimo"],
                item["maximo"],
                item["alvo"],
                item["desvio"],
                item["folga"],
            ),
        )


def gravar_resultado_completo(
    engine: EngineSQLite,
    resultado: dict,
    estrategia: str,
    parametros: dict,
    cenario_id: int | None = None,
) -> int:
    with conexao(engine) as conn:
        if cenario_id is None:
            cenario_id = _inserir_cenario(conn, {})
        execucao_id = _inserir_execucao(conn, resultado, estrategia, parametros, cenario_id)
        _inserir_cardapio(conn, execucao_id, resultado["cardapio"])
        _inserir_porcoes(conn, execucao_id, resultado["porcoes"])
        _inserir_compras(conn, execucao_id, resultado["compras"])
        _inserir_descartes(conn, execucao_id, resultado["descartes"])
        _inserir_aderencia(conn, execucao_id, resultado["aderencia"])
        return execucao_id


def ler_execucao(engine: EngineSQLite, execucao_id: int) -> dict:
    with conexao(engine) as conn:
        execucao = conn.execute("SELECT * FROM execucao WHERE id = ?", (execucao_id,)).fetchone()
        if execucao is None:
            raise ValueError(f"Execucao {execucao_id} nao encontrada.")

        cardapio_rows = conn.execute(
            "SELECT * FROM cardapio WHERE execucao_id = ?", (execucao_id,)
        ).fetchall()
        porcao_rows = conn.execute(
            """
            SELECT porcao.*, cardapio.dia, cardapio.refeicao, cardapio.prato
            FROM porcao
            JOIN cardapio ON cardapio.id = porcao.cardapio_id
            WHERE cardapio.execucao_id = ?
            """,
            (execucao_id,),
        ).fetchall()
        compra_rows = conn.execute(
            "SELECT * FROM compra WHERE execucao_id = ?", (execucao_id,)
        ).fetchall()
        descarte_rows = conn.execute(
            "SELECT * FROM descarte WHERE execucao_id = ?", (execucao_id,)
        ).fetchall()
        aderencia_rows = conn.execute(
            "SELECT * FROM aderencia WHERE execucao_id = ?", (execucao_id,)
        ).fetchall()

    cardapio = [
        {
            "dia": row["dia"],
            "refeicao": row["refeicao"],
            "receita_id": row["prato"],
            "puxado_por_validade": bool(row["puxado_por_validade"]),
        }
        for row in cardapio_rows
    ]
    porcoes = [
        {
            "membro_id": row["membro"],
            "dia": row["dia"],
            "refeicao": row["refeicao"],
            "receita_id": row["prato"],
            "fracao": row["quantidade"],
        }
        for row in porcao_rows
    ]
    compras = [
        {
            "ingrediente_id": row["ingrediente"],
            "dia": None,
            "quantidade": row["quantidade"],
            "unidade": row["unidade"],
            "custo": row["custo"],
        }
        for row in compra_rows
    ]
    descartes = [
        {
            "lote_id": row["lote"],
            "ingrediente_id": row["ingrediente"],
            "quantidade": row["quantidade"],
            "motivo": row["motivo"],
        }
        for row in descarte_rows
    ]
    aderencia = [
        {
            "membro_id": row["membro"],
            "dia": row["dia"],
            "nutriente": row["regra"],
            "valor": row["valor"],
            "minimo": row["minimo"],
            "maximo": row["maximo"],
            "alvo": row["alvo"],
            "desvio": row["desvio"],
            "folga": row["folga"],
        }
        for row in aderencia_rows
    ]
    resumo = {
        "status": execucao["status"],
        "tempo_segundos": execucao["tempo_ms"] / 1000,
        "custo_total": execucao["total_custo"],
        "valor_desperdicio": execucao["total_descarte"],
        "tempo_cozinha_minutos": execucao["total_preparo"],
        "folga_total": sum(item["folga"] for item in aderencia),
    }

    return {
        "resumo": resumo,
        "cardapio": cardapio,
        "porcoes": porcoes,
        "compras": compras,
        "descartes": descartes,
        "aderencia": aderencia,
    }
