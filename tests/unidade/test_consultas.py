"""Os quatro numeros da apresentacao (card S4-06, MARCO do Sprint 4)."""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, membro, receita

from nutricasa2050.analise.consultas import (
    economia_mensal,
    folgas_mais_frequentes,
    preco_da_prescricao,
    reducao_de_desperdicio,
)
from nutricasa2050.dominio import Faixa, Parametros
from nutricasa2050.persistencia.banco import criar_schema
from nutricasa2050.persistencia.repositorio import gravar_aderencia, gravar_execucao


def _execucao_minima(custo: float, descarte: float) -> dict:
    return {
        "resumo": {
            "status": "Optimal",
            "tempo_segundos": 0.1,
            "custo_total": custo,
            "valor_desperdicio": descarte,
            "tempo_cozinha_minutos": 30,
        },
        "cardapio": [],
        "porcoes": [],
        "compras": [],
        "descartes": [],
        "aderencia": [],
    }


def test_reducao_calculada_corretamente(engine_memoria) -> None:
    criar_schema(engine_memoria)

    cenario_1 = {"rodada": 0, "semente": 1}
    cenario_2 = {"rodada": 0, "semente": 2}
    from nutricasa2050.persistencia.repositorio import gravar_cenario

    id_1 = gravar_cenario(engine_memoria, cenario_1)
    id_2 = gravar_cenario(engine_memoria, cenario_2)

    gravar_execucao(engine_memoria, _execucao_minima(100.0, 20.0), "humano", {}, cenario_id=id_1)
    gravar_execucao(
        engine_memoria, _execucao_minima(100.0, 10.0), "otimizado", {}, cenario_id=id_1
    )
    gravar_execucao(engine_memoria, _execucao_minima(100.0, 30.0), "humano", {}, cenario_id=id_2)
    gravar_execucao(
        engine_memoria, _execucao_minima(100.0, 15.0), "otimizado", {}, cenario_id=id_2
    )

    # media humano = 25, media otimizado = 12.5 -> reducao = 50%
    reducao = reducao_de_desperdicio(engine_memoria)

    assert abs(reducao - 50.0) < 1e-6


def test_economia_mensal_devolve_intervalo(engine_memoria) -> None:
    criar_schema(engine_memoria)
    from nutricasa2050.persistencia.repositorio import gravar_cenario

    valores_humano = [120.0, 140.0, 100.0, 160.0]
    valores_otimizado = [80.0, 90.0, 85.0, 95.0]

    pares = zip(valores_humano, valores_otimizado, strict=True)
    for indice, (humano, otimizado) in enumerate(pares):
        cenario_id = gravar_cenario(engine_memoria, {"rodada": 0, "semente": indice})
        gravar_execucao(
            engine_memoria, _execucao_minima(humano, 0.0), "humano", {}, cenario_id=cenario_id
        )
        gravar_execucao(
            engine_memoria, _execucao_minima(otimizado, 0.0), "otimizado", {}, cenario_id=cenario_id
        )

    media, inferior, superior = economia_mensal(engine_memoria)

    assert inferior < media < superior


def test_folgas_ordenadas_por_frequencia(engine_memoria) -> None:
    criar_schema(engine_memoria)
    from nutricasa2050.persistencia.repositorio import gravar_cenario

    def _linha_aderencia(membro_id: str, nutriente: str, folga: float) -> dict:
        return {
            "membro_id": membro_id,
            "dia": 1,
            "nutriente": nutriente,
            "valor": 100.0,
            "minimo": 100.0,
            "maximo": 200.0,
            "alvo": 150.0,
            "desvio": 0.0,
            "folga": folga,
        }

    for indice in range(3):
        cenario_id = gravar_cenario(engine_memoria, {"rodada": 0, "semente": indice})
        execucao_id = gravar_execucao(
            engine_memoria, _execucao_minima(0.0, 0.0), "otimizado", {}, cenario_id=cenario_id
        )
        # sodio_mg folga em TODOS os cenarios; fibra_g so no primeiro.
        linhas = [_linha_aderencia("idoso", "sodio_mg", 10.0)]
        if indice == 0:
            linhas.append(_linha_aderencia("idoso", "fibra_g", 5.0))
        gravar_aderencia(engine_memoria, execucao_id, linhas)

    resultado = folgas_mais_frequentes(engine_memoria)

    assert resultado[0]["nutriente"] == "sodio_mg"
    assert resultado[0]["vezes_com_folga"] == 3
    assert any(linha["nutriente"] == "fibra_g" for linha in resultado)


def test_preco_da_prescricao_e_positivo() -> None:
    """Seguir a dieta restritiva nunca pode sair mais barato que nao
    seguir nenhuma — senao a prescricao nao esta restringindo nada."""
    catalogo = construir_catalogo(
        ingredientes=[
            ingrediente("1", "Peito de frango", preco_embalagem=20.0, tamanho_embalagem=1.0)
        ],
        receitas=[
            receita("r1", tempo_min=10, preferencia=1.0),
            receita("r2", tempo_min=40, preferencia=0.1),
        ],
        matriz_a={("r2", "1"): 1.0},
        nutrientes={("r1", "kcal"): 100.0, ("r2", "kcal"): 600.0},
        membros=[
            membro(
                "p1",
                fator_porcao=1.0,
                faixas={"kcal": Faixa(minimo=500, maximo=700, alvo=600)},
            )
        ],
    )
    parametros = Parametros(
        horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=1, orcamento=1000.0, dias_compra=(1,)
    )

    resultado = preco_da_prescricao(catalogo, parametros)

    assert resultado["reais_por_semana"] >= 0
    assert resultado["minutos_de_cozinha"] >= 0
