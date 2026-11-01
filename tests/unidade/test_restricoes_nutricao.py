from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus, lpSum

from nutricasa2050.dominio import Faixa, Parametros
from nutricasa2050.otimizacao.restricoes import (
    preparar_catalogo,
    r1_cobertura,
    r2_vinculo,
    r5_faixas_nutricionais,
    r8_consumo_derivado,
    r9_balanco_de_estoque,
    r12_orcamento,
)
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def _catalogo_nutricional(minimo: float, maximo: float):
    return construir_catalogo(
        receitas=[receita("r1")],
        nutrientes={("r1", "kcal"): 500.0},
        membros=[
            membro(
                "p1",
                fator_porcao=1.0,
                faixas={"kcal": Faixa(minimo=minimo, maximo=maximo, alvo=500)},
            )
        ],
    )


def test_r5_resultado_dentro_das_faixas() -> None:
    catalogo = _catalogo_nutricional(minimo=400, maximo=600)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r5", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r5_faixas_nutricionais(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    fracao = variaveis.y[("p1", "r1", dia, refeicao)].varValue
    consumo_kcal = catalogo.nutriente("r1", "kcal") * fracao
    assert 400 <= consumo_kcal <= 600


def test_r5_faixa_impossivel_usa_folga() -> None:
    """Desde o S3-06, R5 usa folga em vez de virar Infeasible direto: uma
    faixa impossivel de bater (unica receita do catalogo tem 500 kcal, a
    faixa exige 5000-6000) fica Optimal, e a folga_falta extraida mostra
    ONDE e QUANTO precisou ceder.
    """
    catalogo = _catalogo_nutricional(minimo=5000, maximo=6000)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r5_folga", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r5_faixas_nutricionais(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia = parametros.dias[0]
    folga_falta = variaveis.folga_falta[("kcal", "p1", dia)].varValue
    assert folga_falta >= 4500 - 1e-6


def _catalogo_compra(preco_embalagem: float = 20.0):
    return construir_catalogo(
        ingredientes=[
            ingrediente("1", "Arroz", preco_embalagem=preco_embalagem, tamanho_embalagem=1.0)
        ],
        receitas=[receita("r1")],
        matriz_a={("r1", "1"): 2.0},
        lotes=[lote("L1", "1", quantidade=0.0, dia_vencimento=180)],
        membros=[membro("p1", fator_porcao=1.0)],
    )


def _montar_problema_de_compra(catalogo, parametros, orcamento: float):
    catalogo = preparar_catalogo(catalogo, parametros)
    variaveis = criar_variaveis(catalogo, parametros)
    problema = LpProblem("teste_r12", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r8_consumo_derivado(problema, variaveis, catalogo, parametros)
    r9_balanco_de_estoque(problema, variaveis, catalogo, parametros)
    r12_orcamento(problema, variaveis, catalogo, parametros)

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    problema += variaveis.x[("r1", dia, refeicao)] == 1

    custo = lpSum(
        catalogo.ingredientes[i].preco_embalagem * variaveis.b[(i, d)]
        for i in catalogo.ingredientes
        for d in parametros.dias_compra
    )
    problema += -custo  # maximiza o custo (dentro do orcamento), para testar o teto de fato

    return problema, variaveis, custo


def test_r12_custo_nunca_passa_do_orcamento() -> None:
    catalogo = _catalogo_compra()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, dias_compra=(1,), orcamento=100.0)
    problema, _, custo = _montar_problema_de_compra(catalogo, parametros, orcamento=100.0)

    assert _resolver(problema) == "Optimal"
    assert custo.value() <= 100.0 + 1e-6


def test_orcamento_de_dez_reais_gera_infeasible() -> None:
    catalogo = _catalogo_compra()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, dias_compra=(1,), orcamento=10.0)
    problema, _, _ = _montar_problema_de_compra(catalogo, parametros, orcamento=10.0)

    assert _resolver(problema) == "Infeasible"
