"""A tela (cards S5-05/06/07) — testa as FUNCOES, nao a renderizacao:
chamar cada "desenhar_*" com um resultado de exemplo (e um Infeasible)
tem que simplesmente nao quebrar.
"""
from __future__ import annotations

from app import (
    desenhar_aderencia,
    desenhar_cardapio,
    desenhar_compras,
    desenhar_despensa,
    desenhar_numeros,
    montar_parametros,
)
from nutricasa2050.dominio import Parametros


def test_montar_parametros_a_partir_de_valores_da_tela() -> None:
    parametros = montar_parametros(
        orcamento=250.0,
        tempo_por_dia=45.0,
        pesos={
            "custo": 1.0,
            "desperdicio": 2.0,
            "preparo": 0.5,
            "desvio": 1.0,
            "folga": 1000.0,
            "preferencia": 1.0,
        },
    )

    assert isinstance(parametros, Parametros)
    assert parametros.orcamento == 250.0
    assert parametros.tempo_por_dia == 45.0
    assert parametros.pesos.desperdicio == 2.0


def _resultado_de_exemplo() -> dict:
    return {
        "resumo": {
            "status": "Optimal",
            "tempo_segundos": 1.0,
            "custo_total": 120.0,
            "valor_desperdicio": 8.0,
            "tempo_cozinha_minutos": 90,
        },
        "cardapio": [
            {
                "dia": 1,
                "refeicao": "almoco",
                "receita_id": "r1",
                "receita_nome": "Arroz com feijao",
                "puxado_por_validade": True,
                "preparado": True,
            }
        ],
        "porcoes": [],
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
        "descartes": [],
        "estoque": [
            {
                "lote_id": "L1",
                "ingrediente_id": "1",
                "ingrediente_nome": "Arroz",
                "dia": 7,
                "quantidade": 0.5,
                "dia_vencimento": 9,
                "dias_restantes": 2,
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
                "folga": 0.0,
            }
        ],
    }


def test_desenhar_funciona_com_resultado_de_exemplo() -> None:
    resultado = _resultado_de_exemplo()
    parametros = montar_parametros(
        orcamento=300.0, tempo_por_dia=60.0, pesos={"custo": 1.0}
    )

    desenhar_numeros(resultado, resultado)
    desenhar_cardapio(resultado)
    desenhar_despensa(resultado)
    desenhar_compras(resultado, parametros)
    desenhar_aderencia(resultado)


def test_desenhar_funciona_com_resultado_infeasible() -> None:
    """A tela precisa MOSTRAR a mensagem, nao quebrar — um resultado
    Infeasible tem todas as listas vazias (ver solver.resolver)."""
    resultado_vazio = {
        "resumo": {
            "status": "Infeasible",
            "tempo_segundos": 0.5,
            "custo_total": 0.0,
            "valor_desperdicio": 0.0,
            "tempo_cozinha_minutos": 0,
        },
        "cardapio": [],
        "porcoes": [],
        "compras": [],
        "descartes": [],
        "estoque": [],
        "aderencia": [],
    }
    parametros = montar_parametros(orcamento=100.0, tempo_por_dia=60.0, pesos={"custo": 1.0})

    desenhar_numeros(resultado_vazio)
    desenhar_cardapio(resultado_vazio)
    desenhar_despensa(resultado_vazio)
    desenhar_compras(resultado_vazio, parametros)
    desenhar_aderencia(resultado_vazio)
