"""Gerador de cenarios (card S4-01) — tem que ser repetivel: mesma
semente, mesmo cenario, sempre."""
from __future__ import annotations

from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita

from nutricasa2050.dominio import Parametros
from nutricasa2050.simulacao.cenarios import (
    Cenario,
    aplicar_cenario,
    esquecer_itens,
    gerar_cenario,
    perturbar_precos,
)


def _catalogo_exemplo():
    return construir_catalogo(
        ingredientes=[
            ingrediente("1", "Arroz", preco_embalagem=6.0),
            ingrediente("2", "Feijao", preco_embalagem=8.0),
            ingrediente("3", "Tomate", preco_embalagem=4.0),
        ],
        receitas=[receita("r1"), receita("r2")],
        matriz_a={("r1", "1"): 0.2, ("r2", "2"): 0.2},
        lotes=[
            lote("L1", "1", quantidade=2.0, dia_vencimento=10),
            lote("L2", "2", quantidade=1.0, dia_vencimento=5),
        ],
        membros=[membro("p1")],
    )


def test_mesma_semente_gera_cenario_identico() -> None:
    assert gerar_cenario(42) == gerar_cenario(42)


def test_sementes_diferentes_geram_cenarios_diferentes() -> None:
    cenarios = [gerar_cenario(s) for s in range(20)]
    assert len({c for c in cenarios}) > 1


def test_perturbacao_de_preco_fica_dentro_de_quinze_por_cento() -> None:
    catalogo = _catalogo_exemplo()
    cenario = Cenario(semente=7, perturbacao_preco=0.15)

    perturbado = perturbar_precos(catalogo, cenario)

    for ingrediente_id, original in catalogo.ingredientes.items():
        novo_preco = perturbado.ingredientes[ingrediente_id].preco_embalagem
        minimo = original.preco_embalagem * 0.85
        maximo = original.preco_embalagem * 1.15
        assert minimo - 1e-9 <= novo_preco <= maximo + 1e-9


def test_aplicar_cenario_nao_altera_o_catalogo_original() -> None:
    catalogo = _catalogo_exemplo()
    precos_originais = {i: ing.preco_embalagem for i, ing in catalogo.ingredientes.items()}
    membros_originais = set(catalogo.membros)
    lotes_originais = {
        lote_id: lote_obj.dia_vencimento for lote_id, lote_obj in catalogo.lotes.items()
    }

    cenario = Cenario(
        semente=99,
        perturbacao_preco=0.15,
        membros_extras=1,
        refeicoes_puladas=1,
        itens_esquecidos=1,
        estragou_antes=1,
    )
    aplicar_cenario(catalogo, Parametros(horizonte=7, refeicoes_por_dia=3), cenario)

    assert {i: ing.preco_embalagem for i, ing in catalogo.ingredientes.items()} == precos_originais
    assert set(catalogo.membros) == membros_originais
    assert {
        lote_id: lote_obj.dia_vencimento for lote_id, lote_obj in catalogo.lotes.items()
    } == lotes_originais
    assert catalogo.itens_esquecidos == frozenset()
    assert catalogo.refeicoes_puladas == frozenset()


def test_esquecer_itens_marca_o_ingrediente_e_infla_o_preco() -> None:
    """Dois sinais tem que existir juntos: Catalogo.itens_esquecidos
    (o que os baselines olham, ja que nao decidem compra pelo preco) E
    o preco inflado (o que faz o solver nunca escolher comprar)."""
    catalogo = _catalogo_exemplo()
    cenario = Cenario(semente=3, itens_esquecidos=1)

    perturbado = esquecer_itens(catalogo, cenario)

    assert len(perturbado.itens_esquecidos) == 1
    (ingrediente_id,) = perturbado.itens_esquecidos
    preco_original = catalogo.ingredientes[ingrediente_id].preco_embalagem
    preco_novo = perturbado.ingredientes[ingrediente_id].preco_embalagem
    assert preco_novo == preco_original * 1000


def test_visita_aumenta_o_numero_de_membros() -> None:
    catalogo = _catalogo_exemplo()
    cenario = Cenario(semente=1, membros_extras=1)

    catalogo_perturbado, _ = aplicar_cenario(catalogo, Parametros(horizonte=1), cenario)

    assert len(catalogo_perturbado.membros) == len(catalogo.membros) + 1
