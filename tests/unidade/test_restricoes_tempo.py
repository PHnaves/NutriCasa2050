"""R11 (tempo de cozinha, card S3-05) e o termo_tempo associado — o
"tempo" que o roteiro da categoria pede explicitamente como recurso a
otimizar. Precisa estar em reais (custo_por_minuto) para os pesos do
objetivo terem algum sentido comparavel.
"""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, membro, receita
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus

from nutricasa2050.dominio import Parametros, Pesos
from nutricasa2050.otimizacao.objetivo import termo_tempo
from nutricasa2050.otimizacao.restricoes import r1_cobertura, r2_vinculo, r11_tempo_de_preparo
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def _catalogo_receitas_de_tempos_diferentes():
    return construir_catalogo(
        receitas=[receita("r1", tempo_min=10), receita("r2", tempo_min=60)],
        membros=[membro("p1")],
    )


def test_tempo_diario_nunca_excede_o_disponivel() -> None:
    catalogo = _catalogo_receitas_de_tempos_diferentes()
    parametros = Parametros(
        horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=2, tempo_por_dia=60.0
    )
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r11_teto", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r11_tempo_de_preparo(problema, variaveis, catalogo, parametros)

    # Forca cozinhar as duas receitas na mesma refeicao (10 + 60 = 70 > 60).
    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    problema += variaveis.x[("r1", dia, refeicao)] == 1
    problema += variaveis.x[("r2", dia, refeicao)] == 1

    assert _resolver(problema) == "Infeasible"


def test_reduzir_o_tempo_de_um_dia_move_receitas_longas() -> None:
    """Com tempo disponivel suficiente so para a receita curta, o solver e
    forcado a nao cozinhar a longa naquele dia."""
    catalogo = _catalogo_receitas_de_tempos_diferentes()
    parametros = Parametros(
        horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=2, tempo_por_dia=15.0
    )
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r11_move", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r11_tempo_de_preparo(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    assert variaveis.x[("r2", dia, refeicao)].varValue < 1e-6


def test_tempo_zero_em_todos_os_dias_da_infeasible() -> None:
    catalogo = _catalogo_receitas_de_tempos_diferentes()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, tempo_por_dia=0.0)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r11_zero", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r11_tempo_de_preparo(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Infeasible"


def test_termo_tempo_esta_em_reais() -> None:
    """A magnitude e compativel com valor monetario, nao com minutos: 60
    minutos x custo_por_minuto (0,10 por padrao) = R$ 6,00, nao 60."""
    catalogo = _catalogo_receitas_de_tempos_diferentes()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, pesos=Pesos(custo_por_minuto=0.10))
    variaveis = criar_variaveis(catalogo, parametros)

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    variaveis.x[("r1", dia, refeicao)].setInitialValue(0)
    variaveis.x[("r1", dia, refeicao)].fixValue()
    variaveis.x[("r2", dia, refeicao)].setInitialValue(1)
    variaveis.x[("r2", dia, refeicao)].fixValue()

    problema = LpProblem("teste_termo_tempo", LpMinimize)
    problema += termo_tempo(variaveis, catalogo, parametros)
    problema.solve(PULP_CBC_CMD(msg=False))

    assert LpStatus[problema.status] == "Optimal"
    assert termo_tempo(variaveis, catalogo, parametros).value() == 60 * 0.10
