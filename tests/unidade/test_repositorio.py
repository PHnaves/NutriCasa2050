from __future__ import annotations

import pytest

from nutricasa2050.persistencia.banco import conexao, criar_schema
from nutricasa2050.persistencia.repositorio import (
    gravar_execucao,
    gravar_resultado_completo,
    ler_execucao,
)


def _resultado_exemplo() -> dict:
    return {
        "resumo": {
            "status": "Optimal",
            "tempo_segundos": 1.25,
            "custo_total": 40.0,
            "valor_desperdicio": 2.0,
            "tempo_cozinha_minutos": 30,
        },
        "cardapio": [
            {
                "dia": 1,
                "refeicao": "almoco",
                "receita_id": "r1",
                "puxado_por_validade": True,
            }
        ],
        "porcoes": [
            {
                "membro_id": "p1",
                "dia": 1,
                "refeicao": "almoco",
                "receita_id": "r1",
                "fracao": 1.0,
            }
        ],
        "compras": [
            {
                "ingrediente_id": "1",
                "ingrediente_nome": "Arroz",
                "dia": 1,
                "embalagens": 2,
                "quantidade": 2.0,
                "unidade": "kg",
                "custo": 12.0,
            }
        ],
        "descartes": [
            {
                "lote_id": "L1",
                "ingrediente_id": "1",
                "dia": 1,
                "quantidade": 0.1,
                "valor": 0.6,
            }
        ],
        "aderencia": [
            {
                "membro_id": "p1",
                "dia": 1,
                "nutriente": "kcal",
                "valor": 500.0,
                "minimo": 400.0,
                "maximo": 600.0,
                "alvo": 500.0,
                "desvio": 0.0,
                "folga": 100.0,
            }
        ],
    }


def test_gravar_execucao_devolve_id(engine_memoria) -> None:
    criar_schema(engine_memoria)
    resultado = _resultado_exemplo()

    execucao_id = gravar_execucao(engine_memoria, resultado, "custo_minimo", {"horizonte": 1})

    assert isinstance(execucao_id, int)
    assert execucao_id > 0


def test_gravar_completo_preenche_as_sete_tabelas(engine_memoria) -> None:
    criar_schema(engine_memoria)
    resultado = _resultado_exemplo()

    execucao_id = gravar_resultado_completo(
        engine_memoria, resultado, "custo_minimo", {"horizonte": 1}
    )

    with conexao(engine_memoria) as conn:
        totais = {
            tabela: conn.execute(f"SELECT COUNT(*) AS total FROM {tabela}").fetchone()["total"]
            for tabela in (
                "cenario",
                "execucao",
                "cardapio",
                "porcao",
                "compra",
                "descarte",
                "aderencia",
            )
        }

    assert totais["cenario"] == 1
    assert totais["execucao"] == 1
    assert totais["cardapio"] == 1
    assert totais["porcao"] == 1
    assert totais["compra"] == 1
    assert totais["descarte"] == 1
    assert totais["aderencia"] == 1
    assert execucao_id > 0


def test_ler_execucao_devolve_o_mesmo_cardapio(engine_memoria) -> None:
    criar_schema(engine_memoria)
    resultado = _resultado_exemplo()
    execucao_id = gravar_resultado_completo(
        engine_memoria, resultado, "custo_minimo", {"horizonte": 1}
    )

    lido = ler_execucao(engine_memoria, execucao_id)

    assert len(lido["cardapio"]) == 1
    item = lido["cardapio"][0]
    assert item["dia"] == 1
    assert item["refeicao"] == "almoco"
    assert item["receita_id"] == "r1"
    assert item["puxado_por_validade"] is True
    assert lido["resumo"]["status"] == "Optimal"
    assert lido["resumo"]["custo_total"] == 40.0


def test_falha_no_meio_nao_grava_nada(engine_memoria) -> None:
    criar_schema(engine_memoria)
    resultado = _resultado_exemplo()
    # Porcao referenciando uma receita/dia/refeicao que nao esta no
    # cardapio: a busca do cardapio_id falha depois que execucao e
    # cardapio ja foram inseridos na mesma transacao.
    resultado["porcoes"][0]["receita_id"] = "receita_fantasma"

    with pytest.raises(ValueError):
        gravar_resultado_completo(engine_memoria, resultado, "custo_minimo", {"horizonte": 1})

    with conexao(engine_memoria) as conn:
        total_execucao = conn.execute("SELECT COUNT(*) AS total FROM execucao").fetchone()["total"]
        total_cardapio = conn.execute("SELECT COUNT(*) AS total FROM cardapio").fetchone()["total"]

    assert total_execucao == 0
    assert total_cardapio == 0


def test_folga_e_gravada_na_tabela_aderencia(engine_memoria) -> None:
    criar_schema(engine_memoria)
    resultado = _resultado_exemplo()

    gravar_resultado_completo(engine_memoria, resultado, "custo_minimo", {"horizonte": 1})

    with conexao(engine_memoria) as conn:
        linha = conn.execute("SELECT folga FROM aderencia").fetchone()

    assert float(linha["folga"]) == 100.0
