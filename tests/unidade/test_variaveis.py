from __future__ import annotations

from nutricasa2050.dados.carga import carregar_catalogo
from nutricasa2050.dominio import Parametros
from nutricasa2050.otimizacao.variaveis import contar_variaveis, criar_variaveis


def test_quantidade_de_variaveis_x() -> None:
    catalogo = carregar_catalogo()
    parametros = Parametros(horizonte=7, refeicoes_por_dia=2)

    variaveis = criar_variaveis(catalogo, parametros)

    assert len(variaveis.x) == 24 * 7 * 2
    assert contar_variaveis(variaveis)["x"] == 24 * 7 * 2


def test_y_tem_quatro_componentes_na_chave() -> None:
    catalogo = carregar_catalogo()
    parametros = Parametros(horizonte=2, refeicoes_por_dia=2)

    variaveis = criar_variaveis(catalogo, parametros)

    chave = next(iter(variaveis.y))
    assert len(chave) == 4
    membro_id, receita_id, dia, refeicao = chave
    assert membro_id in catalogo.membros
    assert receita_id in catalogo.receitas
    assert dia in parametros.dias
    assert refeicao in parametros.refeicoes


def test_s_u_w_tem_indice_de_lote() -> None:
    catalogo = carregar_catalogo()
    parametros = Parametros(horizonte=2, refeicoes_por_dia=2)

    variaveis = criar_variaveis(catalogo, parametros)

    for dicionario in (variaveis.s, variaveis.u, variaveis.w):
        lote_id, dia = next(iter(dicionario))
        assert lote_id in catalogo.lotes
        assert dia in parametros.dias


def test_y_limitada_entre_zero_e_um() -> None:
    catalogo = carregar_catalogo()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=2)

    variaveis = criar_variaveis(catalogo, parametros)
    variavel = next(iter(variaveis.y.values()))

    assert variavel.lowBound == 0
    assert variavel.upBound == 1
    assert variavel.cat == "Continuous"


def test_b_e_inteira() -> None:
    catalogo = carregar_catalogo()
    parametros = Parametros(horizonte=1, refeicoes_por_dia=2)

    variaveis = criar_variaveis(catalogo, parametros)
    variavel = next(iter(variaveis.b.values()))

    assert variavel.cat == "Integer"
    assert variavel.lowBound == 0


def test_b_so_existe_nos_dias_de_compra() -> None:
    catalogo = carregar_catalogo()
    parametros = Parametros(horizonte=5, refeicoes_por_dia=2, dias_compra=(1,))

    variaveis = criar_variaveis(catalogo, parametros)

    dias_usados = {dia for (_, dia) in variaveis.b}
    assert dias_usados == {1}
