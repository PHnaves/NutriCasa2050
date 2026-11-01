"""Dois baselines sem solver (cards S4-02 e S4-03) — comparados entre si
e contra o modelo otimizado. Sem baseline, "o modelo funciona" nao
significa nada: nao existe referencia.
"""
from __future__ import annotations

from dataclasses import replace

from apoio_catalogo import construir_catalogo, ingrediente, membro, receita
from pulp import PULP_CBC_CMD, LpStatus

from nutricasa2050.dominio import Parametros, Solucao
from nutricasa2050.otimizacao.modelo import RESTRICOES_ATIVAS, construir
from nutricasa2050.serializacao import resultado_para_dict
from nutricasa2050.simulacao.baselines import (
    baseline_guloso,
    baseline_humano,
    catalogo_com_compra_habitual,
)


def _catalogo_dois_perecíveis():
    """alface vence antes (dia 2) que tomate (dia 3); salada_mista usa os
    dois ao mesmo tempo, algo que so um planejamento de semana inteira
    (o otimizado) consegue explorar bem — o guloso so olha "qual receita
    consome mais do lote mais urgente" uma refeicao por vez."""
    return construir_catalogo(
        ingredientes=[
            ingrediente(
                "alface", "Alface", preco_embalagem=1.0, tamanho_embalagem=1.0, validade_dias=1
            ),
            ingrediente(
                "tomate", "Tomate", preco_embalagem=1.0, tamanho_embalagem=1.0, validade_dias=2
            ),
            ingrediente(
                "arroz", "Arroz", preco_embalagem=1.0, tamanho_embalagem=1.0, validade_dias=180
            ),
        ],
        receitas=[
            receita("salada_alface", preferencia=0.5, tempo_min=10),
            receita("molho_tomate", preferencia=0.5, tempo_min=10),
            receita("salada_mista", preferencia=0.5, tempo_min=10),
            receita("arroz_simples", preferencia=0.5, tempo_min=10),
        ],
        matriz_a={
            ("salada_alface", "alface"): 1.0,
            ("molho_tomate", "tomate"): 1.0,
            ("salada_mista", "alface"): 0.6,
            ("salada_mista", "tomate"): 0.6,
            ("arroz_simples", "arroz"): 1.0,
        },
        membros=[membro("p1", fator_porcao=1.0)],
    )


def _parametros():
    return Parametros(
        horizonte=5, refeicoes_por_dia=1, pratos_por_refeicao=1, orcamento=1000.0, dias_compra=(1,)
    )


def test_baseline_humano_devolve_o_mesmo_formato_do_solver() -> None:
    solucao = baseline_humano(_catalogo_dois_perecíveis(), _parametros())

    assert isinstance(solucao, Solucao)
    assert isinstance(solucao.cardapio, dict)
    assert isinstance(solucao.porcoes, dict)
    assert isinstance(solucao.compras, dict)
    assert isinstance(solucao.descartes, dict)
    assert set(solucao.aderencia) == {
        "folga_falta",
        "folga_sobra",
        "desvio_acima",
        "desvio_abaixo",
    }
    chave_cardapio = next(iter(solucao.cardapio))
    assert len(chave_cardapio) == 3
    chave_porcao = next(iter(solucao.porcoes))
    assert len(chave_porcao) == 4


def test_baseline_humano_preenche_todas_as_refeicoes() -> None:
    catalogo = _catalogo_dois_perecíveis()
    parametros = _parametros()

    solucao = baseline_humano(catalogo, parametros)

    dias_e_refeicoes_no_cardapio = {(dia, refeicao) for (_r, dia, refeicao) in solucao.cardapio}
    esperado = {(dia, refeicao) for dia in parametros.dias for refeicao in parametros.refeicoes}
    assert dias_e_refeicoes_no_cardapio == esperado


def test_baseline_humano_respeita_dias_consecutivos() -> None:
    solucao = baseline_humano(_catalogo_dois_perecíveis(), _parametros())

    por_refeicao: dict[str, list[tuple[int, str]]] = {}
    for receita_id, dia, refeicao in solucao.cardapio:
        por_refeicao.setdefault(refeicao, []).append((dia, receita_id))

    for lista in por_refeicao.values():
        lista.sort()
        for (dia_atual, receita_atual), (dia_seguinte, receita_seguinte) in zip(
            lista, lista[1:], strict=False
        ):
            if dia_seguinte == dia_atual + 1:
                assert receita_atual != receita_seguinte


def test_baseline_humano_gera_desperdicio() -> None:
    solucao = baseline_humano(_catalogo_dois_perecíveis(), _parametros())

    assert sum(solucao.descartes.values()) > 0


def test_item_esquecido_nao_e_comprado_mesmo_com_preco_inflado() -> None:
    """Regressao: a perturbacao esquecer_itens (S4-01) infla o preco em
    1000x para o SOLVER nunca escolher comprar — mas a compra habitual
    dos baselines nao olha preco, so quantidade. Sem checar
    Catalogo.itens_esquecidos, o baseline comprava igual, e um descarte
    desse item depois virava um valor em reais absurdo (preco x1000 x
    quantidade). Isso inflou a primeira rodada de validacao do S4-06
    para uma media de R$ 10 mil/semana de desperdicio — nunca mais pode
    voltar a acontecer.
    """
    catalogo = _catalogo_dois_perecíveis()
    catalogo_com_item_caro = replace(
        catalogo,
        ingredientes={
            **catalogo.ingredientes,
            "tomate": replace(
                catalogo.ingredientes["tomate"], preco_embalagem=1000.0
            ),
        },
        itens_esquecidos=frozenset({"tomate"}),
    )

    compras = baseline_humano(catalogo_com_item_caro, _parametros()).compras
    assert all(ingrediente_id != "tomate" for (ingrediente_id, _dia) in compras)


def test_descarte_do_baseline_e_serializavel() -> None:
    """Regressao: o descarte do baseline referencia um lote sintetico
    ("compra_habitual_*") que NAO existe no catalogo original — so
    dentro da simulacao interna. Sem passar por
    catalogo_com_compra_habitual antes, resultado_para_dict (que
    traduz lote -> ingrediente para calcular o valor em reais) quebra
    com KeyError. Isso derrubou os 40/40 cenarios da primeira rodada de
    validacao do S4-06 — nunca mais pode voltar a quebrar.
    """
    catalogo = _catalogo_dois_perecíveis()
    parametros = _parametros()
    solucao = baseline_humano(catalogo, parametros)
    assert solucao.descartes  # a premissa do teste: tem que ter descarte

    catalogo_expandido = catalogo_com_compra_habitual(catalogo, parametros)
    resultado = resultado_para_dict(solucao, catalogo_expandido, parametros)

    assert resultado["resumo"]["valor_desperdicio"] > 0


def test_guloso_prioriza_o_lote_mais_proximo_do_vencimento() -> None:
    catalogo = _catalogo_dois_perecíveis()
    parametros = _parametros()

    solucao = baseline_guloso(catalogo, parametros)

    primeira_refeicao = min(parametros.dias)
    primeira_receita = next(
        receita_id
        for (receita_id, dia, _refeicao) in solucao.cardapio
        if dia == primeira_refeicao
    )
    # Alface vence no dia 2, antes do tomate (dia 3) — a primeira escolha
    # tem que usar alface, o lote mais urgente.
    assert catalogo.quantidade(primeira_receita, "alface") > 0


def test_guloso_desperdica_menos_que_o_humano() -> None:
    catalogo = _catalogo_dois_perecíveis()
    parametros = _parametros()

    desperdicio_humano = sum(baseline_humano(catalogo, parametros).descartes.values())
    desperdicio_guloso = sum(baseline_guloso(catalogo, parametros).descartes.values())

    assert desperdicio_guloso < desperdicio_humano


def test_guloso_desperdica_mais_que_o_otimizado() -> None:
    """Sem R4 (variedade) de proposito: o ponto aqui e isolar o efeito da
    validade/estoque (R8-R10), nao a variedade — com R4, este catalogo
    minusculo (so 4 receitas) cai num impasse de cobertura que nao tem
    nada a ver com o que este teste mede."""
    catalogo = _catalogo_dois_perecíveis()
    parametros = _parametros()

    desperdicio_guloso = sum(baseline_guloso(catalogo, parametros).descartes.values())

    restricoes_sem_r4 = [r for r in RESTRICOES_ATIVAS if r.__name__ != "r4_variedade"]
    problema, variaveis = construir(catalogo, parametros, restricoes_ativas=restricoes_sem_r4)
    problema.solve(PULP_CBC_CMD(msg=False))
    assert LpStatus[problema.status] == "Optimal"
    desperdicio_otimizado = sum(v.varValue for v in variaveis.w.values() if v.varValue)

    assert desperdicio_guloso > desperdicio_otimizado
