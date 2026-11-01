"""Preco-sombra (card S5-01) — derivada do resultado em relacao ao
limite de uma restricao, calculada por resolucao repetida (o CBC nao
devolve dual confiavel para este MIP — ver o docstring do modulo).
"""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, membro, receita

from nutricasa2050.analise.sensibilidade import (
    interpretar_preco_sombra,
    preco_sombra_do_orcamento,
    preco_sombra_por_membro_e_nutriente,
)
from nutricasa2050.dominio import Faixa, Parametros


def _catalogo_compra():
    return construir_catalogo(
        ingredientes=[
            ingrediente("1", "Arroz", preco_embalagem=6.0, tamanho_embalagem=1.0)
        ],
        receitas=[receita("r1")],
        matriz_a={("r1", "1"): 1.0},
        membros=[membro("p1", fator_porcao=1.0)],
    )


def test_dual_do_orcamento_nao_e_positivo() -> None:
    """Orcamento apertado (so cobre exatamente a compra necessaria):
    dar mais dinheiro nao pode piorar o resultado."""
    catalogo = _catalogo_compra()
    parametros = Parametros(
        horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=1, orcamento=6.0, dias_compra=(1,)
    )

    dual = preco_sombra_do_orcamento(catalogo, parametros)

    assert dual <= 1e-9


def test_restricao_folgada_tem_dual_zero() -> None:
    """Orcamento bem acima do que precisa: afrouxar mais nao muda nada."""
    catalogo = _catalogo_compra()
    parametros = Parametros(
        horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=1, orcamento=1000.0, dias_compra=(1,)
    )

    dual = preco_sombra_do_orcamento(catalogo, parametros)

    assert abs(dual) < 1e-9


def test_preco_sombra_do_sodio_nao_e_positivo() -> None:
    """Afrouxar o teto de sodio (subir o maximo) nunca pode piorar o
    resultado — mesma logica do orcamento, para uma faixa nutricional."""
    catalogo = construir_catalogo(
        ingredientes=[ingrediente("1", "Embutido", preco_embalagem=5.0, tamanho_embalagem=1.0)],
        receitas=[receita("r1")],
        matriz_a={("r1", "1"): 1.0},
        nutrientes={("r1", "sodio_mg"): 2000.0},
        membros=[
            membro(
                "idoso",
                fator_porcao=1.0,
                faixas={"sodio_mg": Faixa(minimo=0, maximo=2000, alvo=1000)},
            )
        ],
    )
    parametros = Parametros(
        horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=1, orcamento=100.0, dias_compra=(1,)
    )

    resultado = preco_sombra_por_membro_e_nutriente(
        catalogo, parametros, membro_id="idoso", nutriente="sodio_mg"
    )

    assert resultado[("idoso", "sodio_mg", "maximo")] <= 1e-9


def test_interpretacao_menciona_reais_e_periodo() -> None:
    frase_orcamento = interpretar_preco_sombra("R12_orcamento", -0.8)
    frase_nutriente = interpretar_preco_sombra("sodio_mg", -4.2)
    frase_zero = interpretar_preco_sombra("R12_orcamento", 0.0)

    for frase in (frase_orcamento, frase_nutriente, frase_zero):
        assert "R$" in frase
        assert "semana" in frase
