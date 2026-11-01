"""Os quatro numeros da apresentacao (card S4-06, MARCO do Sprint 4). Cada
funcao devolve so o numero — a conversa com o banco fica toda aqui, nada
disso se espalha para quem for montar o slide ou o relatorio.
"""
from __future__ import annotations

import math
from dataclasses import replace

from pulp import LpStatus

from nutricasa2050.dominio import Catalogo, Parametros
from nutricasa2050.otimizacao.modelo import construir
from nutricasa2050.otimizacao.objetivo import termo_custo, termo_tempo
from nutricasa2050.otimizacao.solver import _escolher_solver
from nutricasa2050.persistencia.banco import EngineSQLite, conexao

ESTRATEGIA_OTIMIZADA = "otimizado"
ESTRATEGIA_HUMANA = "humano"


def desperdicio_por_estrategia(engine: EngineSQLite) -> dict[str, float]:
    """Media do desperdicio (R$) de cada estrategia, sobre todas as
    execucoes gravadas (uma por cenario x estrategia)."""
    with conexao(engine) as conn:
        linhas = conn.execute(
            "SELECT estrategia, AVG(total_descarte) AS media FROM execucao GROUP BY estrategia"
        ).fetchall()
    return {linha["estrategia"]: linha["media"] or 0.0 for linha in linhas}


def reducao_de_desperdicio(engine: EngineSQLite) -> float:
    """Quanto por cento o modelo otimizado reduz o desperdicio em relacao
    a familia normal (baseline humano). E A MANCHETE da apresentacao."""
    medias = desperdicio_por_estrategia(engine)
    desperdicio_humano = medias.get(ESTRATEGIA_HUMANA, 0.0)
    desperdicio_otimizado = medias.get(ESTRATEGIA_OTIMIZADA, 0.0)
    if desperdicio_humano <= 0:
        return 0.0
    return (desperdicio_humano - desperdicio_otimizado) / desperdicio_humano * 100.0


_SEMANAS_POR_MES = 30.0 / 7.0


def economia_mensal(engine: EngineSQLite) -> tuple[float, float, float]:
    """Economia projetada por mes (custo de compra + valor desperdicado,
    otimizado vs. humano), com intervalo de confianca de 95% vindo da
    variancia entre os cenarios da Monte Carlo — devolve (media,
    limite_inferior, limite_superior)."""
    with conexao(engine) as conn:
        linhas = conn.execute(
            """
            SELECT cenario_id, estrategia, total_custo, total_descarte
            FROM execucao
            WHERE estrategia IN (?, ?)
            """,
            (ESTRATEGIA_OTIMIZADA, ESTRATEGIA_HUMANA),
        ).fetchall()

    por_cenario: dict[int, dict[str, float]] = {}
    for linha in linhas:
        gasto_total = (linha["total_custo"] or 0.0) + (linha["total_descarte"] or 0.0)
        por_cenario.setdefault(linha["cenario_id"], {})[linha["estrategia"]] = gasto_total

    economias_semanais = [
        valores[ESTRATEGIA_HUMANA] - valores[ESTRATEGIA_OTIMIZADA]
        for valores in por_cenario.values()
        if ESTRATEGIA_HUMANA in valores and ESTRATEGIA_OTIMIZADA in valores
    ]
    if not economias_semanais:
        return (0.0, 0.0, 0.0)

    economias_mensais = [valor * _SEMANAS_POR_MES for valor in economias_semanais]
    n = len(economias_mensais)
    media = sum(economias_mensais) / n
    if n < 2:
        return (media, media, media)

    variancia = sum((valor - media) ** 2 for valor in economias_mensais) / (n - 1)
    erro_padrao = math.sqrt(variancia / n)
    margem = 1.96 * erro_padrao
    return (media, media - margem, media + margem)


def preco_da_prescricao(catalogo: Catalogo, parametros: Parametros) -> dict[str, float]:
    """Roda o modelo DUAS VEZES — uma com as faixas da nutricionista, uma
    sem — e devolve a diferenca em reais e em minutos de cozinha. "Seguir
    esta dieta custa R$ X a mais por semana e Y minutos a mais de
    cozinha": nenhuma nutricionista consegue dizer isso hoje, e aqui e
    so uma subtracao.

    Usa termo_custo (so a compra, em reais de verdade), NAO o objetivo
    completo — o objetivo mistura compra com folga/desvio ponderados
    (Pesos.folga = 1000x, S3-06), e quando a nutricao fica dificil a
    folga domina o numero a ponto de "R$ 38 por semana" virar "R$ 5
    milhoes": tecnicamente correto para o solver minimizar, mas inutil
    como resposta para a nutricionista.
    """

    def _resolver(catalogo_a_usar: Catalogo) -> tuple[float, float]:
        problema, variaveis = construir(catalogo_a_usar, parametros)
        problema.solve(_escolher_solver(parametros))
        if LpStatus[problema.status] not in ("Optimal", "Not Solved"):
            return (0.0, 0.0)
        custo = termo_custo(variaveis, catalogo_a_usar, parametros).value() or 0.0
        termo_tempo_em_reais = termo_tempo(variaveis, catalogo_a_usar, parametros).value() or 0.0
        custo_por_minuto = parametros.pesos.custo_por_minuto
        minutos_brutos = termo_tempo_em_reais / custo_por_minuto if custo_por_minuto else 0.0
        return (custo, minutos_brutos)

    custo_com_faixas, minutos_com_faixas = _resolver(catalogo)

    membros_sem_faixas = {
        membro_id: replace(membro, faixas={}) for membro_id, membro in catalogo.membros.items()
    }
    catalogo_sem_faixas = replace(catalogo, membros=membros_sem_faixas)
    custo_sem_faixas, minutos_sem_faixas = _resolver(catalogo_sem_faixas)

    return {
        "reais_por_semana": custo_com_faixas - custo_sem_faixas,
        "minutos_de_cozinha": minutos_com_faixas - minutos_sem_faixas,
    }


def folgas_mais_frequentes(engine: EngineSQLite) -> list[dict]:
    """Agrupa a tabela aderencia por membro e nutriente, contando em
    quantos cenarios/execucoes a folga foi maior que zero — responde "de
    todas as regras da nutricionista, qual a realidade mais atropela?",
    saindo de um GROUP BY.
    """
    with conexao(engine) as conn:
        linhas = conn.execute(
            """
            SELECT membro, regra AS nutriente, COUNT(*) AS vezes_com_folga,
                   AVG(folga) AS folga_media
            FROM aderencia
            WHERE folga > 0
            GROUP BY membro, regra
            ORDER BY vezes_com_folga DESC, folga_media DESC
            """
        ).fetchall()
    return [
        {
            "membro_id": linha["membro"],
            "nutriente": linha["nutriente"],
            "vezes_com_folga": linha["vezes_com_folga"],
            "folga_media": linha["folga_media"],
        }
        for linha in linhas
    ]
