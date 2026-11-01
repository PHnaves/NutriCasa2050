"""R10 (validade/FEFO) e o termo_desperdicio associado — card S3-01, "o
coracao do projeto": o que nao foi comido a tempo tem que sair pela
variavel de descarte, nunca sobrar num lote vencido nem ser consumido
depois de vencer.
"""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus

from nutricasa2050.dominio import Parametros, Pesos
from nutricasa2050.otimizacao.modelo import construir
from nutricasa2050.otimizacao.objetivo import termo_desperdicio
from nutricasa2050.otimizacao.restricoes import (
    criar_lotes_de_compra,
    r9_balanco_de_estoque,
    r10_validade_por_lote,
)
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def test_lote_vencido_nao_e_consumido() -> None:
    catalogo = construir_catalogo(
        ingredientes=[ingrediente("1", "Tomate")],
        lotes=[lote("L1", "1", quantidade=1.0, dia_vencimento=1)],
    )
    parametros = Parametros(horizonte=2, refeicoes_por_dia=1, dias_compra=())
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r10_consumo", LpMinimize)
    r9_balanco_de_estoque(problema, variaveis, catalogo, parametros)
    r10_validade_por_lote(problema, variaveis, catalogo, parametros)

    # Tenta consumir no dia 2, um dia depois do vencimento (dia 1).
    problema += variaveis.u[("L1", 2)] == 0.5

    assert _resolver(problema) == "Infeasible"


def test_sobra_de_lote_vencido_vira_descarte() -> None:
    catalogo = construir_catalogo(
        ingredientes=[ingrediente("1", "Tomate")],
        lotes=[lote("L1", "1", quantidade=2.0, dia_vencimento=1)],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, dias_compra=())
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r10_descarte", LpMinimize)
    r9_balanco_de_estoque(problema, variaveis, catalogo, parametros)
    r10_validade_por_lote(problema, variaveis, catalogo, parametros)

    dia = parametros.dias[0]
    problema += variaveis.u[("L1", dia)] == 0  # nada foi consumido

    assert _resolver(problema) == "Optimal"
    assert abs(variaveis.w[("L1", dia)].varValue - 2.0) < 1e-6
    assert abs(variaveis.s[("L1", dia)].varValue - 0.0) < 1e-6


def test_lote_de_compra_tem_vencimento_correto() -> None:
    """Comprar no dia 2 um item que dura 5 dias cria um lote vencendo no
    dia 7."""
    catalogo = construir_catalogo(ingredientes=[ingrediente("1", "Arroz", validade_dias=5)])
    parametros = Parametros(horizonte=7, refeicoes_por_dia=1, dias_compra=(2,))

    lotes_compra = criar_lotes_de_compra(catalogo, parametros)

    assert len(lotes_compra) == 1
    lote_compra = lotes_compra[0]
    assert lote_compra.ingrediente_id == "1"
    assert lote_compra.dia_compra == 2
    assert lote_compra.dia_vencimento == 7


def test_termo_desperdicio_usa_preco_unitario() -> None:
    catalogo = construir_catalogo(
        ingredientes=[
            ingrediente("1", "Arroz", preco_embalagem=6.0, tamanho_embalagem=2.0)  # unitario 3.0
        ],
        lotes=[lote("L1", "1", quantidade=5.0, dia_vencimento=5)],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, dias_compra=())
    variaveis = criar_variaveis(catalogo, parametros)

    variaveis.w[("L1", 1)].setInitialValue(2.0)
    variaveis.w[("L1", 1)].fixValue()

    problema = LpProblem("teste_termo_desperdicio", LpMinimize)
    problema += termo_desperdicio(variaveis, catalogo, parametros)
    problema.solve(PULP_CBC_CMD(msg=False))

    assert LpStatus[problema.status] == "Optimal"
    assert termo_desperdicio(variaveis, catalogo, parametros).value() == 2.0 * 3.0


def test_aumentar_peso_do_desperdicio_reduz_descarte() -> None:
    """r1 (preferido, nao usa o ingrediente que vence) compete com r2 (nao
    preferido, consome exatamente o lote que vence). Com peso baixo de
    desperdicio, a preferencia por r1 vale mais que o custo de jogar o
    lote fora; com peso alto, a conta se inverte e o descarte zera.
    """

    def _descarte(peso_desperdicio: float) -> float:
        pesos = Pesos(
            desperdicio=peso_desperdicio, preparo=0.0, desvio=0.0, folga=0.0, preferencia=10.0
        )
        catalogo = construir_catalogo(
            ingredientes=[
                ingrediente("1", "Tomate", preco_embalagem=1.0, tamanho_embalagem=1.0)
            ],
            receitas=[receita("r1", preferencia=1.0), receita("r2", preferencia=0.0)],
            matriz_a={("r2", "1"): 2.0},
            lotes=[lote("L1", "1", quantidade=2.0, dia_vencimento=1)],
            membros=[membro("p1", fator_porcao=1.0)],
        )
        parametros = Parametros(
            horizonte=1,
            refeicoes_por_dia=1,
            pratos_por_refeicao=1,  # so um dos dois pode ser cozinhado — escolha genuina
            orcamento=0.0,
            dias_compra=(),
            pesos=pesos,
        )
        problema, variaveis = construir(catalogo, parametros)
        assert _resolver(problema) == "Optimal"
        return variaveis.w[("L1", 1)].varValue

    descarte_peso_baixo = _descarte(1.0)
    descarte_peso_alto = _descarte(10.0)

    assert descarte_peso_baixo > descarte_peso_alto
    assert descarte_peso_alto < 1e-6
