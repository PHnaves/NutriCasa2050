"""Monta o problema completo: variaveis + restricoes + objetivo.

Depois deste modulo, qualquer restricao e uma chamada na lista
RESTRICOES_ATIVAS — e por isso que ele cabe numa tela so.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from pulp import LpMinimize, LpProblem

from nutricasa2050.dominio import Catalogo, Parametros
from nutricasa2050.otimizacao.objetivo import montar_objetivo
from nutricasa2050.otimizacao.restricoes import (
    r1_cobertura,
    r2_vinculo,
    r3_limite_de_pratos,
    r5_faixas_nutricionais,
    r8_consumo_derivado,
    r9_balanco_de_estoque,
    r12_orcamento,
)
from nutricasa2050.otimizacao.variaveis import Variaveis, criar_variaveis

FuncaoRestricao = Callable[[LpProblem, Variaveis, Catalogo, Parametros], None]

# As restricoes implementadas ate o Sprint 2. R4, R6, R7, R10 e R11 entram
# no Sprint 3 (ver docs/formulacao.md). Ligar/desligar uma restricao para
# comparar resultados e so passar uma lista diferente para `construir`.
RESTRICOES_ATIVAS: list[FuncaoRestricao] = [
    r1_cobertura,
    r2_vinculo,
    r3_limite_de_pratos,
    r5_faixas_nutricionais,
    r8_consumo_derivado,
    r9_balanco_de_estoque,
    r12_orcamento,
]


def construir(
    catalogo: Catalogo,
    parametros: Parametros,
    restricoes_ativas: Sequence[FuncaoRestricao] = RESTRICOES_ATIVAS,
) -> tuple[LpProblem, Variaveis]:
    problema = LpProblem("NutriCasa2050", LpMinimize)
    variaveis = criar_variaveis(catalogo, parametros)

    for restricao in restricoes_ativas:
        restricao(problema, variaveis, catalogo, parametros)

    montar_objetivo(problema, variaveis, catalogo, parametros)

    return problema, variaveis
