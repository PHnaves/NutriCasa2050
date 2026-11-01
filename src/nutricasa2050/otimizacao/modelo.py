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
    preparar_catalogo,
    r1_cobertura,
    r2_vinculo,
    r3_limite_de_pratos,
    r4_variedade,
    r5_faixas_nutricionais,
    r6_restricao_alimentar_individual,
    r7_desvio_do_alvo,
    r8_consumo_derivado,
    r9_balanco_de_estoque,
    r10_validade_por_lote,
    r11_tempo_de_preparo,
    r12_orcamento,
)
from nutricasa2050.otimizacao.variaveis import Variaveis, criar_variaveis

FuncaoRestricao = Callable[[LpProblem, Variaveis, Catalogo, Parametros], None]

# As 12 restricoes da formulacao (docs/formulacao.md) completas no Sprint
# 3. Ligar/desligar uma restricao para comparar resultados e so passar
# uma lista diferente para `construir`.
RESTRICOES_ATIVAS: list[FuncaoRestricao] = [
    r1_cobertura,
    r2_vinculo,
    r3_limite_de_pratos,
    r4_variedade,
    r5_faixas_nutricionais,
    r6_restricao_alimentar_individual,
    r7_desvio_do_alvo,
    r8_consumo_derivado,
    r9_balanco_de_estoque,
    r10_validade_por_lote,
    r11_tempo_de_preparo,
    r12_orcamento,
]


def construir(
    catalogo: Catalogo,
    parametros: Parametros,
    restricoes_ativas: Sequence[FuncaoRestricao] = RESTRICOES_ATIVAS,
) -> tuple[LpProblem, Variaveis]:
    # Os lotes de compra (S3-01/R10) tem que existir ANTES das variaveis
    # serem criadas, senao s/u/w nunca sao instanciadas para eles.
    catalogo = preparar_catalogo(catalogo, parametros)

    problema = LpProblem("NutriCasa2050", LpMinimize)
    variaveis = criar_variaveis(catalogo, parametros)

    for restricao in restricoes_ativas:
        restricao(problema, variaveis, catalogo, parametros)

    montar_objetivo(problema, variaveis, catalogo, parametros)

    return problema, variaveis
