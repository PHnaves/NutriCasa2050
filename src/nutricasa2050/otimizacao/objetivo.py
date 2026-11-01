"""A funcao objetivo (ver docs/formulacao.md, Secao 4).

Nesta versao (S2-07), so o termo de custo de compra. Os outros cinco
termos (desperdicio, preparo, desvio nutricional, preferencia, sobra de
embalagem) entram no card S3-07.
"""
from __future__ import annotations

from pulp import LpAffineExpression, LpProblem, lpSum

from nutricasa2050.dominio import Catalogo, Parametros
from nutricasa2050.otimizacao.variaveis import Variaveis


def termo_custo(
    variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> LpAffineExpression:
    """Soma de (preco da embalagem) x (embalagens compradas), sobre todos
    os ingredientes e dias de compra.

    Repare: ela DEVOLVE a expressao, nao adiciona ao problema. Isso permite
    (a) testar o termo isolado e (b) reaproveita-lo no calculo do "preco da
    prescricao" do card S4-06. O preco no CSV JA e o preco do PACOTE —
    multiplicar de novo pelo tamanho da embalagem cobraria o ingrediente
    multiplicado por si mesmo (o tamanho so aparece em R9, convertendo
    pacote em quantidade).
    """
    return lpSum(
        catalogo.ingredientes[ingrediente_id].preco_embalagem * variaveis.b[(ingrediente_id, dia)]
        for ingrediente_id in catalogo.ingredientes
        for dia in parametros.dias_compra
    )


def montar_objetivo(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    problema += termo_custo(variaveis, catalogo, parametros), "Custo_Total"
