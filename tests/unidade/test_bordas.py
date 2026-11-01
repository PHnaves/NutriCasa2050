"""Casos de borda: tem que dar mensagem CLARA, nunca travar o programa
(card S2-12). Falhar mal e um KeyError na linha 143 de restricoes.py.
Falhar bem e "nao existe cardapio possivel: o orcamento de R$ 0,00 nao
cobre nem a refeicao mais barata do catalogo."
"""
from __future__ import annotations

import pytest
from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita

from nutricasa2050.dominio import Parametros
from nutricasa2050.otimizacao.solver import descrever_status, resolver


def _catalogo_basico(quantidade_inicial_estoque: float = 0.0):
    return construir_catalogo(
        ingredientes=[
            ingrediente("1", "Arroz", preco_embalagem=6.0, tamanho_embalagem=1.0)
        ],
        receitas=[receita("r1")],
        matriz_a={("r1", "1"): 0.2},
        lotes=[lote("L1", "1", quantidade=quantidade_inicial_estoque, dia_vencimento=180)],
        membros=[membro("p1", fator_porcao=1.0)],
    )


def test_geladeira_vazia_funciona_comprando_tudo() -> None:
    catalogo = _catalogo_basico(quantidade_inicial_estoque=0.0)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, orcamento=100.0, dias_compra=(1,))

    solucao = resolver(catalogo, parametros)

    assert solucao.status == "Optimal"
    assert solucao.compras  # precisou comprar, porque a geladeira estava vazia


def test_orcamento_zero_da_infeasible_com_mensagem() -> None:
    catalogo = _catalogo_basico(quantidade_inicial_estoque=0.0)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, orcamento=0.0, dias_compra=(1,))

    solucao = resolver(catalogo, parametros)

    assert solucao.status == "Infeasible"
    mensagem = descrever_status(solucao.status)
    assert "nao existe cardapio" in mensagem.lower() or "não existe cardápio" in mensagem.lower()


def test_todas_as_receitas_bloqueadas_da_infeasible_com_mensagem() -> None:
    """R6 (bloqueio por tag) ainda nao existe como restricao propria (card
    S3) — aqui simulamos o efeito fixando as porcoes em zero direto, do
    mesmo jeito que Membro.pode_comer() vai orientar o R6 de verdade."""
    tag = frozenset({"alto_sodio"})
    catalogo = construir_catalogo(
        receitas=[receita("r1", tags=tag), receita("r2", tags=tag)],
        membros=[membro("p1", tags_bloqueadas=tag)],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, orcamento=1000.0, dias_compra=(1,))

    bloqueado = catalogo.membros["p1"]
    assert all(not bloqueado.pode_comer(r) for r in catalogo.receitas.values())

    from pulp import PULP_CBC_CMD, LpStatus

    from nutricasa2050.otimizacao.modelo import construir
    from nutricasa2050.otimizacao.restricoes import r1_cobertura, r2_vinculo

    restricoes = [r1_cobertura, r2_vinculo]
    problema, variaveis = construir(catalogo, parametros, restricoes_ativas=restricoes)
    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    for receita_id, receita_obj in catalogo.receitas.items():
        if not bloqueado.pode_comer(receita_obj):
            problema += variaveis.y[("p1", receita_id, dia, refeicao)] == 0

    problema.solve(PULP_CBC_CMD(msg=False))
    status = LpStatus[problema.status]

    assert status == "Infeasible"
    assert "nao existe cardapio" in descrever_status(status).lower()


@pytest.mark.skip(reason="depende de R11 (tempo de preparo), que entra no card S3-05")
def test_dia_sem_tempo_de_cozinha_empurra_pratos_para_outros_dias() -> None:
    pass


def test_catalogo_com_uma_receita_so_nao_quebra() -> None:
    """Uma receita so pode dar Infeasible por causa da variedade (R4, que
    so entra no Sprint 3) — mas o importante aqui e que o solver devolve
    uma resposta clara (um status conhecido, sem levantar excecao)."""
    catalogo = construir_catalogo(
        ingredientes=[ingrediente("1", "Arroz")],
        receitas=[receita("r1")],
        matriz_a={("r1", "1"): 0.1},
        lotes=[lote("L1", "1", quantidade=10.0)],
        membros=[membro("p1")],
    )
    parametros = Parametros(horizonte=2, refeicoes_por_dia=1, orcamento=100.0, dias_compra=(1,))

    solucao = resolver(catalogo, parametros)

    assert solucao.status in {"Optimal", "Infeasible"}
    assert descrever_status(solucao.status)


def test_horizonte_de_um_dia_funciona() -> None:
    catalogo = _catalogo_basico(quantidade_inicial_estoque=5.0)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, orcamento=100.0, dias_compra=(1,))

    solucao = resolver(catalogo, parametros)

    assert solucao.status == "Optimal"
    assert len(parametros.dias) == 1
