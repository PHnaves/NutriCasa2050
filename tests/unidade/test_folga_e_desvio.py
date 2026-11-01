"""R5 com folga e R7 (desvio do alvo) — card S3-06. A folga existe para o
modelo NUNCA recusar por nutricao (entrega a melhor resposta possivel e
mostra onde precisou ceder); R7 mede a distancia do alvo prescrito via a
linearizacao padrao do modulo (duas variaveis nao-negativas, so uma fica
positiva de cada vez quando o objetivo minimiza a soma das duas).
"""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, membro, receita
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus

from nutricasa2050.dominio import Faixa, Parametros, Pesos
from nutricasa2050.otimizacao.modelo import construir
from nutricasa2050.otimizacao.objetivo import termo_desvio, termo_folga
from nutricasa2050.otimizacao.restricoes import (
    r1_cobertura,
    r2_vinculo,
    r5_faixas_nutricionais,
    r7_desvio_do_alvo,
)
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def _resolver(problema: LpProblem) -> str:
    problema.solve(PULP_CBC_CMD(msg=False))
    return LpStatus[problema.status]


def _catalogo_kcal_fixo(kcal_receita: float, minimo: float, maximo: float, alvo: float):
    return construir_catalogo(
        receitas=[receita("r1")],
        nutrientes={("r1", "kcal"): kcal_receita},
        membros=[
            membro(
                "p1",
                fator_porcao=1.0,
                faixas={"kcal": Faixa(minimo=minimo, maximo=maximo, alvo=alvo)},
            )
        ],
    )


def test_desvio_e_zero_quando_atinge_o_alvo() -> None:
    catalogo = _catalogo_kcal_fixo(kcal_receita=500, minimo=0, maximo=10_000, alvo=500)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r7_zero", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r7_desvio_do_alvo(problema, variaveis, catalogo, parametros)
    problema += termo_desvio(variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia = parametros.dias[0]
    chave = ("kcal", "p1", dia)
    assert abs(variaveis.desvio_acima[chave].varValue) < 1e-6
    assert abs(variaveis.desvio_abaixo[chave].varValue) < 1e-6


def test_apenas_um_lado_do_desvio_fica_positivo() -> None:
    catalogo = _catalogo_kcal_fixo(kcal_receita=800, minimo=0, maximo=10_000, alvo=500)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_r7_um_lado", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r7_desvio_do_alvo(problema, variaveis, catalogo, parametros)
    problema += termo_desvio(variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia = parametros.dias[0]
    chave = ("kcal", "p1", dia)
    assert abs(variaveis.desvio_acima[chave].varValue - 300) < 1e-6
    assert abs(variaveis.desvio_abaixo[chave].varValue) < 1e-6


def test_folga_evita_infeasible() -> None:
    """So existe uma receita de 500 kcal, e a faixa exige 5000-6000 — sem
    folga, Infeasible; com folga, Optimal."""
    catalogo = _catalogo_kcal_fixo(kcal_receita=500, minimo=5000, maximo=6000, alvo=5500)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_folga_evita_infeasible", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r5_faixas_nutricionais(problema, variaveis, catalogo, parametros)
    problema += termo_folga(variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia = parametros.dias[0]
    assert variaveis.folga_falta[("kcal", "p1", dia)].varValue >= 4500 - 1e-6


def test_folga_aponta_o_nutriente_certo() -> None:
    """Apertando so o sodio (receita tem 5000 mg, maximo e 1000), a folga
    aparece no sodio — o kcal, com faixa folgada, fica com folga zero."""
    catalogo = construir_catalogo(
        receitas=[receita("r1")],
        nutrientes={("r1", "kcal"): 500.0, ("r1", "sodio_mg"): 5000.0},
        membros=[
            membro(
                "p1",
                fator_porcao=1.0,
                faixas={
                    "kcal": Faixa(minimo=400, maximo=600, alvo=500),
                    "sodio_mg": Faixa(minimo=0, maximo=1000, alvo=500),
                },
            )
        ],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_folga_certa", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r5_faixas_nutricionais(problema, variaveis, catalogo, parametros)
    problema += termo_folga(variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia = parametros.dias[0]
    assert variaveis.folga_sobra[("sodio_mg", "p1", dia)].varValue >= 4000 - 1e-6
    assert variaveis.folga_falta[("sodio_mg", "p1", dia)].varValue < 1e-6
    assert variaveis.folga_falta[("kcal", "p1", dia)].varValue < 1e-6
    assert variaveis.folga_sobra[("kcal", "p1", dia)].varValue < 1e-6


def test_folga_e_zero_quando_a_prescricao_e_folgada() -> None:
    catalogo = _catalogo_kcal_fixo(kcal_receita=500, minimo=400, maximo=600, alvo=500)
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1)
    variaveis = criar_variaveis(catalogo, parametros)

    problema = LpProblem("teste_folga_zero", LpMinimize)
    r1_cobertura(problema, variaveis, catalogo, parametros)
    r2_vinculo(problema, variaveis, catalogo, parametros)
    r5_faixas_nutricionais(problema, variaveis, catalogo, parametros)
    problema += termo_folga(variaveis, catalogo, parametros)

    assert _resolver(problema) == "Optimal"

    dia = parametros.dias[0]
    assert variaveis.folga_falta[("kcal", "p1", dia)].varValue < 1e-6
    assert variaveis.folga_sobra[("kcal", "p1", dia)].varValue < 1e-6


def test_peso_alto_da_folga_desencoraja_o_uso() -> None:
    """r1 (de graca, so entrega 100 kcal) compete com r2 (precisa comprar
    um suplemento de R$ 50 para entregar os 400 kcal exigidos sem
    folga). Com peso baixo de folga, aceitar a folga de r1 e mais barato
    que comprar; com peso alto, a conta se inverte."""

    def _folga_falta(peso_folga: float) -> float:
        pesos = Pesos(
            custo=1.0, desperdicio=0.0, preparo=0.0, desvio=0.0, folga=peso_folga, preferencia=0.0
        )
        catalogo = construir_catalogo(
            ingredientes=[
                ingrediente("1", "Suplemento", preco_embalagem=50.0, tamanho_embalagem=1.0)
            ],
            receitas=[receita("r1"), receita("r2")],
            matriz_a={("r2", "1"): 1.0},
            nutrientes={("r1", "kcal"): 100.0, ("r2", "kcal"): 400.0},
            membros=[
                membro(
                    "p1",
                    fator_porcao=1.0,
                    faixas={"kcal": Faixa(minimo=400, maximo=1000, alvo=400)},
                )
            ],
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
        dia = parametros.dias[0]
        return variaveis.folga_falta[("kcal", "p1", dia)].varValue

    folga_peso_baixo = _folga_falta(0.1)
    folga_peso_alto = _folga_falta(1.0)

    assert folga_peso_baixo > folga_peso_alto
    assert folga_peso_alto < 1e-6
