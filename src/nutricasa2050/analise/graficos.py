"""Os gráficos do "nao existe almoço gratis" (card S5-02) e o desenho da
geometria por tras do modelo (card S5-03). Nao se testa a APARENCIA de
um grafico — testa-se que a funcao devolve o numero certo de pontos, que
o arquivo foi criado e nao esta vazio, e que a relacao matematica
esperada se mantem (ver os testes).
"""
from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sem isso, tentar desenhar sem display quebra o CI/servidor.
import matplotlib.pyplot as plt  # noqa: E402 — precisa vir depois do matplotlib.use

from nutricasa2050.dominio import Catalogo, Parametros  # noqa: E402
from nutricasa2050.otimizacao.solver import resolver  # noqa: E402
from nutricasa2050.persistencia.banco import EngineSQLite, conexao  # noqa: E402
from nutricasa2050.serializacao import resultado_para_dict  # noqa: E402

# ============================ S5-02 — Pareto ===============================


def varrer_peso(
    catalogo: Catalogo, parametros: Parametros, nome_do_peso: str, valores: list[float]
) -> list[dict]:
    """Roda o modelo uma vez para cada valor do peso `nome_do_peso`
    (um campo de Pesos, ex.: "desperdicio") e devolve custo, desperdicio
    e desvio total de cada rodada — a materia-prima da fronteira de
    Pareto."""
    pontos = []
    for valor in valores:
        pesos = replace(parametros.pesos, **{nome_do_peso: valor})
        parametros_variados = replace(parametros, pesos=pesos)
        solucao = resolver(catalogo, parametros_variados)
        resultado = resultado_para_dict(solucao, catalogo, parametros_variados)
        resumo = resultado["resumo"]
        desvio_total = sum(abs(item["desvio"]) for item in resultado["aderencia"])
        pontos.append(
            {
                "peso": valor,
                "status": solucao.status,
                "custo": resumo["custo_total"],
                "desperdicio": resumo["valor_desperdicio"],
                "desvio": desvio_total,
            }
        )
    return pontos


def _salvar_grafico(caminho: str | Path) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(caminho, bbox_inches="tight")
    plt.close()


def grafico_pareto_custo_desperdicio(pontos: list[dict], caminho: str | Path) -> None:
    fig, ax = plt.subplots()
    custos = [p["custo"] for p in pontos]
    desperdicios = [p["desperdicio"] for p in pontos]
    ax.plot(custos, desperdicios, "o-", color="#1D8A66")
    ax.set_xlabel("Custo de compra (R$/semana)")
    ax.set_ylabel("Desperdicio (R$/semana)")
    ax.set_title('Nao existe almoco gratis: custo x desperdicio')
    fig.text(
        0.1, -0.05,
        "Reduzir o desperdicio custa dinheiro — cada ponto e um peso diferente do mesmo modelo.",
        fontsize=8, ha="left",
    )
    _salvar_grafico(caminho)


def grafico_pareto_custo_aderencia(pontos: list[dict], caminho: str | Path) -> None:
    fig, ax = plt.subplots()
    custos = [p["custo"] for p in pontos]
    desvios = [p["desvio"] for p in pontos]
    ax.plot(custos, desvios, "o-", color="#E8912A")
    ax.set_xlabel("Custo de compra (R$/semana)")
    ax.set_ylabel("Desvio total do alvo nutricional")
    ax.set_title("Nao existe almoco gratis: custo x aderencia nutricional")
    fig.text(
        0.1, -0.05,
        "Seguir a dieta a risca tambem custa dinheiro — a mesma troca, vista por outro angulo.",
        fontsize=8, ha="left",
    )
    _salvar_grafico(caminho)


def grafico_desperdicio_por_cenario(engine: EngineSQLite, caminho: str | Path) -> None:
    """Boxplot do desperdicio das tres estrategias nos cenarios da Monte
    Carlo (card S4-04) — mostra que a vantagem do modelo nao foi sorte
    com um cenario especifico."""
    with conexao(engine) as conn:
        linhas = conn.execute(
            "SELECT estrategia, total_descarte FROM execucao ORDER BY estrategia"
        ).fetchall()

    por_estrategia: dict[str, list[float]] = {}
    for linha in linhas:
        por_estrategia.setdefault(linha["estrategia"], []).append(linha["total_descarte"] or 0.0)

    fig, ax = plt.subplots()
    nomes = sorted(por_estrategia)
    dados = [por_estrategia[nome] for nome in nomes]
    ax.boxplot(dados, tick_labels=nomes)
    ax.set_ylabel("Desperdicio por execucao (R$)")
    ax.set_title("Distribuicao do desperdicio nos cenarios da Monte Carlo")
    fig.text(
        0.1, -0.05,
        "Cada caixa resume centenas de cenarios perturbados — a mesma estrategia,\n"
        "dados diferentes.",
        fontsize=8, ha="left",
    )
    _salvar_grafico(caminho)


# ======================= S5-03 — geometria em 2D ============================

# Restricao linear: a*x1 + b*x2 {op} c. op e "<=" ou ">=".
Restricao = tuple[float, float, str, float]


def modelo_reduzido_2d() -> tuple:
    """Uma versao MINUSCULA do modelo (2 "receitas", no estilo do
    problema de Stigler que inspirou o projeto — ver notebooks/00_stigler.ipynb):
    x1 = porcoes de arroz, x2 = porcoes de feijao.

    minimizar  2 x1 + 3 x2                     (custo)
    sujeito a    x1 +   x2 >= 4                 (R5 — nutriente A, minimo)
               2 x1 +   x2 >= 4                 (R5 — nutriente B, minimo)
                    x1      <= 3                (R12 — orcamento/estoque de arroz)
                         x2 <= 5                (estoque de feijao)
    x1, x2 >= 0

    Nao precisa ter nada a ver com os dados reais — precisa ser
    DESENHAVEL (duas variaveis, poucas restricoes). O teto em x2 fecha a
    regiao num poligono LIMITADO — sem ele, a regiao viavel so tem 2
    vertices finitos e se estende ao infinito (x2 -> inf), o que nao da
    pra desenhar nem sombrear como um poligono de verdade.
    """
    from pulp import LpMinimize, LpProblem, LpVariable

    problema = LpProblem("modelo_reduzido_2d", LpMinimize)
    x1 = LpVariable("x1", lowBound=0)
    x2 = LpVariable("x2", lowBound=0)
    problema += 2 * x1 + 3 * x2, "custo"
    problema += (x1 + x2 >= 4, "nutriente_a")
    problema += (2 * x1 + x2 >= 4, "nutriente_b")
    problema += (x1 <= 3, "estoque_de_arroz")
    problema += (x2 <= 5, "estoque_de_feijao")
    return problema, {"x1": x1, "x2": x2}


def restricoes_do_modelo_reduzido() -> list[Restricao]:
    return [
        (1.0, 1.0, ">=", 4.0),
        (2.0, 1.0, ">=", 4.0),
        (1.0, 0.0, "<=", 3.0),
        (0.0, 1.0, "<=", 5.0),
        (1.0, 0.0, ">=", 0.0),
        (0.0, 1.0, ">=", 0.0),
    ]


def _satisfaz(restricao: Restricao, ponto: tuple[float, float], tolerancia: float = 1e-6) -> bool:
    a, b, op, c = restricao
    valor = a * ponto[0] + b * ponto[1]
    if op == "<=":
        return valor <= c + tolerancia
    return valor >= c - tolerancia


def _intersecao(r1: Restricao, r2: Restricao) -> tuple[float, float] | None:
    a1, b1, _, c1 = r1
    a2, b2, _, c2 = r2
    determinante = a1 * b2 - a2 * b1
    if abs(determinante) < 1e-12:
        return None
    x1 = (c1 * b2 - c2 * b1) / determinante
    x2 = (a1 * c2 - a2 * c1) / determinante
    return (x1, x2)


def calcular_regiao_viavel(restricoes: list[Restricao]) -> list[tuple[float, float]]:
    """Os vertices do poligono viavel: interseção de cada par de retas
    que tambem satisfaz TODAS as outras restricoes, ordenados pelo
    angulo em torno do centroide (para desenhar o contorno sem cruzar
    linhas)."""
    candidatos = []
    for r1, r2 in combinations(restricoes, 2):
        ponto = _intersecao(r1, r2)
        if ponto is None:
            continue
        if all(_satisfaz(r, ponto) for r in restricoes):
            candidatos.append(ponto)

    # Remove duplicatas (a mesma interseccao aparece em varios pares).
    vertices: list[tuple[float, float]] = []
    for ponto in candidatos:
        if not any(abs(ponto[0] - v[0]) < 1e-6 and abs(ponto[1] - v[1]) < 1e-6 for v in vertices):
            vertices.append(ponto)

    if len(vertices) < 3:
        return vertices

    cx = sum(v[0] for v in vertices) / len(vertices)
    cy = sum(v[1] for v in vertices) / len(vertices)
    import math

    vertices.sort(key=lambda v: math.atan2(v[1] - cy, v[0] - cx))
    return vertices


def grafico_regiao_viavel(caminho: str | Path) -> None:
    from pulp import PULP_CBC_CMD, LpStatus

    problema, variaveis = modelo_reduzido_2d()
    problema.solve(PULP_CBC_CMD(msg=False))
    assert LpStatus[problema.status] == "Optimal"
    otimo = (variaveis["x1"].varValue, variaveis["x2"].varValue)

    restricoes = restricoes_do_modelo_reduzido()
    vertices = calcular_regiao_viavel(restricoes)

    fig, ax = plt.subplots()

    eixo_x = [0.0, 6.0]
    for a, b, _op, c in restricoes:
        if abs(b) > 1e-9:
            ys = [(c - a * x) / b for x in eixo_x]
            ax.plot(eixo_x, ys, "--", color="gray", linewidth=1)

    if len(vertices) >= 3:
        poligono = [*vertices, vertices[0]]
        ax.fill(
            [v[0] for v in poligono], [v[1] for v in poligono], color="#1D8A66", alpha=0.25
        )
        ax.plot([v[0] for v in poligono], [v[1] for v in poligono], color="#1D8A66")

    custo_otimo = 2 * otimo[0] + 3 * otimo[1]
    for nivel in (custo_otimo * 0.7, custo_otimo, custo_otimo * 1.3):
        xs = [x for x in (0.0, 6.0)]
        ys = [(nivel - 2 * x) / 3 for x in xs]
        ax.plot(xs, ys, ":", color="#E8912A", linewidth=1)

    ax.plot(*otimo, "o", color="#E8912A", markersize=10, zorder=5)
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 5)
    ax.set_xlabel("x1 (porcoes de arroz)")
    ax.set_ylabel("x2 (porcoes de feijao)")
    ax.set_title("Regiao viavel e o otimo num vertice")
    fig.text(
        0.1, -0.05,
        "A area sombreada e viavel; as linhas pontilhadas sao o custo constante —\n"
        "o otimo cai num vertice.",
        fontsize=8, ha="left",
    )
    _salvar_grafico(caminho)
