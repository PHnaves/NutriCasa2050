from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus

from nutricasa2050.dominio import Parametros
from nutricasa2050.otimizacao.restricoes import (
    r1_cobertura,
    r2_vinculo,
    r8_consumo_derivado,
    r9_balanco_de_estoque,
)
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def _catalogo_arroz(quantidade_inicial: float = 5.0, consumo_por_porcao: float = 0.2):
    return construir_catalogo(
        ingredientes=[ingrediente("1", "Arroz", tamanho_embalagem=1.0)],
        receitas=[receita("r1")],
        matriz_a={("r1", "1"): consumo_por_porcao},
        lotes=[lote("L1", "1", quantidade=quantidade_inicial, dia_vencimento=180)],
        membros=[membro("p1", fator_porcao=1.0)],
    )


def test_r8_consumo_bate_com_a_matriz_a() -> None:
    catalogo = _catalogo_arroz()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r8", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r8_consumo_derivado(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    assert abs(variaveis.y[("p1", "r1", dia, refeicao)].varValue - 1.0) < 1e-6
    assert abs(variaveis.u[("L1", dia)].varValue - 0.2) < 1e-6


def test_r8_fator_de_porcao_reduz_consumo() -> None:
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)

    def _consumo(fator_porcao: float) -> float:
        catalogo = _catalogo_arroz()
        catalogo = construir_catalogo(
            ingredientes=list(catalogo.ingredientes.values()),
            receitas=list(catalogo.receitas.values()),
            matriz_a=catalogo.matriz_a,
            lotes=list(catalogo.lotes.values()),
            membros=[membro("p1", fator_porcao=fator_porcao)],
        )
        variaveis = criar_variaveis(catalogo, parametros)
        problema = LpProblem("teste_fator_porcao", LpMinimize)
        r1_cobertura(problema, variaveis, catalogo, parametros)
        r2_vinculo(problema, variaveis, catalogo, parametros)
        r8_consumo_derivado(problema, variaveis, catalogo, parametros)
        assert _resolver(problema) == "Optimal"
        dia = parametros.dias[0]
        return variaveis.u[("L1", dia)].varValue

    consumo_adulto = _consumo(1.0)
    consumo_crianca = _consumo(0.6)

    assert abs(consumo_crianca - 0.6 * consumo_adulto) < 1e-6


def test_r9_conserva_massa() -> None:
    """O teste mais importante do sprint: entrada total (estoque inicial +
    compras) tem que ser igual a consumo + descarte + estoque final, para
    todo ingrediente. Se quebrar, tem comida sumindo ou aparecendo do nada.
    """
    catalogo = _catalogo_arroz(quantidade_inicial=1.0)
    parametros = Parametros(horizonte=3, refeicoes_por_dia=1, dias_compra=(2,))
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r9_massa", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r8_consumo_derivado(problema, variaveis, catalogo, parametros)
    r9_balanco_de_estoque(problema, variaveis, catalogo, parametros)

    problema += variaveis.b[("1", 2)] == 3  # compra 3 embalagens de 1kg no dia 2

    assert _resolver(problema) == "Optimal"

    lote_obj = catalogo.lotes["L1"]
    consumo_total = sum(variaveis.u[("L1", dia)].varValue for dia in parametros.dias)
    descarte_total = sum(variaveis.w[("L1", dia)].varValue for dia in parametros.dias)
    estoque_final = variaveis.s[("L1", parametros.dias[-1])].varValue
    entrada_total = lote_obj.quantidade + sum(
        chegada_valor(variaveis, catalogo, "1", dia) for dia in parametros.dias
    )

    assert abs(entrada_total - (consumo_total + descarte_total + estoque_final)) < 1e-6


def chegada_valor(variaveis, catalogo, ingrediente_id: str, dia: int) -> float:
    chave = (ingrediente_id, dia)
    if chave not in variaveis.b:
        return 0.0
    tamanho = catalogo.ingredientes[ingrediente_id].tamanho_embalagem
    return tamanho * variaveis.b[chave].varValue


def test_r9_estoque_nunca_negativo() -> None:
    """Sem compra possivel e exigindo mais consumo do que existe em
    estoque, o modelo tem que dar Infeasible — nunca um estoque negativo."""
    catalogo = _catalogo_arroz(quantidade_inicial=0.1, consumo_por_porcao=1.0)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, dias_compra=())
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_estoque_negativo", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r8_consumo_derivado(problema, variaveis, catalogo, parametros)
    r9_balanco_de_estoque(problema, variaveis, catalogo, parametros)

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    problema += variaveis.x[("r1", dia, refeicao)] == 1

    assert _resolver(problema) == "Infeasible"


def test_r9_sobra_de_um_dia_disponivel_no_seguinte() -> None:
    catalogo = _catalogo_arroz(quantidade_inicial=1.0)
    parametros = Parametros(horizonte=2, refeicoes_por_dia=1, dias_compra=())
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_sobra", LpMinimize)
    r9_balanco_de_estoque(problema, variaveis, catalogo, parametros)

    problema += variaveis.u[("L1", 1)] == 0
    problema += variaveis.w[("L1", 1)] == 0
    problema += variaveis.u[("L1", 2)] == 0.3
    problema += variaveis.w[("L1", 2)] == 0

    assert _resolver(problema) == "Optimal"

    assert abs(variaveis.s[("L1", 1)].varValue - 1.0) < 1e-6
    assert abs(variaveis.s[("L1", 2)].varValue - 0.7) < 1e-6
