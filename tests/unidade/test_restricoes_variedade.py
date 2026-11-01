"""R4 (regra da variedade, card S3-04): sem ela, o solver serve a receita
mais barata os sete dias da semana — matematicamente otimo, mas ninguem
aguenta. Bom senso humano traduzido em restricao.
"""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, membro, receita
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus, lpSum

from nutricasa2050.dominio import Parametros
from nutricasa2050.otimizacao.restricoes import r1_cobertura, r2_vinculo, r4_variedade
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def _preferencia_total(variaveis, catalogo, parametros):
    return lpSum(
        catalogo.receitas[receita_id].preferencia * variaveis.x[(receita_id, dia, refeicao)]
        for receita_id in catalogo.receitas
        for dia in parametros.dias
        for refeicao in parametros.refeicoes
    )


def _catalogo_barato_e_caro():
    """r1 e a preferida; r2/r3/r4 sao alternativas sem preferencia nenhuma.
    4 receitas para um horizonte de 7 dias/1 refeicao: com o teto de 2
    aparicoes cada (R4a), cabem no maximo 8 usos — o suficiente para
    cobrir os 7 dias necessarios (card: "conferir a viabilidade antes").
    """
    return construir_catalogo(
        ingredientes=[ingrediente("1", "Arroz", preco_embalagem=1.0, tamanho_embalagem=1.0)],
        receitas=[
            receita("r1", preferencia=1.0),
            receita("r2", preferencia=0.0),
            receita("r3", preferencia=0.0),
            receita("r4", preferencia=0.0),
        ],
        matriz_a={
            ("r1", "1"): 0.01,
            ("r2", "1"): 0.01,
            ("r3", "1"): 0.01,
            ("r4", "1"): 0.01,
        },
        membros=[membro("p1", fator_porcao=1.0)],
    )


def test_receita_nao_aparece_mais_de_duas_vezes() -> None:
    catalogo = _catalogo_barato_e_caro()
    parametros = Parametros(horizonte=7, refeicoes_por_dia=1, dias_compra=())
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r4_max_duas", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r4_variedade(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    for receita_id in catalogo.receitas:
        total = sum(
            variaveis.x[(receita_id, dia, parametros.refeicoes[0])].varValue
            for dia in parametros.dias
        )
        assert total <= 2 + 1e-6


def test_receita_nao_aparece_em_dias_consecutivos() -> None:
    catalogo = _catalogo_barato_e_caro()
    parametros = Parametros(horizonte=7, refeicoes_por_dia=1, dias_compra=())
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r4_consecutivo", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r4_variedade(problema, variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    refeicao = parametros.refeicoes[0]
    for receita_id in catalogo.receitas:
        for dia, dia_seguinte in zip(parametros.dias, parametros.dias[1:], strict=False):
            usado_hoje = variaveis.x[(receita_id, dia, refeicao)].varValue
            usado_depois = variaveis.x[(receita_id, dia_seguinte, refeicao)].varValue
            assert usado_hoje + usado_depois <= 1 + 1e-6


def test_sem_r4_alguma_receita_repete_mais_de_duas_vezes() -> None:
    """Documenta por que R4 existe: sem ela, nada impede o solver de
    escolher a receita preferida (e mais barata) todos os 7 dias."""
    catalogo = _catalogo_barato_e_caro()
    parametros = Parametros(horizonte=7, refeicoes_por_dia=1, dias_compra=())
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_sem_r4", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    # Preferencia precisa estar no objetivo para a repeticao ser a escolha
    # otima — sem custo nenhum diferenciando as receitas, o CBC poderia
    # escolher qualquer uma por tie-break.
    problema += -_preferencia_total(variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    repeticoes_r1 = sum(
        variaveis.x[("r1", dia, parametros.refeicoes[0])].varValue for dia in parametros.dias
    )
    assert repeticoes_r1 > 2


def test_com_r4_o_custo_sobe() -> None:
    """Mede o PRECO DA VARIEDADE: forcar o solver a nao repetir a receita
    preferida custa preferencia perdida (aqui, o unico termo relevante)."""

    def _resolver_e_medir(com_r4: bool) -> float:
        catalogo = _catalogo_barato_e_caro()
        parametros = Parametros(horizonte=7, refeicoes_por_dia=1, dias_compra=())
        variaveis = criar_variaveis(catalogo, parametros)

        problema = LpProblem("teste_preco_variedade", LpMinimize)
        r1_cobertura(problema, variaveis, catalogo, parametros)
        r2_vinculo(problema, variaveis, catalogo, parametros)
        if com_r4:
            r4_variedade(problema, variaveis, catalogo, parametros)
        problema += -_preferencia_total(variaveis, catalogo, parametros)

        assert _resolver(problema) == "Optimal"
        return _preferencia_total(variaveis, catalogo, parametros).value()

    preferencia_sem_r4 = _resolver_e_medir(com_r4=False)
    preferencia_com_r4 = _resolver_e_medir(com_r4=True)

    assert preferencia_com_r4 < preferencia_sem_r4
