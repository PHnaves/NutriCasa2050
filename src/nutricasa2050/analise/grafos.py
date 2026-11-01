"""Mapa de ingredientes (card S5-04, opcional). Receitas e ingredientes
ligados num grafo BIPARTIDO: dois grupos de nos (receitas de um lado,
ingredientes do outro) com arestas entre eles. Os ingredientes que SO
UMA receita usa (os orfaos, Catalogo.ingredientes_orfaos) sao
justamente os que mais viram lixo, porque quando sobram nao existe
outra receita para consumi-los — e isso que cruzar_orfaos_com_desperdicio
confirma com dado real.

Representacao escolhida: um dict simples de adjacencia (no -> conjunto
de vizinhos), sem depender de bibliotecas de grafos — e so o que
componentes_conexas (busca em largura) precisa. Os nos do lado das
receitas e dos ingredientes usam prefixos ("r:"/"i:") para nunca
colidir, mesmo que um id de receita e um de ingrediente sejam iguais.
"""
from __future__ import annotations

from nutricasa2050.dominio import Catalogo
from nutricasa2050.persistencia.banco import EngineSQLite, conexao

Grafo = dict[str, set[str]]


def _no_receita(receita_id: str) -> str:
    return f"r:{receita_id}"


def _no_ingrediente(ingrediente_id: str) -> str:
    return f"i:{ingrediente_id}"


def montar_grafo_bipartido(catalogo: Catalogo) -> Grafo:
    """Dois conjuntos de nos (receitas, ingredientes) e uma aresta por
    par (receita, ingrediente) que aparece na matriz A."""
    grafo: Grafo = {}
    for receita_id in catalogo.receitas:
        grafo.setdefault(_no_receita(receita_id), set())
    for ingrediente_id in catalogo.ingredientes:
        grafo.setdefault(_no_ingrediente(ingrediente_id), set())

    for receita_id, ingrediente_id in catalogo.matriz_a:
        no_r, no_i = _no_receita(receita_id), _no_ingrediente(ingrediente_id)
        grafo.setdefault(no_r, set()).add(no_i)
        grafo.setdefault(no_i, set()).add(no_r)
    return grafo


def grafo_de_substituicao(catalogo: Catalogo) -> Grafo:
    """Quais receitas compartilham ingredientes entre si — receitas
    conectadas podem se substituir sem gerar sobra, porque quem
    sobrar de uma pode ser aproveitado pela outra."""
    grafo: Grafo = {receita_id: set() for receita_id in catalogo.receitas}
    for ingrediente_id in catalogo.ingredientes:
        receitas = catalogo.receitas_com_ingrediente(ingrediente_id)
        for i, receita_a in enumerate(receitas):
            for receita_b in receitas[i + 1 :]:
                grafo[receita_a].add(receita_b)
                grafo[receita_b].add(receita_a)
    return grafo


def componentes_conexas(grafo: Grafo) -> list[set[str]]:
    """Grupos de nos que se conectam entre si mas nao com o resto —
    busca em largura simples, sem biblioteca externa."""
    visitados: set[str] = set()
    componentes: list[set[str]] = []

    for no_inicial in grafo:
        if no_inicial in visitados:
            continue
        componente: set[str] = set()
        fila = [no_inicial]
        while fila:
            no = fila.pop()
            if no in componente:
                continue
            componente.add(no)
            fila.extend(grafo.get(no, ()))
        visitados |= componente
        componentes.append(componente)

    return componentes


def cruzar_orfaos_com_desperdicio(engine: EngineSQLite, catalogo: Catalogo) -> list[dict]:
    """Os ingredientes orfaos (usados por menos de 2 receitas),
    ORDENADOS PELO DESPERDICIO REAL observado nos cenarios da Monte
    Carlo (card S4-04) — a funcao que transforma teoria de grafos em
    resultado: mostra que a previsao teorica ("orfaos viram lixo") se
    confirmou nos dados, nao so no desenho.
    """
    orfaos = catalogo.ingredientes_orfaos()
    with conexao(engine) as conn:
        linhas = conn.execute(
            "SELECT ingrediente, SUM(quantidade) AS total FROM descarte GROUP BY ingrediente"
        ).fetchall()
    desperdicio_por_ingrediente = {linha["ingrediente"]: linha["total"] or 0.0 for linha in linhas}

    resultado = [
        {
            "ingrediente_id": ingrediente_id,
            "nome": catalogo.ingredientes[ingrediente_id].nome,
            "desperdicio_observado": desperdicio_por_ingrediente.get(ingrediente_id, 0.0),
        }
        for ingrediente_id in orfaos
    ]
    resultado.sort(key=lambda item: item["desperdicio_observado"], reverse=True)
    return resultado
