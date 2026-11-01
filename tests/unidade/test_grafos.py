"""Mapa de ingredientes (card S5-04, opcional) — grafo bipartido entre
receitas e ingredientes, e a confirmacao de que os orfaos (teoria) viram
lixo (dado real).
"""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, membro, receita

from nutricasa2050.analise.grafos import (
    componentes_conexas,
    cruzar_orfaos_com_desperdicio,
    grafo_de_substituicao,
    montar_grafo_bipartido,
)
from nutricasa2050.persistencia.banco import criar_schema
from nutricasa2050.persistencia.repositorio import gravar_cenario, gravar_descartes, gravar_execucao


def _catalogo_exemplo():
    return construir_catalogo(
        ingredientes=[
            ingrediente("arroz", "Arroz"),
            ingrediente("feijao", "Feijao"),
            ingrediente("cominho", "Cominho"),  # orfao: so uma receita usa
        ],
        receitas=[receita("arroz_feijao"), receita("feijao_tropeiro"), receita("arroz_simples")],
        matriz_a={
            ("arroz_feijao", "arroz"): 0.2,
            ("arroz_feijao", "feijao"): 0.2,
            ("feijao_tropeiro", "feijao"): 0.2,
            ("feijao_tropeiro", "cominho"): 0.01,
            ("arroz_simples", "arroz"): 0.2,
        },
        membros=[membro("p1")],
    )


def test_grafo_tem_uma_ligacao_por_par_da_matriz_a() -> None:
    catalogo = _catalogo_exemplo()

    grafo = montar_grafo_bipartido(catalogo)

    total_arestas = sum(len(vizinhos) for vizinhos in grafo.values()) // 2
    assert total_arestas == len(catalogo.matriz_a)


def test_detecta_orfaos_em_grafo_de_teste() -> None:
    catalogo = _catalogo_exemplo()

    grafo = montar_grafo_bipartido(catalogo)

    graus = {no: len(vizinhos) for no, vizinhos in grafo.items()}
    assert graus["i:cominho"] == 1
    assert graus["i:feijao"] == 2
    assert catalogo.ingredientes_orfaos() == ["cominho"]


def test_componentes_conexas_em_grafo_conhecido() -> None:
    """arroz_feijao e feijao_tropeiro compartilham feijao (1 componente);
    uma terceira receita isolada (nenhum ingrediente em comum) forma
    sua PROPRIA componente."""
    catalogo = construir_catalogo(
        ingredientes=[
            ingrediente("arroz", "Arroz"),
            ingrediente("feijao", "Feijao"),
            ingrediente("leite", "Leite"),
        ],
        receitas=[receita("arroz_feijao"), receita("feijao_tropeiro"), receita("vitamina")],
        matriz_a={
            ("arroz_feijao", "arroz"): 0.2,
            ("arroz_feijao", "feijao"): 0.2,
            ("feijao_tropeiro", "feijao"): 0.2,
            ("vitamina", "leite"): 0.3,
        },
        membros=[membro("p1")],
    )

    grafo = grafo_de_substituicao(catalogo)
    componentes = componentes_conexas(grafo)

    assert len(componentes) == 2
    tamanhos = sorted(len(c) for c in componentes)
    assert tamanhos == [1, 2]


def test_cruzar_orfaos_com_desperdicio_ordena_pelo_total_real(engine_memoria) -> None:
    criar_schema(engine_memoria)
    catalogo = construir_catalogo(
        ingredientes=[
            ingrediente("arroz", "Arroz"),
            ingrediente("feijao", "Feijao"),
            ingrediente("cominho", "Cominho"),
            ingrediente("acafrao", "Acafrao"),
        ],
        receitas=[
            receita("arroz_feijao"),
            receita("feijao_tropeiro"),
            receita("risoto"),
            receita("arroz_simples"),
        ],
        matriz_a={
            ("arroz_feijao", "arroz"): 0.2,
            ("arroz_feijao", "feijao"): 0.2,
            ("feijao_tropeiro", "feijao"): 0.2,
            ("feijao_tropeiro", "cominho"): 0.01,
            ("risoto", "acafrao"): 0.01,
            ("arroz_simples", "arroz"): 0.2,
        },
        membros=[membro("p1")],
    )
    assert sorted(catalogo.ingredientes_orfaos()) == ["acafrao", "cominho"]

    resultado_exemplo = {
        "resumo": {
            "status": "Optimal", "tempo_segundos": 0.1, "custo_total": 10.0,
            "valor_desperdicio": 5.0, "tempo_cozinha_minutos": 20,
        },
        "cardapio": [], "porcoes": [], "compras": [],
        "descartes": [
            {
                "lote_id": "L1",
                "ingrediente_id": "cominho",
                "dia": 1,
                "quantidade": 0.5,
                "valor": 2.0,
            },
        ],
        "aderencia": [],
    }
    cenario_id = gravar_cenario(engine_memoria, {"rodada": 0, "semente": 1})
    execucao_id = gravar_execucao(
        engine_memoria, resultado_exemplo, "humano", {}, cenario_id=cenario_id
    )
    gravar_descartes(engine_memoria, execucao_id, resultado_exemplo["descartes"])

    resultado = cruzar_orfaos_com_desperdicio(engine_memoria, catalogo)

    assert resultado[0]["ingrediente_id"] == "cominho"
    assert resultado[0]["desperdicio_observado"] == 0.5
    assert resultado[1]["ingrediente_id"] == "acafrao"
    assert resultado[1]["desperdicio_observado"] == 0.0
