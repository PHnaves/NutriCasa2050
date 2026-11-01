from __future__ import annotations

from apoio_catalogo import construir_catalogo, membro, receita
from pulp import PULP_CBC_CMD, LpProblem, LpStatus

from nutricasa2050.dominio import Parametros
from nutricasa2050.otimizacao.modelo import RESTRICOES_ATIVAS, construir
from nutricasa2050.otimizacao.variaveis import Variaveis


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def _catalogo_minimo():
    return construir_catalogo(
        receitas=[receita("r1"), receita("r2")],
        membros=[membro("p1")],
    )


def test_construir_devolve_problema_e_variaveis() -> None:
    catalogo = _catalogo_minimo()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)

    problema, variaveis = construir(catalogo, parametros)

    assert isinstance(problema, LpProblem)
    assert isinstance(variaveis, Variaveis)


def test_modelo_minimo_e_resoluvel() -> None:
    catalogo = _catalogo_minimo()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, orcamento=1000.0)

    problema, _ = construir(catalogo, parametros)

    assert _resolver(problema) == "Optimal"


def test_desligar_uma_restricao_muda_o_resultado() -> None:
    catalogo = construir_catalogo(
        receitas=[receita("r1"), receita("r2")],
        membros=[membro("p1"), membro("p2")],
    )
    parametros = Parametros(
        horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=1, orcamento=1000.0
    )

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]

    problema_com_r3, variaveis_com_r3 = construir(catalogo, parametros)
    problema_com_r3 += variaveis_com_r3.y[("p1", "r1", dia, refeicao)] == 1
    problema_com_r3 += variaveis_com_r3.y[("p2", "r2", dia, refeicao)] == 1

    sem_r3 = [r for r in RESTRICOES_ATIVAS if r.__name__ != "r3_limite_de_pratos"]
    problema_sem_r3, variaveis_sem_r3 = construir(catalogo, parametros, restricoes_ativas=sem_r3)
    problema_sem_r3 += variaveis_sem_r3.y[("p1", "r1", dia, refeicao)] == 1
    problema_sem_r3 += variaveis_sem_r3.y[("p2", "r2", dia, refeicao)] == 1

    assert _resolver(problema_com_r3) == "Infeasible"
    assert _resolver(problema_sem_r3) == "Optimal"
