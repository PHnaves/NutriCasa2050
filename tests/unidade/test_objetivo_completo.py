"""Os seis termos da funcao objetivo juntos (card S3-07) — todos em reais
antes de somar, senao os pesos nao significam nada comparavel entre si.
"""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita
from pulp import PULP_CBC_CMD, LpStatus

from nutricasa2050.dominio import Parametros, Pesos
from nutricasa2050.otimizacao.modelo import construir
from nutricasa2050.otimizacao.objetivo import descrever_objetivo
from nutricasa2050.otimizacao.solver import resolver


def _resolver(problema) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def test_aumentar_peso_do_desperdicio_reduz_desperdicio_e_aumenta_custo() -> None:
    """r1 e de graca mas deixa o tomate (que vence hoje) apodrecer; r2
    evita o desperdicio, mas precisa comprar queijo (R$ 10) pra servir.
    Com peso baixo de desperdicio, o tomate perdido (R$ 2) sai mais
    barato que comprar; com peso alto, a conta se inverte."""

    def _resolver_e_medir(peso_desperdicio: float) -> tuple[float, float]:
        pesos = Pesos(
            custo=1.0,
            desperdicio=peso_desperdicio,
            preparo=0.0,
            desvio=0.0,
            folga=0.0,
            preferencia=0.0,
        )
        catalogo = construir_catalogo(
            ingredientes=[
                ingrediente("1", "Tomate", preco_embalagem=1.0, tamanho_embalagem=1.0),
                ingrediente("2", "Queijo", preco_embalagem=10.0, tamanho_embalagem=1.0),
            ],
            receitas=[receita("r1"), receita("r2")],
            matriz_a={("r2", "1"): 2.0, ("r2", "2"): 1.0},
            lotes=[lote("L1", "1", quantidade=2.0, dia_vencimento=1)],
            membros=[membro("p1", fator_porcao=1.0)],
        )
        parametros = Parametros(
            horizonte=1,
            refeicoes_por_dia=1,
            pratos_por_refeicao=1,
            orcamento=1000.0,
            dias_compra=(1,),
            pesos=pesos,
        )
        problema, variaveis = construir(catalogo, parametros)
        assert _resolver(problema) == "Optimal"
        desperdicio = variaveis.w[("L1", 1)].varValue
        custo = sum(
            catalogo.ingredientes[i].preco_embalagem * variaveis.b[(i, 1)].varValue
            for i in catalogo.ingredientes
        )
        return desperdicio, custo

    desperdicio_peso_baixo, custo_peso_baixo = _resolver_e_medir(1.0)
    desperdicio_peso_alto, custo_peso_alto = _resolver_e_medir(10.0)

    assert desperdicio_peso_baixo > desperdicio_peso_alto
    assert custo_peso_alto > custo_peso_baixo


def test_preferencia_entra_com_sinal_negativo() -> None:
    """r2 custa R$ 5 a mais que r1, mas e mais preferida. Subir o peso da
    preferencia faz o solver aceitar pagar esse custo extra — so faz
    sentido se preferencia entrar com sinal NEGATIVO no objetivo (que e
    minimizado)."""

    def _escolhe_r2(peso_preferencia: float) -> bool:
        pesos = Pesos(
            custo=1.0, desperdicio=0.0, preparo=0.0, desvio=0.0, folga=0.0,
            preferencia=peso_preferencia,
        )
        catalogo = construir_catalogo(
            ingredientes=[
                ingrediente("1", "Especial", preco_embalagem=5.0, tamanho_embalagem=1.0)
            ],
            receitas=[receita("r1", preferencia=0.0), receita("r2", preferencia=1.0)],
            matriz_a={("r2", "1"): 1.0},
            membros=[membro("p1", fator_porcao=1.0)],
        )
        parametros = Parametros(
            horizonte=1,
            refeicoes_por_dia=1,
            pratos_por_refeicao=1,
            orcamento=1000.0,
            dias_compra=(1,),
            pesos=pesos,
        )
        problema, variaveis = construir(catalogo, parametros)
        assert _resolver(problema) == "Optimal"
        dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
        return variaveis.x[("r2", dia, refeicao)].varValue > 0.5

    assert _escolhe_r2(peso_preferencia=1.0) is False
    assert _escolhe_r2(peso_preferencia=10.0) is True


def test_todos_os_termos_tem_magnitude_de_reais() -> None:
    """100 minutos de preparo tem que virar R$ 10 (custo_por_minuto=0,10),
    nao continuar "100"; 0,5 ponto de preferencia tem que virar R$ 1,00
    (valor_por_ponto=2,0), nao continuar "0,5". Nenhum termo com a ordem
    de grandeza da unidade original.
    """
    catalogo = construir_catalogo(
        receitas=[receita("r1", tempo_min=100, preferencia=0.5)],
        membros=[membro("p1")],
    )
    parametros = Parametros(
        horizonte=1,
        refeicoes_por_dia=1,
        pesos=Pesos(custo_por_minuto=0.10, valor_por_ponto_preferencia=2.0),
    )

    solucao = resolver(catalogo, parametros)
    assert solucao.status == "Optimal"

    termos = descrever_objetivo(solucao, catalogo, parametros)

    assert abs(termos["preparo"] - 100 * 0.10) < 1e-6
    assert abs(termos["preferencia"] - (-1.0 * 0.5 * 2.0)) < 1e-6


def test_descrever_objetivo_soma_o_valor_total() -> None:
    # Duas receitas (nao uma) porque R4 (variedade) proibe a mesma receita
    # em dois dias consecutivos — com horizonte=2 e so uma opcao, R1
    # forcaria repetir no dia seguinte e o modelo ficaria Infeasible.
    catalogo = construir_catalogo(
        ingredientes=[ingrediente("1", "Arroz", preco_embalagem=5.0, tamanho_embalagem=1.0)],
        receitas=[
            receita("r1", tempo_min=20, preferencia=0.8),
            receita("r2", tempo_min=20, preferencia=0.8),
        ],
        matriz_a={("r1", "1"): 0.2, ("r2", "1"): 0.2},
        membros=[membro("p1", fator_porcao=1.0)],
    )
    parametros = Parametros(horizonte=2, refeicoes_por_dia=1, orcamento=100.0, dias_compra=(1,))

    solucao = resolver(catalogo, parametros)
    assert solucao.status == "Optimal"

    termos = descrever_objetivo(solucao, catalogo, parametros)

    assert abs(termos["total"] - solucao.valor_objetivo) < 1e-4
