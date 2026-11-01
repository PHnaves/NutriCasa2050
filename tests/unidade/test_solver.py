from __future__ import annotations

from apoio_catalogo import construir_catalogo, membro, receita

from nutricasa2050.dominio import Parametros, Solucao
from nutricasa2050.otimizacao.solver import (
    _catalogo_smoke,
    _extrair_cardapio,
    _parametros_smoke,
    descrever_status,
    main,
    resolver,
)
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def test_smoke_resolve_e_da_optimal() -> None:
    solucao = resolver(_catalogo_smoke(), _parametros_smoke())

    assert solucao.status == "Optimal"


def test_main_smoke_devolve_codigo_zero() -> None:
    assert main(["--smoke"]) == 0


def test_resolver_devolve_objeto_solucao_completo() -> None:
    solucao = resolver(_catalogo_smoke(), _parametros_smoke())

    assert isinstance(solucao, Solucao)
    assert solucao.status == "Optimal"
    assert solucao.tempo_segundos >= 0
    assert solucao.valor_objetivo is not None
    assert solucao.cardapio
    assert solucao.porcoes
    assert isinstance(solucao.compras, dict)
    assert isinstance(solucao.descartes, dict)
    assert isinstance(solucao.estoque, dict)
    assert set(solucao.aderencia) == {
        "folga_falta",
        "folga_sobra",
        "desvio_acima",
        "desvio_abaixo",
    }


def test_infeasible_nao_levanta_excecao() -> None:
    """Desde o S3-06, R5 tem folga e nao fica mais Infeasible so por
    nutricao. Uma restricao alimentar (R6) que bloqueia a UNICA receita
    do UNICO membro ainda e genuinamente inviavel: R1 exige comer algo,
    R6 proibe tudo — nao ha folga que resolva isso.
    """
    tag = frozenset({"alergeno"})
    catalogo = construir_catalogo(
        receitas=[receita("r1", tags=tag)],
        membros=[membro("p1", tags_bloqueadas=tag)],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, orcamento=0.0, dias_compra=())

    solucao = resolver(catalogo, parametros)

    assert solucao.status == "Infeasible"
    assert solucao.valor_objetivo is None
    assert solucao.cardapio == {}


def test_descrever_status_traduz_infeasible() -> None:
    descricao = descrever_status("Infeasible")

    assert "nao existe cardapio" in descricao.lower()


def test_extracao_ignora_valores_zero() -> None:
    catalogo = construir_catalogo(
        receitas=[receita("r1"), receita("r2")],
        membros=[membro("p1")],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    chave_usada = ("r1", 1, "almoco")
    chave_nao_usada = ("r2", 1, "almoco")
    variaveis.x[chave_usada].varValue = 1.0
    variaveis.x[chave_nao_usada].varValue = 0.0

    extraido = _extrair_cardapio(variaveis)

    assert extraido == {chave_usada: 1.0}
