"""O que a tela redesenhada do Sprint 6 le da serializacao: a marcacao
"usa algo que vence em breve" no cardapio e o resumo nutricional."""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita

from nutricasa2050.dominio import Parametros, Solucao
from nutricasa2050.serializacao import resultado_para_dict, resumo_nutricional


def _solucao(cardapio: dict, estoque: dict) -> Solucao:
    return Solucao(
        status="Optimal",
        tempo_segundos=0.1,
        valor_objetivo=0.0,
        cardapio=cardapio,
        porcoes={},
        compras={},
        descartes={},
        estoque=estoque,
        aderencia={"folga_falta": {}, "folga_sobra": {}, "desvio_acima": {}, "desvio_abaixo": {}},
    )


def _catalogo():
    return construir_catalogo(
        ingredientes=[ingrediente("tomate"), ingrediente("arroz")],
        receitas=[receita("molho"), receita("arroz_puro")],
        matriz_a={("molho", "tomate"): 0.2, ("arroz_puro", "arroz"): 0.2},
        lotes=[
            lote("L_tomate", "tomate", quantidade=1.0, dia_vencimento=2),
            lote("L_arroz", "arroz", quantidade=1.0, dia_vencimento=30),
        ],
        membros=[membro("p1")],
    )


def test_prato_que_usa_item_perto_de_vencer_e_marcado() -> None:
    parametros = Parametros(horizonte=3, refeicoes_por_dia=1, orcamento=0.0, dias_compra=())
    solucao = _solucao(
        cardapio={("molho", 1, "almoco"): 1.0, ("arroz_puro", 2, "almoco"): 1.0},
        estoque={("L_tomate", 1): 0.8, ("L_arroz", 1): 0.8},
    )

    resultado = resultado_para_dict(solucao, _catalogo(), parametros)
    marcados = {item["receita_id"]: item["puxado_por_validade"] for item in resultado["cardapio"]}

    assert marcados["molho"] is True  # tomate vence no dia 2, estava na despensa no dia 1
    assert marcados["arroz_puro"] is False  # arroz vence no dia 30


def test_lote_ja_vazio_nao_marca_o_prato() -> None:
    """No dia 2 o tomate ja tinha acabado no fim do dia 1: nada a salvar."""
    parametros = Parametros(horizonte=3, refeicoes_por_dia=1, orcamento=0.0, dias_compra=())
    solucao = _solucao(cardapio={("molho", 2, "almoco"): 1.0}, estoque={("L_tomate", 1): 0.0})

    resultado = resultado_para_dict(solucao, _catalogo(), parametros)

    assert resultado["cardapio"][0]["puxado_por_validade"] is False


def test_resumo_nutricional_faz_media_e_conta_dias_fora_da_faixa() -> None:
    base = {"membro_id": "p1", "nutriente": "kcal", "minimo": 1000, "maximo": 2000, "alvo": 1500}
    aderencia = [
        {**base, "dia": 1, "valor": 1200.0, "folga": 0.0, "desvio": 0.0},
        {**base, "dia": 2, "valor": 900.0, "folga": 100.0, "desvio": 0.0},
    ]

    (linha,) = resumo_nutricional(aderencia)

    assert linha["media"] == 1050.0
    assert linha["dias"] == 2
    assert linha["dias_fora_da_faixa"] == 1
    assert (linha["minimo"], linha["maximo"], linha["alvo"]) == (1000, 2000, 1500)
