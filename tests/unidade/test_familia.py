"""A casa deixa de ser um numero e vira quatro pessoas de verdade (card
S3-02) — cada uma com faixa nutricional e fator de porcao proprios, lidos
de data/perfis/familia_demo.json (nenhum codigo precisou trocar: a
arquitetura de S2-01/S2-03 ja era indexada por membro).
"""
from __future__ import annotations

import dataclasses

import pytest
from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus

from nutricasa2050.dados.carga import carregar_catalogo
from nutricasa2050.dominio import Faixa, Parametros
from nutricasa2050.otimizacao.restricoes import (
    r1_cobertura,
    r2_vinculo,
    r5_faixas_nutricionais,
    r8_consumo_derivado,
)
from nutricasa2050.otimizacao.solver import resolver
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def test_cada_membro_fecha_a_propria_faixa() -> None:
    """Isola a ligacao R5-por-membro (sem depender do catalogo real, cujas
    6 faixas simultaneas para 4 pessoas competindo por so 2 pratos por
    refeicao exigem folga — ver docs/resultados.md): cada um dos quatro
    tem uma faixa de kcal DIFERENTE, e cada um fecha a sua, nao uma
    faixa global."""
    catalogo = construir_catalogo(
        receitas=[receita("r1")],
        nutrientes={("r1", "kcal"): 1000.0},
        membros=[
            membro("adulto", fator_porcao=1.0, faixas={"kcal": Faixa(900, 1100, 1000)}),
            membro("crianca", fator_porcao=0.6, faixas={"kcal": Faixa(500, 700, 600)}),
            membro("idoso", fator_porcao=0.8, faixas={"kcal": Faixa(700, 900, 800)}),
        ],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_familia_faixas", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r5_faixas_nutricionais(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    for membro_id, membro_obj in catalogo.membros.items():
        fracao = variaveis.y[(membro_id, "r1", dia, refeicao)].varValue
        consumo = 1000.0 * membro_obj.fator_porcao * fracao
        faixa = membro_obj.faixas["kcal"]
        assert faixa.minimo - 1e-6 <= consumo <= faixa.maximo + 1e-6


def test_crianca_consome_sessenta_por_cento_do_adulto() -> None:
    """No MESMO prato, a crianca_8_anos (fator_porcao real 0.6) consome
    60% do que a adulto_ativo (fator_porcao 1.0) consome — ver card
    S3-02, item 3 ("conferir que R8 esta aplicando o fator de porcao
    DAQUELE membro")."""
    catalogo_real = carregar_catalogo()
    adulto = catalogo_real.membros["adulto_ativo"]
    crianca = catalogo_real.membros["crianca_8_anos"]
    assert crianca.fator_porcao == pytest.approx(0.6)

    catalogo = construir_catalogo(
        ingredientes=[ingrediente("1", "Arroz", tamanho_embalagem=1.0)],
        receitas=[receita("r1")],
        matriz_a={("r1", "1"): 1.0},
        lotes=[lote("L1", "1", quantidade=10.0, dia_vencimento=180)],
        membros=[
            membro("adulto", fator_porcao=adulto.fator_porcao),
            membro("crianca", fator_porcao=crianca.fator_porcao),
        ],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=1, dias_compra=())
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_fator_porcao_real", LpMinimize)
    r8_consumo_derivado(problema, variaveis, catalogo, parametros)

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]
    problema += variaveis.y[("adulto", "r1", dia, refeicao)] == 1
    problema += variaveis.y[("crianca", "r1", dia, refeicao)] == 1

    assert _resolver(problema) == "Optimal"

    dia = parametros.dias[0]
    consumo_total = sum(
        variaveis.u[(lote.id, dia)].varValue for lote in catalogo.lotes_do_ingrediente("1")
    )
    consumo_adulto = 1.0 * adulto.fator_porcao
    consumo_crianca = 1.0 * crianca.fator_porcao
    assert abs(consumo_total - (consumo_adulto + consumo_crianca)) < 1e-6
    assert abs(consumo_crianca - 0.6 * consumo_adulto) < 1e-6


@pytest.mark.lento
def test_familia_de_quatro_consome_mais_que_de_um() -> None:
    """Catalogo real, horizonte curto (1 dia) so para manter o teste
    rapido-o-suficiente-para-rodar-sempre: a familia de 4 compra mais
    comida que uma unica pessoa, nos mesmos parametros."""
    catalogo = carregar_catalogo()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=3, orcamento=500.0, dias_compra=(1,))

    def _total_comprado(membros: dict) -> float:
        catalogo_filtrado = dataclasses.replace(catalogo, membros=dict(membros))
        solucao = resolver(catalogo_filtrado, parametros)
        assert solucao.status == "Optimal"
        return sum(solucao.compras.values())

    total_um = _total_comprado({"adulto_ativo": catalogo.membros["adulto_ativo"]})
    total_quatro = _total_comprado(catalogo.membros)

    assert total_quatro > total_um


@pytest.mark.lento
def test_tempo_de_solucao_abaixo_de_trinta_segundos() -> None:
    """Media em ~37s quando este teste foi escrito no S3-02 (acima dos
    30s do card) — exatamente o sinal que o card previu para abrir o
    S4-05. Resolvido la: baixar o NUTRICASA2050_SOLVER_TIMEOUT padrao de
    30s para 10s (config.py) foi suficiente por si so para este cenario
    especifico (~15,3s, Optimal de verdade, nao so um incumbente) — a
    alavanca extra de reduzir o horizonte so foi necessaria para a
    Monte Carlo de 500 cenarios (ver docs/resultados.md, secao S4-05).

    Orcamento R$ 900 desde o Sprint 6: com os precos reais do Atacadao a
    semana custa R$ 440-550, e com R$ 500 o solver nao acha cardapio
    inteiro no tempo limite (medido; ver docs/resultados.md, topo)."""
    catalogo = carregar_catalogo()
    parametros = Parametros(horizonte=7, refeicoes_por_dia=3, orcamento=900.0, dias_compra=(1,))

    solucao = resolver(catalogo, parametros)

    assert solucao.status == "Optimal"
    assert solucao.tempo_segundos < 30
