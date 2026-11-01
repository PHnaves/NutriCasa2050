from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente
from pulp import PULP_CBC_CMD, LpMinimize, LpProblem, LpStatus

from nutricasa2050.dominio import Parametros
from nutricasa2050.otimizacao.objetivo import montar_objetivo, termo_custo
from nutricasa2050.otimizacao.variaveis import criar_variaveis


def test_termo_custo_bate_com_a_lista_de_compras() -> None:
    catalogo = construir_catalogo(
        ingredientes=[
            ingrediente("1", "Arroz", preco_embalagem=6.0, tamanho_embalagem=1.0),
            ingrediente("2", "Feijao", preco_embalagem=8.0, tamanho_embalagem=1.0),
        ],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, dias_compra=(1,))
    variaveis = criar_variaveis(catalogo, parametros)

    variaveis.b[("1", 1)].setInitialValue(3)
    variaveis.b[("1", 1)].fixValue()
    variaveis.b[("2", 1)].setInitialValue(2)
    variaveis.b[("2", 1)].fixValue()

    problema = LpProblem("teste_termo_custo", LpMinimize)
    problema += termo_custo(variaveis, catalogo, parametros)
    problema.solve(PULP_CBC_CMD(msg=False))

    assert LpStatus[problema.status] == "Optimal"
    assert termo_custo(variaveis, catalogo, parametros).value() == 3 * 6.0 + 2 * 8.0


def test_custo_nao_multiplica_pelo_tamanho_da_embalagem() -> None:
    """Trava o erro classico do card: comprar 1 pacote de arroz de 1 kg a
    R$ 6,00 custa R$ 6,00, nao R$ 6.000 (preco x tamanho)."""
    catalogo = construir_catalogo(
        ingredientes=[ingrediente("1", "Arroz", preco_embalagem=6.0, tamanho_embalagem=1.0)],
    )
    parametros = Parametros(horizonte=1, refeicoes_por_dia=1, dias_compra=(1,))
    variaveis = criar_variaveis(catalogo, parametros)
    variaveis.b[("1", 1)].setInitialValue(1)
    variaveis.b[("1", 1)].fixValue()

    problema = LpProblem("teste_custo_pacote", LpMinimize)
    montar_objetivo(problema, variaveis, catalogo, parametros)
    problema.solve(PULP_CBC_CMD(msg=False))

    assert problema.objective.value() == 6.0
