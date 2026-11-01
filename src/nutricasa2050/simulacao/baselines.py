"""Dois baselines (cards S4-02 e S4-03): versoes SIMPLES do problema, sem
usar o solver, para comparar com o modelo otimizado. Sem baseline, dizer
"o modelo funciona" nao significa nada — nao existe referencia.

Os dois compartilham a mesma compra (_compra_habitual: uma estimativa
grosseira, derivada so da media do catalogo, NUNCA do cardapio realmente
escolhido — e assim na vida real: a familia compra por habito antes de
saber o que vai cozinhar) e a mesma simulacao dia a dia de estoque/
descarte (_atualizar_estoque_do_dia). A UNICA diferenca entre eles e
como cada um ESCOLHE o prato de cada refeicao.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import replace

from nutricasa2050.dominio import Catalogo, Lote, Parametros, Solucao

_ADERENCIA_VAZIA = {
    "folga_falta": {},
    "folga_sobra": {},
    "desvio_acima": {},
    "desvio_abaixo": {},
}


def _compra_habitual(catalogo: Catalogo, parametros: Parametros) -> dict[tuple[str, int], float]:
    """Quanto comprar de cada ingrediente, decidido ANTES de qualquer
    cardapio existir — so a partir de uma media grosseira de quanto o
    catalogo usa daquele ingrediente, com uma margem de 30% (comprar
    "um pouco mais, por garantia", o habito que gera a sobra).

    Ingredientes em catalogo.itens_esquecidos (S4-01) sao pulados de
    proposito: ESTA funcao nao olha preco, so quantidade — sem esse
    pulo, "esquecer um item" (que o otimizador ve como um preco
    proibitivo) nao faria diferenca nenhuma pra quem decide so pela
    quantidade habitual, e um descarte depois dele viraria um valor em
    reais sem nenhum sentido (preco x1000 x quantidade descartada).
    """
    if not parametros.dias_compra:
        dia_compra = parametros.dias[0]
    else:
        dia_compra = min(parametros.dias_compra)
    total_fator_porcao = sum(m.fator_porcao for m in catalogo.membros.values()) or 1.0
    total_refeicoes = len(parametros.dias) * len(parametros.refeicoes)
    total_receitas = max(catalogo.total_receitas(), 1)

    compras: dict[tuple[str, int], float] = {}
    for ingrediente_id, ingrediente in catalogo.ingredientes.items():
        if ingrediente_id in catalogo.itens_esquecidos:
            continue
        receitas_que_usam = catalogo.receitas_com_ingrediente(ingrediente_id)
        if not receitas_que_usam:
            continue
        quantidade_media_por_porcao = sum(
            catalogo.quantidade(r, ingrediente_id) for r in receitas_que_usam
        ) / len(receitas_que_usam)
        fracao_das_refeicoes = len(receitas_que_usam) / total_receitas
        demanda_estimada = (
            quantidade_media_por_porcao
            * total_fator_porcao
            * total_refeicoes
            * fracao_das_refeicoes
        )
        if demanda_estimada <= 0:
            continue
        embalagens = math.ceil((demanda_estimada * 1.3) / ingrediente.tamanho_embalagem)
        if embalagens > 0:
            compras[(ingrediente_id, dia_compra)] = float(embalagens)
    return compras


def catalogo_com_compra_habitual(catalogo: Catalogo, parametros: Parametros) -> Catalogo:
    """Mesma ideia de restricoes.preparar_catalogo (S3-01): pura e
    deterministica, devolve uma copia do catalogo com os lotes de
    "compra_habitual_*" ja incluidos em `lotes`.

    Por que precisa existir: `_montar_solucao` registra descartes usando
    o id sintetico "compra_habitual_{ingrediente}_{dia}" (ele nunca
    existiu no catalogo original — so dentro da simulacao interna dos
    baselines). Se `serializacao.resultado_para_dict` tentar traduzir
    esse id de volta para um ingrediente (para calcular o valor em
    reais do descarte) usando o catalogo ORIGINAL, da KeyError. Quem for
    serializar o resultado de um baseline tem que chamar isto primeiro
    e usar o catalogo devolvido — ver simulacao/monte_carlo.py.
    """
    compras = _compra_habitual(catalogo, parametros)
    lotes_extra = {
        f"compra_habitual_{ingrediente_id}_{dia}": Lote(
            id=f"compra_habitual_{ingrediente_id}_{dia}",
            ingrediente_id=ingrediente_id,
            quantidade=0.0,
            dia_vencimento=dia + catalogo.ingredientes[ingrediente_id].validade_dias,
            dia_compra=dia,
        )
        for (ingrediente_id, dia) in compras
    }
    return replace(catalogo, lotes={**catalogo.lotes, **lotes_extra})


def _estoque_inicial(
    catalogo: Catalogo, compras: dict[tuple[str, int], float]
) -> dict[str, float]:
    estoque = {lote_id: lote.quantidade for lote_id, lote in catalogo.lotes.items()}
    for (ingrediente_id, dia), embalagens in compras.items():
        lote_compra_id = f"compra_habitual_{ingrediente_id}_{dia}"
        ingrediente = catalogo.ingredientes[ingrediente_id]
        estoque[lote_compra_id] = embalagens * ingrediente.tamanho_embalagem
    return estoque


def _vencimento_por_lote(
    catalogo: Catalogo, compras: dict[tuple[str, int], float]
) -> dict[str, tuple[str, int]]:
    """lote_id -> (ingrediente_id, dia_vencimento), incluindo os lotes de
    compra habitual sintetizados por _estoque_inicial."""
    info = {
        lote_id: (lote.ingrediente_id, lote.dia_vencimento)
        for lote_id, lote in catalogo.lotes.items()
    }
    for ingrediente_id, dia in compras:
        ingrediente = catalogo.ingredientes[ingrediente_id]
        lote_compra_id = f"compra_habitual_{ingrediente_id}_{dia}"
        info[lote_compra_id] = (ingrediente_id, dia + ingrediente.validade_dias)
    return info


def _lotes_do_ingrediente(
    info_lotes: dict[str, tuple[str, int]], ingrediente_id: str
) -> list[str]:
    return [lote_id for lote_id, (ing, _) in info_lotes.items() if ing == ingrediente_id]


def _consumir(
    estoque: dict[str, float], lotes_ordenados: list[str], quantidade_necessaria: float
) -> float:
    """Consome `quantidade_necessaria` dos lotes, na ordem dada, parando
    quando acabar o estoque disponivel. Devolve o quanto foi REALMENTE
    consumido (pode ser menos que o pedido, se nao houver estoque)."""
    restante = quantidade_necessaria
    consumido_total = 0.0
    for lote_id in lotes_ordenados:
        if restante <= 1e-9:
            break
        disponivel = estoque.get(lote_id, 0.0)
        usado = min(disponivel, restante)
        estoque[lote_id] = disponivel - usado
        restante -= usado
        consumido_total += usado
    return consumido_total


def _descartar_vencidos(
    estoque: dict[str, float], info_lotes: dict[str, tuple[str, int]], dia: int
) -> dict[str, float]:
    """Zera (e registra) o que resta em qualquer lote cujo vencimento ja
    chegou neste dia — mesma regra de R10: a partir do dia do
    vencimento (inclusive), nao pode sobrar estoque."""
    descartado: dict[str, float] = {}
    for lote_id, (_ingrediente_id, dia_vencimento) in info_lotes.items():
        if dia < dia_vencimento:
            continue
        sobra = estoque.get(lote_id, 0.0)
        if sobra > 1e-9:
            descartado[lote_id] = sobra
            estoque[lote_id] = 0.0
    return descartado


def _calcular_aderencia(catalogo: Catalogo, parametros: Parametros, porcoes: dict) -> dict:
    """Mesma ideia de R5/R7 (S3-06), mas calculada por fora do solver: a
    folga/desvio sao a distancia da faixa/alvo que REALMENTE aconteceu,
    nao uma variavel de decisao. Sem isso, as consultas do S4-06
    (folgas_mais_frequentes) ficariam sempre zero para os baselines.
    """
    consumo: dict[tuple[str, str, int], float] = defaultdict(float)
    for (membro_id, receita_id, dia, _refeicao), fracao in porcoes.items():
        membro = catalogo.membros[membro_id]
        for nutriente in membro.faixas:
            valor_receita = catalogo.nutriente(receita_id, nutriente)
            if valor_receita:
                consumo[(membro_id, nutriente, dia)] += valor_receita * membro.fator_porcao * fracao

    aderencia = {
        "folga_falta": {},
        "folga_sobra": {},
        "desvio_acima": {},
        "desvio_abaixo": {},
    }
    for membro_id, membro in catalogo.membros.items():
        for nutriente, faixa in membro.faixas.items():
            for dia in parametros.dias:
                chave = (nutriente, membro_id, dia)
                valor = consumo.get((membro_id, nutriente, dia), 0.0)
                aderencia["folga_falta"][chave] = max(0.0, faixa.minimo - valor)
                aderencia["folga_sobra"][chave] = max(0.0, valor - faixa.maximo)
                aderencia["desvio_acima"][chave] = max(0.0, valor - faixa.alvo)
                aderencia["desvio_abaixo"][chave] = max(0.0, faixa.alvo - valor)
    return {chave: {k: v for k, v in sub.items() if v > 1e-9} for chave, sub in aderencia.items()}


def _montar_solucao(
    catalogo: Catalogo,
    parametros: Parametros,
    cardapio_escolhido: dict[tuple[int, str], str],
    compras: dict[tuple[str, int], float],
    descartes_totais: dict[tuple[str, int], float],
) -> Solucao:
    cardapio = {
        (receita_id, dia, refeicao): 1.0
        for (dia, refeicao), receita_id in cardapio_escolhido.items()
    }
    porcoes = {
        (membro_id, receita_id, dia, refeicao): 1.0
        for (dia, refeicao), receita_id in cardapio_escolhido.items()
        for membro_id in catalogo.membros
    }
    aderencia = _calcular_aderencia(catalogo, parametros, porcoes)

    return Solucao(
        status="Optimal",
        tempo_segundos=0.0,
        valor_objetivo=None,
        cardapio=cardapio,
        porcoes=porcoes,
        compras={chave: valor for chave, valor in compras.items() if valor > 1e-9},
        descartes={chave: valor for chave, valor in descartes_totais.items() if valor > 1e-9},
        estoque={},
        aderencia=aderencia,
    )


def _demanda_do_dia(
    catalogo: Catalogo, receita_id: str, ingrediente_id: str, dia: int, refeicao: str
) -> float:
    quantidade_por_porcao = catalogo.quantidade(receita_id, ingrediente_id)
    if quantidade_por_porcao <= 0:
        return 0.0
    if (dia, refeicao) in catalogo.refeicoes_puladas:
        return 0.0
    return quantidade_por_porcao * sum(m.fator_porcao for m in catalogo.membros.values())


def baseline_humano(catalogo: Catalogo, parametros: Parametros) -> Solucao:
    """Escolhe pelo que gosta (ordem de preferencia, maior primeiro),
    preenche as refeicoes em ordem so respeitando "nao repetir no dia
    seguinte", compra por habito (sem olhar o cardapio) e consome o
    estoque em qualquer ordem — sem checar o que vence primeiro. E o que
    uma familia faz hoje, sem otimizar nada.
    """
    receitas_ordenadas = [
        r.id for r in sorted(catalogo.receitas.values(), key=lambda r: r.preferencia, reverse=True)
    ]
    if not receitas_ordenadas:
        return _montar_solucao(catalogo, parametros, {}, {}, {})

    compras = _compra_habitual(catalogo, parametros)
    estoque = _estoque_inicial(catalogo, compras)
    info_lotes = _vencimento_por_lote(catalogo, compras)

    cardapio: dict[tuple[int, str], str] = {}
    descartes_totais: dict[tuple[str, int], float] = defaultdict(float)
    ultima_por_refeicao: dict[str, str | None] = dict.fromkeys(parametros.refeicoes)

    for dia in parametros.dias:
        for refeicao in parametros.refeicoes:
            if (dia, refeicao) in catalogo.refeicoes_puladas:
                continue
            escolhida = next(
                (r for r in receitas_ordenadas if r != ultima_por_refeicao[refeicao]),
                receitas_ordenadas[0],
            )
            cardapio[(dia, refeicao)] = escolhida
            ultima_por_refeicao[refeicao] = escolhida

            for ingrediente_id in catalogo.ingredientes_da_receita(escolhida):
                necessario = _demanda_do_dia(catalogo, escolhida, ingrediente_id, dia, refeicao)
                if necessario <= 0:
                    continue
                # Ordem ARBITRARIA (nao por vencimento) — e exatamente a
                # falta de cuidado que o baseline guloso (S4-03) corrige.
                lotes = _lotes_do_ingrediente(info_lotes, ingrediente_id)
                _consumir(estoque, lotes, necessario)

        for lote_id, quantidade in _descartar_vencidos(estoque, info_lotes, dia).items():
            descartes_totais[(lote_id, dia)] += quantidade

    return _montar_solucao(catalogo, parametros, cardapio, compras, descartes_totais)


def baseline_guloso(catalogo: Catalogo, parametros: Parametros) -> Solucao:
    """Para cada refeicao, em ordem de dia: olha os lotes disponiveis,
    ordenados por proximidade do vencimento, e escolhe a receita que
    consome MAIS do lote mais urgente. Miope por definicao — decide uma
    refeicao por vez, sem planejar a semana — mas pelo menos reage ao
    que esta vencendo, o que ja evita bastante desperdicio.
    """
    if not catalogo.receitas:
        return _montar_solucao(catalogo, parametros, {}, {}, {})

    receitas_por_preferencia = [
        r.id for r in sorted(catalogo.receitas.values(), key=lambda r: r.preferencia, reverse=True)
    ]

    compras = _compra_habitual(catalogo, parametros)
    estoque = _estoque_inicial(catalogo, compras)
    info_lotes = _vencimento_por_lote(catalogo, compras)

    cardapio: dict[tuple[int, str], str] = {}
    descartes_totais: dict[tuple[str, int], float] = defaultdict(float)

    for dia in parametros.dias:
        for refeicao in parametros.refeicoes:
            if (dia, refeicao) in catalogo.refeicoes_puladas:
                continue

            lotes_urgentes = sorted(
                (lote_id for lote_id, qtd in estoque.items() if qtd > 1e-9),
                key=lambda lote_id: info_lotes[lote_id][1],
            )

            escolhida = None
            for lote_id in lotes_urgentes:
                ingrediente_id, _vencimento = info_lotes[lote_id]
                candidatas = catalogo.receitas_com_ingrediente(ingrediente_id)
                if not candidatas:
                    continue
                escolhida = max(
                    candidatas, key=lambda r: catalogo.quantidade(r, ingrediente_id)
                )
                break
            if escolhida is None:
                escolhida = receitas_por_preferencia[0]

            cardapio[(dia, refeicao)] = escolhida
            for ingrediente_id in catalogo.ingredientes_da_receita(escolhida):
                necessario = _demanda_do_dia(catalogo, escolhida, ingrediente_id, dia, refeicao)
                if necessario <= 0:
                    continue
                lotes = sorted(
                    _lotes_do_ingrediente(info_lotes, ingrediente_id),
                    key=lambda lote_id: info_lotes[lote_id][1],
                )
                _consumir(estoque, lotes, necessario)

        for lote_id, quantidade in _descartar_vencidos(estoque, info_lotes, dia).items():
            descartes_totais[(lote_id, dia)] += quantidade

    return _montar_solucao(catalogo, parametros, cardapio, compras, descartes_totais)
