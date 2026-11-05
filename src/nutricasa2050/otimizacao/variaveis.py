from __future__ import annotations

from dataclasses import dataclass

from pulp import LpVariable

from nutricasa2050.dominio import Catalogo, Parametros

# Chaves: ver docs/formulacao.md (Secao 3) e o card S2-03.
ChaveX = tuple[str, int, str]  # (receita_id, dia, refeicao)
ChaveY = tuple[str, str, int, str]  # (membro_id, receita_id, dia, refeicao)
ChaveIngredienteDia = tuple[str, int]  # (ingrediente_id, dia)
ChaveLoteDia = tuple[str, int]  # (lote_id, dia)
ChaveNutrienteMembroDia = tuple[str, str, int]  # (nutriente, membro_id, dia)


@dataclass
class Variaveis:
    x: dict[ChaveX, LpVariable]
    y: dict[ChaveY, LpVariable]
    b: dict[ChaveIngredienteDia, LpVariable]
    s: dict[ChaveLoteDia, LpVariable]
    u: dict[ChaveLoteDia, LpVariable]
    w: dict[ChaveLoteDia, LpVariable]
    folga_falta: dict[ChaveNutrienteMembroDia, LpVariable]
    folga_sobra: dict[ChaveNutrienteMembroDia, LpVariable]
    desvio_acima: dict[ChaveNutrienteMembroDia, LpVariable]
    desvio_abaixo: dict[ChaveNutrienteMembroDia, LpVariable]


def nutrientes_acompanhados(catalogo: Catalogo) -> list[str]:
    return sorted({nutriente for (_, nutriente) in catalogo.nutrientes})


def criar_variaveis(catalogo: Catalogo, parametros: Parametros) -> Variaveis:
    dias = parametros.dias
    refeicoes = parametros.refeicoes
    nutrientes = nutrientes_acompanhados(catalogo)

    x = {
        (receita_id, dia, refeicao): LpVariable(
            f"x_{receita_id}_{dia}_{refeicao}", cat="Binary"
        )
        for receita_id in catalogo.receitas
        for dia in dias
        for refeicao in refeicoes
    }

    y = {
        (membro_id, receita_id, dia, refeicao): LpVariable(
            f"y_{membro_id}_{receita_id}_{dia}_{refeicao}",
            lowBound=0,
            upBound=1,
            cat="Continuous",
        )
        for membro_id in catalogo.membros
        for receita_id in catalogo.receitas
        for dia in dias
        for refeicao in refeicoes
    }

    # Item "esquecido" na compra (Monte Carlo, S4-01): nao pode ser comprado
    # nesta semana (upBound=0). Ate o Sprint 6 isso era feito multiplicando
    # o PRECO por 1000 — e o mesmo preco inflado valorava o descarte do
    # estoque inicial daquele item, inflando o desperdicio de todas as
    # estrategias (ver docs/resultados.md, correcao de precos).
    b = {
        (ingrediente_id, dia): LpVariable(
            f"b_{ingrediente_id}_{dia}",
            lowBound=0,
            upBound=0 if ingrediente_id in catalogo.itens_esquecidos else None,
            cat="Integer",
        )
        for ingrediente_id in catalogo.ingredientes
        for dia in parametros.dias_compra
    }

    s = {
        (lote_id, dia): LpVariable(f"s_{lote_id}_{dia}", lowBound=0, cat="Continuous")
        for lote_id in catalogo.lotes
        for dia in dias
    }

    u = {
        (lote_id, dia): LpVariable(f"u_{lote_id}_{dia}", lowBound=0, cat="Continuous")
        for lote_id in catalogo.lotes
        for dia in dias
    }

    w = {
        (lote_id, dia): LpVariable(f"w_{lote_id}_{dia}", lowBound=0, cat="Continuous")
        for lote_id in catalogo.lotes
        for dia in dias
    }

    def _variaveis_de_folga(prefixo: str) -> dict[ChaveNutrienteMembroDia, LpVariable]:
        return {
            (nutriente, membro_id, dia): LpVariable(
                f"{prefixo}_{nutriente}_{membro_id}_{dia}", lowBound=0, cat="Continuous"
            )
            for nutriente in nutrientes
            for membro_id in catalogo.membros
            for dia in dias
        }

    return Variaveis(
        x=x,
        y=y,
        b=b,
        s=s,
        u=u,
        w=w,
        folga_falta=_variaveis_de_folga("folga_falta"),
        folga_sobra=_variaveis_de_folga("folga_sobra"),
        desvio_acima=_variaveis_de_folga("desvio_acima"),
        desvio_abaixo=_variaveis_de_folga("desvio_abaixo"),
    )


def contar_variaveis(variaveis: Variaveis) -> dict[str, int]:
    return {
        "x": len(variaveis.x),
        "y": len(variaveis.y),
        "b": len(variaveis.b),
        "s": len(variaveis.s),
        "u": len(variaveis.u),
        "w": len(variaveis.w),
        "folga_falta": len(variaveis.folga_falta),
        "folga_sobra": len(variaveis.folga_sobra),
        "desvio_acima": len(variaveis.desvio_acima),
        "desvio_abaixo": len(variaveis.desvio_abaixo),
    }
