"""Os graficos do "nao existe almoco gratis" (card S5-02). Nao se testa
a aparencia — testa-se a contagem de pontos, o arquivo criado, e a
relacao matematica esperada.
"""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita

from nutricasa2050.analise.graficos import (
    grafico_desperdicio_por_cenario,
    grafico_pareto_custo_aderencia,
    grafico_pareto_custo_desperdicio,
    varrer_peso,
)
from nutricasa2050.dominio import Parametros, Pesos
from nutricasa2050.persistencia.banco import criar_schema
from nutricasa2050.persistencia.repositorio import gravar_cenario, gravar_execucao


def _catalogo_com_tradeoff():
    """r1 (preferida) nao usa o ingrediente que vence; r2 (nao preferida)
    usa exatamente o lote que vence — o mesmo desenho de S3-01, aqui
    reaproveitado para variar o peso do desperdicio de verdade."""
    return construir_catalogo(
        ingredientes=[
            ingrediente("1", "Tomate", preco_embalagem=1.0, tamanho_embalagem=1.0)
        ],
        receitas=[receita("r1", preferencia=1.0), receita("r2", preferencia=0.0)],
        matriz_a={("r2", "1"): 2.0},
        lotes=[lote("L1", "1", quantidade=2.0, dia_vencimento=1)],
        membros=[membro("p1", fator_porcao=1.0)],
    )


def _parametros_com_peso(peso_desperdicio: float) -> Parametros:
    pesos = Pesos(
        desperdicio=peso_desperdicio, preparo=0.0, desvio=0.0, folga=0.0, preferencia=10.0
    )
    return Parametros(
        horizonte=1,
        refeicoes_por_dia=1,
        pratos_por_refeicao=1,
        orcamento=0.0,
        dias_compra=(),
        pesos=pesos,
    )


def test_varrer_peso_devolve_um_ponto_por_valor() -> None:
    catalogo = _catalogo_com_tradeoff()
    parametros = _parametros_com_peso(1.0)
    valores = [1.0, 2.0, 5.0, 10.0]

    pontos = varrer_peso(catalogo, parametros, "desperdicio", valores)

    assert len(pontos) == len(valores)
    assert all(p["status"] == "Optimal" for p in pontos)


def test_pareto_e_monotonico() -> None:
    """Aumentar o peso do desperdicio NUNCA aumenta o desperdicio. Se
    aumentar, tem erro de sinal em algum termo do objetivo."""
    catalogo = _catalogo_com_tradeoff()
    parametros = _parametros_com_peso(1.0)
    valores = [1.0, 2.0, 4.0, 6.0, 8.0, 10.0]

    pontos = varrer_peso(catalogo, parametros, "desperdicio", valores)
    desperdicios = [p["desperdicio"] for p in pontos]

    for atual, seguinte in zip(desperdicios, desperdicios[1:], strict=False):
        assert seguinte <= atual + 1e-9


def test_grafico_cria_o_arquivo(tmp_path) -> None:
    catalogo = _catalogo_com_tradeoff()
    parametros = _parametros_com_peso(1.0)
    pontos = varrer_peso(catalogo, parametros, "desperdicio", [1.0, 5.0, 10.0])

    caminho = tmp_path / "pareto.png"
    grafico_pareto_custo_desperdicio(pontos, caminho)

    assert caminho.exists()
    assert caminho.stat().st_size > 0


def test_grafico_custo_aderencia_cria_o_arquivo(tmp_path) -> None:
    catalogo = _catalogo_com_tradeoff()
    parametros = _parametros_com_peso(1.0)
    pontos = varrer_peso(catalogo, parametros, "desvio", [1.0, 5.0])

    caminho = tmp_path / "pareto_aderencia.png"
    grafico_pareto_custo_aderencia(pontos, caminho)

    assert caminho.exists()
    assert caminho.stat().st_size > 0


def test_grafico_desperdicio_por_cenario_cria_o_arquivo(tmp_path, engine_memoria) -> None:
    criar_schema(engine_memoria)
    resumo_vazio = {
        "resumo": {
            "status": "Optimal",
            "tempo_segundos": 0.1,
            "custo_total": 10.0,
            "valor_desperdicio": 2.0,
            "tempo_cozinha_minutos": 20,
        },
        "cardapio": [],
        "porcoes": [],
        "compras": [],
        "descartes": [],
        "aderencia": [],
    }
    for indice, estrategia in enumerate(("otimizado", "humano", "guloso")):
        cenario_id = gravar_cenario(engine_memoria, {"rodada": 0, "semente": indice})
        gravar_execucao(engine_memoria, resumo_vazio, estrategia, {}, cenario_id=cenario_id)

    caminho = tmp_path / "boxplot.png"
    grafico_desperdicio_por_cenario(engine_memoria, caminho)

    assert caminho.exists()
    assert caminho.stat().st_size > 0
