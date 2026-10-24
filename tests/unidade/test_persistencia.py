from nutricasa2050.persistencia.banco import (
    ErroDeBanco,
    conexao,
    criar_engine,
    criar_schema,
    limpar_dados,
)


def _nomes_tabelas(conn) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row["name"] for row in rows if not row["name"].startswith("sqlite_")}


def test_schema_cria_as_sete_tabelas(engine_memoria):
    criar_schema(engine_memoria)

    with conexao(engine_memoria) as conn:
        tabelas = _nomes_tabelas(conn)

    assert tabelas == {
        "cenario",
        "execucao",
        "cardapio",
        "porcao",
        "compra",
        "descarte",
        "aderencia",
    }


def test_aderencia_tem_coluna_folga(engine_memoria):
    criar_schema(engine_memoria)

    with conexao(engine_memoria) as conn:
        rows = conn.execute("PRAGMA table_info(aderencia)").fetchall()

    colunas = {row["name"] for row in rows}
    assert "folga" in colunas


def test_gravar_e_ler_de_volta(engine_memoria):
    criar_schema(engine_memoria)

    with conexao(engine_memoria) as conn:
        cenario_id = conn.execute(
            """
            INSERT INTO cenario (rodada, semente, dados_sorteados)
            VALUES (?, ?, ?)
            """,
            (1, 42, '{"chuva": 0.2}'),
        ).lastrowid

        execucao_id = conn.execute(
            """
            INSERT INTO execucao (
                cenario_id,
                estrategia,
                parametros,
                pesos,
                status,
                tempo_ms,
                total_custo,
                total_descarte,
                total_preparo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cenario_id,
                "custo_minimo",
                '{"limite": 10}',
                '{"custo": 1.0}',
                "concluida",
                1250,
                212.35,
                4.250,
                18.500,
            ),
        ).lastrowid

        cardapio_id = conn.execute(
            """
            INSERT INTO cardapio (
                execucao_id,
                dia,
                refeicao,
                prato,
                puxado_por_validade
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (execucao_id, 1, "almoco", "ensopado", 1),
        ).lastrowid

        conn.execute(
            """
            INSERT INTO porcao (cardapio_id, membro, quantidade)
            VALUES (?, ?, ?)
            """,
            (cardapio_id, "ana", 0.350),
        )
        conn.execute(
            """
            INSERT INTO compra (execucao_id, ingrediente, quantidade, unidade, custo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (execucao_id, "arroz", 2.000, "kg", 14.90),
        )
        conn.execute(
            """
            INSERT INTO descarte (execucao_id, ingrediente, lote, quantidade, motivo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (execucao_id, "tomate", "L001", 0.180, "vencimento"),
        )
        conn.execute(
            """
            INSERT INTO aderencia (
                execucao_id,
                dia,
                membro,
                regra,
                valor,
                minimo,
                maximo,
                alvo,
                desvio,
                folga
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (execucao_id, 1, "ana", "proteina", 52.0, 45.0, 60.0, 50.0, 2.0, 7.0),
        )

    with conexao(engine_memoria) as conn:
        row = conn.execute("SELECT membro, folga FROM aderencia").fetchone()

    assert row["membro"] == "ana"
    assert float(row["folga"]) == 7.0


def test_limpar_dados_esvazia_sem_apagar_tabela(engine_arquivo):
    criar_schema(engine_arquivo)

    with conexao(engine_arquivo) as conn:
        cenario_id = conn.execute(
            "INSERT INTO cenario (rodada, semente, dados_sorteados) VALUES (?, ?, ?)",
            (10, 123, "{}"),
        ).lastrowid
        execucao_id = conn.execute(
            """
            INSERT INTO execucao (cenario_id, estrategia, parametros, pesos, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (cenario_id, "teste", "{}", "{}", "ok"),
        ).lastrowid
        conn.execute(
            """
            INSERT INTO aderencia (
                execucao_id,
                dia,
                membro,
                regra,
                valor,
                minimo,
                maximo,
                alvo,
                desvio,
                folga
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (execucao_id, 1, "bia", "energia", 1800, 1700, 2100, 1900, -100, 100),
        )

    limpar_dados(engine_arquivo)

    with conexao(engine_arquivo) as conn:
        total_aderencia = conn.execute(
            "SELECT COUNT(*) AS total FROM aderencia"
        ).fetchone()["total"]
        total_execucao = conn.execute(
            "SELECT COUNT(*) AS total FROM execucao"
        ).fetchone()["total"]
        total_cenario = conn.execute(
            "SELECT COUNT(*) AS total FROM cenario"
        ).fetchone()["total"]
        tabelas = _nomes_tabelas(conn)

    assert total_aderencia == 0
    assert total_execucao == 0
    assert total_cenario == 0
    assert "aderencia" in tabelas
    assert "execucao" in tabelas
    assert "cenario" in tabelas


def test_trava_impede_teste_de_usar_banco_principal(cfg):
    try:
        criar_engine(cfg, cfg.url_banco_principal)
    except ErroDeBanco:
        return

    raise AssertionError("Esperava ErroDeBanco ao usar URL principal em ambiente de teste")
