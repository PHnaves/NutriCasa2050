"""Resolve o modelo e traduz a resposta do PuLP para o resto do projeto.

Separar "montar as regras" (modelo.py) de "resolver e entender a resposta"
(este arquivo) e o que permite o modo --smoke: um jeito de provar, dentro do
container do CI, que o solver esta mesmo acessivel (card S1-13/S2-09).
"""
from __future__ import annotations

import argparse
import time

from pulp import PULP_CBC_CMD, LpProblem, LpStatus

from nutricasa2050 import config
from nutricasa2050.dominio import Catalogo, Ingrediente, Lote, Membro, Parametros, Receita, Solucao
from nutricasa2050.otimizacao.modelo import construir
from nutricasa2050.otimizacao.variaveis import Variaveis

_DESCRICOES_STATUS = {
    "Optimal": "cardapio encontrado dentro de todas as regras.",
    "Infeasible": "nao existe cardapio que atenda todas as regras com esses parametros.",
    "Unbounded": "o problema esta mal configurado: o objetivo pode cair sem limite.",
    "Not Solved": (
        "o solver bateu no tempo limite antes de achar um cardapio inteiro "
        "e viavel — nenhum resultado confiavel (aumente o tempo limite, "
        "reduza o horizonte ou afrouxe o orcamento; ver card S4-05)."
    ),
    "Undefined": "o solver nao conseguiu determinar um resultado.",
}


def descrever_status(status: str) -> str:
    return _DESCRICOES_STATUS.get(status, f"status desconhecido do solver: {status!r}.")


class ErroDeSolucao(RuntimeError):
    """O solver terminou sem uma solucao inteira e viavel utilizavel."""


TOLERANCIA_INTEIRA = 1e-4


def solucao_e_inteira(problema: LpProblem) -> bool:
    """True se toda variavel binaria/inteira do problema resolvido tem valor
    inteiro (dentro de uma tolerancia).

    Existe por causa de um erro do Sprint 4 (corrigido no 6): quando o CBC
    bate no tempo limite SEM ter achado nenhuma solucao inteira, o PuLP
    ainda devolve valores — mas sao os da RELAXACAO LINEAR (pratos "meio
    cozinhados", 0,3 embalagem comprada), que satisfazem R1 e as outras
    restricoes lineares e por isso parecem uma resposta valida. Checar so
    a soma das porcoes (o que eu fiz na epoca) nao pega isso; checar a
    integralidade pega.
    """
    for variavel in problema.variables():
        if variavel.cat not in ("Binary", "Integer"):
            continue
        valor = variavel.varValue
        if valor is None or abs(valor - round(valor)) > TOLERANCIA_INTEIRA:
            return False
    return True


def resolver_problema(problema: LpProblem, parametros: Parametros) -> str:
    """Resolve `problema` ja montado e devolve o status do PuLP. Levanta
    ErroDeSolucao se o solver terminou sem uma solucao inteira — nunca
    devolve em silencio os valores de uma relaxacao linear."""
    problema.solve(_escolher_solver(parametros))
    status = LpStatus[problema.status]
    if status in ("Optimal", "Not Solved") and not solucao_e_inteira(problema):
        raise ErroDeSolucao(descrever_status("Not Solved"))
    return status


def _escolher_solver(parametros: Parametros) -> PULP_CBC_CMD:
    tempo_limite = config.solver_tempo_limite()
    caminho = config.solver_caminho_binario()
    if caminho:
        return PULP_CBC_CMD(msg=False, timeLimit=tempo_limite, path=caminho)
    return PULP_CBC_CMD(msg=False, timeLimit=tempo_limite)


def _somente_positivos(variaveis: dict) -> dict:
    return {
        chave: variavel.varValue
        for chave, variavel in variaveis.items()
        if variavel.varValue is not None and variavel.varValue > 1e-9
    }


def _extrair_cardapio(variaveis: Variaveis) -> dict:
    return _somente_positivos(variaveis.x)


def _extrair_porcoes(variaveis: Variaveis) -> dict:
    return _somente_positivos(variaveis.y)


def _extrair_compras(variaveis: Variaveis) -> dict:
    return _somente_positivos(variaveis.b)


def _extrair_descartes(variaveis: Variaveis) -> dict:
    return _somente_positivos(variaveis.w)


def _extrair_estoque(variaveis: Variaveis) -> dict:
    return _somente_positivos(variaveis.s)


def _extrair_aderencia(variaveis: Variaveis) -> dict:
    return {
        "folga_falta": _somente_positivos(variaveis.folga_falta),
        "folga_sobra": _somente_positivos(variaveis.folga_sobra),
        "desvio_acima": _somente_positivos(variaveis.desvio_acima),
        "desvio_abaixo": _somente_positivos(variaveis.desvio_abaixo),
    }


_ADERENCIA_VAZIA = {
    "folga_falta": {},
    "folga_sobra": {},
    "desvio_acima": {},
    "desvio_abaixo": {},
}


def resolver(catalogo: Catalogo, parametros: Parametros) -> Solucao:
    problema, variaveis = construir(catalogo, parametros)
    solver = _escolher_solver(parametros)

    inicio = time.monotonic()
    problema.solve(solver)
    tempo_segundos = time.monotonic() - inicio

    status = LpStatus[problema.status]

    sem_solucao = status in ("Infeasible", "Unbounded", "Undefined") or (
        status in ("Optimal", "Not Solved") and not solucao_e_inteira(problema)
    )
    if sem_solucao:
        # Sem solucao utilizavel: nao ha cardapio, porcao, compra, descarte,
        # estoque ou aderencia para reportar. Tres casos: o solver concluiu
        # que a resposta nao existe (varValue e lixo de ramo abandonado), ou
        # bateu no tempo limite antes de achar qualquer solucao INTEIRA —
        # ai varValue e a relaxacao linear (ver solucao_e_inteira).
        return Solucao(
            status=status,
            tempo_segundos=tempo_segundos,
            valor_objetivo=None,
            cardapio={},
            porcoes={},
            compras={},
            descartes={},
            estoque={},
            aderencia=dict(_ADERENCIA_VAZIA),
        )

    # "Optimal" (provado) OU "Not Solved" COM solucao inteira (achou uma
    # resposta viavel mas nao deu tempo de provar que e a melhor — S4-05).
    valor_objetivo = problema.objective.value()
    if valor_objetivo is None and status == "Optimal":
        # Objetivo sem nenhuma variavel (ex.: nenhum dia de compra no
        # horizonte) — PuLP devolve None em vez da constante nesse caso.
        valor_objetivo = float(problema.objective.constant)

    return Solucao(
        status=status,
        tempo_segundos=tempo_segundos,
        valor_objetivo=valor_objetivo,
        cardapio=_extrair_cardapio(variaveis),
        porcoes=_extrair_porcoes(variaveis),
        compras=_extrair_compras(variaveis),
        descartes=_extrair_descartes(variaveis),
        estoque=_extrair_estoque(variaveis),
        aderencia=_extrair_aderencia(variaveis),
    )


def _catalogo_smoke() -> Catalogo:
    """Catalogo minusculo so para o --smoke: 2 receitas, 1 ingrediente com
    estoque de sobra (sem precisar comprar) e 1 membro sem faixas (R5 fica
    vazia). O unico objetivo e provar que o solver consegue rodar e devolver
    Optimal, nao testar a logica de nutricao/estoque."""
    ingredientes = {
        "1": Ingrediente(
            id="1",
            nome="Ingrediente smoke",
            unidade="kg",
            categoria="secos",
            validade_dias=30,
            preco_embalagem=5.0,
            tamanho_embalagem=1.0,
        )
    }
    receitas = {
        "r1": Receita(id="r1", nome="Receita 1", tempo_min=10, tags=frozenset(), preferencia=0.5),
        "r2": Receita(id="r2", nome="Receita 2", tempo_min=10, tags=frozenset(), preferencia=0.5),
    }
    matriz_a = {("r1", "1"): 0.1, ("r2", "1"): 0.1}
    lotes = {"L1": Lote(id="L1", ingrediente_id="1", quantidade=100.0, dia_vencimento=30)}
    membros = {
        "p1": Membro(
            id="p1", nome="Membro smoke", fator_porcao=1.0, tags_bloqueadas=frozenset(), faixas={}
        )
    }
    return Catalogo(
        ingredientes=ingredientes,
        receitas=receitas,
        matriz_a=matriz_a,
        nutrientes={},
        lotes=lotes,
        membros=membros,
    )


def _parametros_smoke() -> Parametros:
    return Parametros(horizonte=1, refeicoes_por_dia=1, orcamento=0.0, dias_compra=())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve o modelo de otimizacao do NutriCasa 2050")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="roda um modelo minusculo so para provar que o solver esta acessivel",
    )
    args = parser.parse_args(argv)

    if not args.smoke:
        parser.print_help()
        return 1

    solucao = resolver(_catalogo_smoke(), _parametros_smoke())
    print(f"status: {solucao.status} ({descrever_status(solucao.status)})")
    print(f"tempo: {solucao.tempo_segundos:.3f}s")
    return 0 if solucao.status == "Optimal" else 1


if __name__ == "__main__":
    raise SystemExit(main())
