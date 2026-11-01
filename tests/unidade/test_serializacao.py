from __future__ import annotations

import json

from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita

from nutricasa2050.dominio import Faixa, Parametros
from nutricasa2050.otimizacao.solver import resolver
from nutricasa2050.serializacao import resultado_para_dict


def _catalogo_e_parametros():
    catalogo = construir_catalogo(
        ingredientes=[ingrediente("1", "Arroz", preco_embalagem=6.0, tamanho_embalagem=1.0)],
        receitas=[receita("r1")],
        matriz_a={("r1", "1"): 0.2},
        nutrientes={("r1", "kcal"): 500.0},
        lotes=[lote("L1", "1", quantidade=0.0, dia_vencimento=180)],
        membros=[
            membro(
                "p1",
                fator_porcao=1.0,
                faixas={"kcal": Faixa(minimo=400, maximo=600, alvo=500)},
            )
        ],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, orcamento=100.0, dias_compra=(1,))
    return catalogo, parametros


def test_dicionario_tem_as_sete_secoes() -> None:
    """Ganhou "estoque" no S5-05: a tela precisa mostrar a despensa dia
    a dia, e isso nao vinha em nenhuma das seis secoes originais."""
    catalogo, parametros = _catalogo_e_parametros()
    solucao = resolver(catalogo, parametros)

    resultado = resultado_para_dict(solucao, catalogo, parametros)

    assert set(resultado) == {
        "resumo",
        "cardapio",
        "porcoes",
        "compras",
        "descartes",
        "estoque",
        "aderencia",
    }


def test_resultado_e_convertivel_para_json() -> None:
    catalogo, parametros = _catalogo_e_parametros()
    solucao = resolver(catalogo, parametros)

    resultado = resultado_para_dict(solucao, catalogo, parametros)

    # Pega tipo do numpy escondido, que e dificil de achar depois.
    json.dumps(resultado)


def test_cardapio_traz_o_nome_da_receita_alem_do_id() -> None:
    catalogo, parametros = _catalogo_e_parametros()
    solucao = resolver(catalogo, parametros)

    resultado = resultado_para_dict(solucao, catalogo, parametros)

    assert resultado["cardapio"]
    item = resultado["cardapio"][0]
    assert item["receita_id"] == "r1"
    assert item["receita_nome"] == catalogo.receitas["r1"].nome


def test_somas_do_resumo_batem_com_as_listas() -> None:
    catalogo, parametros = _catalogo_e_parametros()
    solucao = resolver(catalogo, parametros)

    resultado = resultado_para_dict(solucao, catalogo, parametros)

    assert resultado["resumo"]["custo_total"] == sum(
        item["custo"] for item in resultado["compras"]
    )
    assert resultado["resumo"]["valor_desperdicio"] == sum(
        item["valor"] for item in resultado["descartes"]
    )
    assert resultado["resumo"]["folga_total"] == sum(
        item["folga"] for item in resultado["aderencia"]
    )
