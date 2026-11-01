from __future__ import annotations

from dataclasses import replace

from apoio_catalogo import construir_catalogo, membro, receita
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus

from nutricasa2050.dominio import Parametros
from nutricasa2050.otimizacao.restricoes import r1_cobertura, r2_vinculo, r3_limite_de_pratos
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def _catalogo_simples():
    return construir_catalogo(
        receitas=[receita("r1"), receita("r2"), receita("r3")],
        membros=[membro("p1")],
    )


def _parametros(**kwargs):
    base = {"horizonte": 2, "refeicoes_por_dia": 1}
    base.update(kwargs)
    return Parametros(**base)


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def test_r1_cada_membro_come_uma_porcao_por_refeicao() -> None:
    catalogo = _catalogo_simples()
    parametros = _parametros()
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r1", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    for dia in parametros.dias:
        for refeicao in parametros.refeicoes:
            total = sum(
                variaveis.y[("p1", receita_id, dia, refeicao)].varValue
                for receita_id in catalogo.receitas
            )
            assert abs(total - 1.0) < 1e-6


def test_r2_ninguem_come_prato_nao_cozinhado() -> None:
    catalogo = _catalogo_simples()
    parametros = _parametros()
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r2", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    for (membro_id, receita_id, dia, refeicao), variavel in variaveis.y.items():
        prato = variaveis.x[(receita_id, dia, refeicao)].varValue
        if prato < 0.5:
            assert variavel.varValue is None or variavel.varValue < 1e-6


def test_r3_nunca_passa_do_limite_de_pratos() -> None:
    catalogo = _catalogo_simples()
    parametros = _parametros(pratos_por_refeicao=2)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r3", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r3_limite_de_pratos(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    for dia in parametros.dias:
        for refeicao in parametros.refeicoes:
            total_pratos = sum(
                variaveis.x[(receita_id, dia, refeicao)].varValue
                for receita_id in catalogo.receitas
            )
            assert total_pratos <= 2 + 1e-6


def test_sem_r3_o_modelo_cozinha_um_prato_por_pessoa() -> None:
    """Documenta por que R3 existe: com dois membros que so aceitam comer
    de pratos diferentes, sem R3 o modelo consegue cozinhar os dois pratos
    na mesma refeicao; com R3 = 1, a mesma exigencia fica Infeasible."""
    catalogo = construir_catalogo(
        receitas=[receita("r1"), receita("r2")],
        membros=[membro("p1"), membro("p2")],
    )
    parametros = _parametros(horizonte=1)

    def _montar(com_r3: bool) -> LpProblem:
        variaveis = criar_variaveis(catalogo, parametros)
        problema = LpProblem("teste_sem_r3", LpMinimize)
        r1_cobertura(problema, variaveis, catalogo, parametros)
        r2_vinculo(problema, variaveis, catalogo, parametros)
        if com_r3:
            params_r3 = _parametros(horizonte=1, pratos_por_refeicao=1)
            r3_limite_de_pratos(problema, variaveis, catalogo, params_r3)
        # Forca cada membro a um prato diferente, simulando preferencias
        # opostas (R6 so existe no Sprint 3).
        dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
        problema += variaveis.y[("p1", "r1", dia, refeicao)] == 1
        problema += variaveis.y[("p2", "r2", dia, refeicao)] == 1
        return problema, variaveis

    problema_sem_r3, variaveis_sem_r3 = _montar(com_r3=False)
    assert _resolver(problema_sem_r3) == "Optimal"
    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    pratos_sem_r3 = sum(
        variaveis_sem_r3.x[(receita_id, dia, refeicao)].varValue
        for receita_id in catalogo.receitas
    )
    assert pratos_sem_r3 == 2

    problema_com_r3, _ = _montar(com_r3=True)
    assert _resolver(problema_com_r3) == "Infeasible"


def test_refeicao_pulada_fica_com_fracao_zero() -> None:
    """S4-01/S5-06 ("ninguem jantou"): uma refeicao marcada em
    catalogo.refeicoes_puladas fica com fracao servida ZERO para todo
    membro, mesmo no modelo otimizado — nao so nos baselines."""
    catalogo = _catalogo_simples()
    catalogo = replace(catalogo, refeicoes_puladas=frozenset({(2, "almoco")}))
    parametros = _parametros()
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_refeicao_pulada", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    for receita_id in catalogo.receitas:
        assert variaveis.y[("p1", receita_id, 2, "almoco")].varValue < 1e-6

    # O dia 1 continua normal: a soma ainda fecha em 1.
    total_dia_1 = sum(
        variaveis.y[("p1", receita_id, 1, "almoco")].varValue for receita_id in catalogo.receitas
    )
    assert abs(total_dia_1 - 1.0) < 1e-6
