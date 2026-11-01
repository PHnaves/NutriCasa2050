"""A funcao objetivo (ver docs/formulacao.md, Secao 4).

Os seis termos (S3-07): custo de compra, desperdicio, tempo de preparo,
desvio do alvo nutricional, folga das faixas e preferencia. TUDO precisa
estar em reais antes de somar — tempo vira reais multiplicando por
Pesos.custo_por_minuto, preferencia por Pesos.valor_por_ponto_preferencia.
Sem isso, "aumentar o peso do tempo em 1" nao significa nada comparavel a
"aumentar o peso do custo em 1".
"""
from __future__ import annotations

from pulp import LpAffineExpression, LpProblem, lpSum

from nutricasa2050.dominio import Catalogo, Parametros, Solucao
from nutricasa2050.otimizacao.restricoes import preparar_catalogo
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


def termo_desperdicio(
    variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> LpAffineExpression:
    """Soma, sobre lotes e dias, de (preco unitario do ingrediente) x
    (quantidade descartada). Junto com R9+R10, e o que faz o solver
    preferir usar primeiro o que vence primeiro — nao porque alguem
    programou FEFO, mas porque jogar comida fora custa dinheiro aqui.
    """
    return lpSum(
        catalogo.ingredientes[lote.ingrediente_id].preco_unitario * variaveis.w[(lote.id, dia)]
        for lote in catalogo.lotes.values()
        for dia in parametros.dias
    )


def termo_tempo(
    variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> LpAffineExpression:
    """(minutos de preparo dos pratos cozinhados) x (custo por minuto) —
    ja devolvido em reais, pronto para ser somado com o resto.
    """
    minutos = lpSum(
        catalogo.receitas[receita_id].tempo_min * variaveis.x[(receita_id, dia, refeicao)]
        for receita_id in catalogo.receitas
        for dia in parametros.dias
        for refeicao in parametros.refeicoes
    )
    return parametros.pesos.custo_por_minuto * minutos


def termo_desvio(
    variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> LpAffineExpression:
    """Soma de desvio_acima + desvio_abaixo (R7) sobre nutriente, membro e
    dia — quanto mais perto do alvo prescrito, menor esse termo.
    """
    return lpSum(variaveis.desvio_acima.values()) + lpSum(variaveis.desvio_abaixo.values())


def termo_folga(
    variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> LpAffineExpression:
    """Soma de folga_falta + folga_sobra (R5) sobre nutriente, membro e
    dia. Entra no objetivo com Pesos.folga (bem alto por padrao) para o
    solver so usar quando realmente nao existe outro jeito.
    """
    return lpSum(variaveis.folga_falta.values()) + lpSum(variaveis.folga_sobra.values())


def termo_preferencia(
    variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> LpAffineExpression:
    """(preferencia da receita) x (prato cozinhado), convertida em reais
    por Pesos.valor_por_ponto_preferencia. Devolve um valor POSITIVO —
    quem soma com sinal negativo e `montar_objetivo`, porque preferencia
    alta e coisa boa e o solver esta MINIMIZANDO.
    """
    pontos = lpSum(
        catalogo.receitas[receita_id].preferencia * variaveis.x[(receita_id, dia, refeicao)]
        for receita_id in catalogo.receitas
        for dia in parametros.dias
        for refeicao in parametros.refeicoes
    )
    return parametros.pesos.valor_por_ponto_preferencia * pontos


def montar_objetivo(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    pesos = parametros.pesos
    objetivo = (
        pesos.custo * termo_custo(variaveis, catalogo, parametros)
        + pesos.desperdicio * termo_desperdicio(variaveis, catalogo, parametros)
        + pesos.preparo * termo_tempo(variaveis, catalogo, parametros)
        + pesos.desvio * termo_desvio(variaveis, catalogo, parametros)
        + pesos.folga * termo_folga(variaveis, catalogo, parametros)
        - pesos.preferencia * termo_preferencia(variaveis, catalogo, parametros)
    )
    problema += objetivo, "Objetivo_Total"


def descrever_objetivo(solucao: Solucao, catalogo: Catalogo, parametros: Parametros) -> dict:
    """Quanto cada um dos seis termos contribuiu no resultado final, em
    reais — "desse total, R$ 271 e compra e R$ 6,40 e comida jogada
    fora". Reconstroi os valores a partir da Solucao ja extraida (nao
    precisa das LpVariable originais), reaplicando os mesmos pesos e o
    mesmo sinal de `montar_objetivo` — por isso a soma das partes bate
    com o valor_objetivo do solver.

    Chama `preparar_catalogo` de novo (pura/determinística, ver seu
    docstring) para que os ids de lote de compra em solucao.descartes
    (ex.: "compra_arroz_2") sejam reconheciveis mesmo que o chamador
    tenha passado o catalogo original, sem os lotes de compra.
    """
    catalogo = preparar_catalogo(catalogo, parametros)
    pesos = parametros.pesos

    custo = sum(
        catalogo.ingredientes[ingrediente_id].preco_embalagem * embalagens
        for (ingrediente_id, _dia), embalagens in solucao.compras.items()
    )
    desperdicio = sum(
        catalogo.ingredientes[catalogo.lotes[lote_id].ingrediente_id].preco_unitario * quantidade
        for (lote_id, _dia), quantidade in solucao.descartes.items()
    )
    minutos = sum(
        catalogo.receitas[receita_id].tempo_min
        for (receita_id, _dia, _refeicao) in solucao.cardapio
    )
    pontos_preferencia = sum(
        catalogo.receitas[receita_id].preferencia
        for (receita_id, _dia, _refeicao) in solucao.cardapio
    )
    desvio = sum(solucao.aderencia["desvio_acima"].values()) + sum(
        solucao.aderencia["desvio_abaixo"].values()
    )
    folga = sum(solucao.aderencia["folga_falta"].values()) + sum(
        solucao.aderencia["folga_sobra"].values()
    )

    termos = {
        "custo": pesos.custo * custo,
        "desperdicio": pesos.desperdicio * desperdicio,
        "preparo": pesos.preparo * pesos.custo_por_minuto * minutos,
        "desvio": pesos.desvio * desvio,
        "folga": pesos.folga * folga,
        "preferencia": -pesos.preferencia * pesos.valor_por_ponto_preferencia * pontos_preferencia,
    }
    termos["total"] = sum(termos.values())
    return termos
