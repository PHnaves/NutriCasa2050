"""R6 (restricao alimentar individual, card S3-03): bloqueia receita so
para quem nao pode comer dela — nao para a casa toda. E o que permite um
filho celiaco sem obrigar todo mundo a comer sem gluten.
"""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, membro, receita
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus

from nutricasa2050.dominio import Faixa, Parametros
from nutricasa2050.otimizacao.modelo import construir
from nutricasa2050.otimizacao.restricoes import (
    r1_cobertura,
    r2_vinculo,
    r6_restricao_alimentar_individual,
)
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def test_membro_restrito_nao_recebe_prato_proibido() -> None:
    tag = frozenset({"gluten"})
    catalogo = construir_catalogo(
        receitas=[receita("r1", tags=tag), receita("r2")],
        membros=[membro("p1", tags_bloqueadas=tag)],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r6", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r6_restricao_alimentar_individual(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    assert variaveis.y[("p1", "r1", dia, refeicao)].varValue < 1e-6
    assert abs(variaveis.y[("p1", "r2", dia, refeicao)].varValue - 1.0) < 1e-6


def test_restricao_de_um_nao_afeta_os_outros() -> None:
    tag = frozenset({"gluten"})
    catalogo = construir_catalogo(
        receitas=[receita("r1", tags=tag), receita("r2")],
        membros=[
            membro("p1", tags_bloqueadas=tag),
            membro("p2", tags_bloqueadas=frozenset()),
        ],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=2)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r6_outros", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r6_restricao_alimentar_individual(problema, variaveis, catalogo, parametros)

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    # Forca p2 (sem restricao) a comer exatamente a receita com gluten.
    problema += variaveis.y[("p2", "r1", dia, refeicao)] == 1

    assert _resolver(problema) == "Optimal"
    assert abs(variaveis.y[("p2", "r1", dia, refeicao)].varValue - 1.0) < 1e-6
    assert variaveis.y[("p1", "r1", dia, refeicao)].varValue < 1e-6


def test_casa_toda_restrita_reduz_as_opcoes() -> None:
    """Com so uma receita liberada para todo mundo, o modelo e forcado a
    usa-la; sem a restricao, qualquer uma das duas serve — o "custo" da
    restricao e perder metade do cardapio disponivel."""
    tag = frozenset({"gluten"})
    catalogo = construir_catalogo(
        receitas=[receita("r1", tags=tag), receita("r2")],
        membros=[membro("p1", tags_bloqueadas=tag), membro("p2", tags_bloqueadas=tag)],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r6_casa_toda", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r6_restricao_alimentar_individual(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    assert abs(variaveis.x[("r2", dia, refeicao)].varValue - 1.0) < 1e-6
    assert variaveis.x[("r1", dia, refeicao)].varValue < 1e-6


def test_celiaco_ainda_fecha_a_faixa_nutricional() -> None:
    """O cenario da demonstracao precisa ser VIAVEL — se der Infeasible, o
    botao morre na frente do visitante."""
    tag = frozenset({"gluten"})
    catalogo = construir_catalogo(
        receitas=[receita("r1", tags=tag), receita("r2")],
        nutrientes={("r1", "kcal"): 500.0, ("r2", "kcal"): 480.0},
        membros=[
            membro(
                "p1",
                tags_bloqueadas=tag,
                faixas={"kcal": Faixa(minimo=400, maximo=600, alvo=500)},
            )
        ],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)

    problema, variaveis = construir(catalogo, parametros)

    assert _resolver(problema) == "Optimal"
    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    assert variaveis.y[("p1", "r1", dia, refeicao)].varValue < 1e-6
