"""Monte Carlo (card S4-04): roda N cenarios perturbados contra as tres
estrategias (otimizado, humano, guloso) e grava tudo no banco.
"""
from __future__ import annotations

import dataclasses

import pytest

from nutricasa2050.dados.carga import carregar_catalogo
from nutricasa2050.dominio import Parametros
from nutricasa2050.persistencia.banco import conexao, criar_schema
from nutricasa2050.simulacao import monte_carlo
from nutricasa2050.simulacao.cenarios import aplicar_cenario, gerar_cenario


def _catalogo_pequeno():
    catalogo = carregar_catalogo()
    primeiro_membro_id = next(iter(catalogo.membros))
    return dataclasses.replace(
        catalogo, membros={primeiro_membro_id: catalogo.membros[primeiro_membro_id]}
    )


def _parametros_pequenos():
    return Parametros(horizonte=1, refeicoes_por_dia=3, orcamento=200.0, dias_compra=(1,))


@pytest.mark.lento
def test_cinco_cenarios_gravam_quinze_execucoes(engine_memoria) -> None:
    criar_schema(engine_memoria)
    catalogo = _catalogo_pequeno()
    parametros = _parametros_pequenos()

    resumo = monte_carlo.rodar_monte_carlo(engine_memoria, catalogo, parametros, n_cenarios=5)

    assert resumo["sucesso"] == 5
    assert resumo["falhas"] == 0
    with conexao(engine_memoria) as conn:
        total_cenarios = conn.execute("SELECT COUNT(*) AS n FROM cenario").fetchone()["n"]
        total_execucoes = conn.execute("SELECT COUNT(*) AS n FROM execucao").fetchone()["n"]
    assert total_cenarios == 5
    assert total_execucoes == 15


def test_cenario_com_erro_nao_para_o_laco(engine_memoria, monkeypatch) -> None:
    criar_schema(engine_memoria)
    catalogo = _catalogo_pequeno()
    parametros = _parametros_pequenos()

    chamada_real = monte_carlo.rodar_um_cenario

    def _com_erro_na_semente_dois(engine, catalogo, parametros, semente, rodada=0):
        if semente == 2:
            raise RuntimeError("cenario de teste proposital")
        return chamada_real(engine, catalogo, parametros, semente, rodada=rodada)

    monkeypatch.setattr(monte_carlo, "rodar_um_cenario", _com_erro_na_semente_dois)

    resumo = monte_carlo.rodar_monte_carlo(engine_memoria, catalogo, parametros, n_cenarios=5)

    assert resumo["sucesso"] == 4
    assert resumo["falhas"] == 1
    assert resumo["detalhe_falhas"][0]["semente"] == 2


def test_as_tres_estrategias_usam_os_mesmos_dados(engine_memoria) -> None:
    """TESTE IMPORTANTE: se cada estrategia rodar sobre dados diferentes,
    a comparacao entre elas (e a manchete da apresentacao) e falsa.
    """
    criar_schema(engine_memoria)
    catalogo = _catalogo_pequeno()
    parametros = _parametros_pequenos()
    semente = 7

    monte_carlo.rodar_um_cenario(engine_memoria, catalogo, parametros, semente)

    cenario_obj = gerar_cenario(semente)
    catalogo_perturbado, _ = aplicar_cenario(catalogo, parametros, cenario_obj)
    algum_ingrediente_id = next(iter(catalogo_perturbado.ingredientes))
    preco_esperado = catalogo_perturbado.ingredientes[algum_ingrediente_id].preco_embalagem

    with conexao(engine_memoria) as conn:
        linhas = conn.execute(
            """
            SELECT execucao.estrategia, compra.custo, compra.quantidade
            FROM compra
            JOIN execucao ON execucao.id = compra.execucao_id
            WHERE compra.ingrediente = ?
            """,
            (algum_ingrediente_id,),
        ).fetchall()

    assert len(linhas) >= 1
    for linha in linhas:
        tamanho_embalagem = catalogo_perturbado.ingredientes[algum_ingrediente_id].tamanho_embalagem
        embalagens = linha["quantidade"] / tamanho_embalagem
        preco_unitario_embalagem = linha["custo"] / embalagens
        assert abs(preco_unitario_embalagem - preco_esperado) < 1e-6


def test_monte_carlo_e_reprodutivel(cfg) -> None:
    """Mesma semente inicial, mesmos totais — roda duas vezes, UMA POR
    VEZ (nao simultaneamente), porque o engine de :memory: usa shared
    cache (ver tests/conftest.py): dois ao mesmo tempo apontariam para o
    MESMO banco por baixo, nao para dois bancos independentes.
    """
    from nutricasa2050.persistencia.banco import criar_engine

    catalogo = _catalogo_pequeno()
    parametros = _parametros_pequenos()

    def _total_custo() -> float:
        engine = criar_engine(cfg, "sqlite:///:memory:")
        try:
            criar_schema(engine)
            monte_carlo.rodar_monte_carlo(engine, catalogo, parametros, n_cenarios=3)
            with conexao(engine) as conn:
                linha = conn.execute("SELECT SUM(total_custo) AS total FROM execucao").fetchone()
                return linha["total"]
        finally:
            if engine.conexao_compartilhada is not None:
                engine.conexao_compartilhada.close()

    total_a = _total_custo()
    total_b = _total_custo()

    assert total_a == total_b
