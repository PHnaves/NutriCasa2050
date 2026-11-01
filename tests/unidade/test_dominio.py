from __future__ import annotations

from nutricasa2050.dominio import (
    Catalogo,
    Faixa,
    Ingrediente,
    Lote,
    Membro,
    Parametros,
    Receita,
)


def _ingrediente(id_="1", nome="Arroz") -> Ingrediente:
    return Ingrediente(
        id=id_,
        nome=nome,
        unidade="kg",
        categoria="secos",
        validade_dias=180,
        preco_embalagem=6.0,
        tamanho_embalagem=2.0,
    )


def _receita(id_="r1", tags: frozenset[str] = frozenset()) -> Receita:
    return Receita(id=id_, nome="Receita", tempo_min=10, tags=tags, preferencia=0.5)


def _membro(tags_bloqueadas: frozenset[str] = frozenset()) -> Membro:
    return Membro(
        id="p1",
        nome="Pessoa",
        fator_porcao=1.0,
        tags_bloqueadas=tags_bloqueadas,
        faixas={"kcal": Faixa(minimo=1000, maximo=2000, alvo=1500)},
    )


def test_preco_unitario_calculado() -> None:
    ingrediente = _ingrediente()
    assert ingrediente.preco_unitario == 3.0


def test_membro_nao_pode_comer_receita_bloqueada() -> None:
    membro = _membro(tags_bloqueadas=frozenset({"alto_sodio"}))
    receita_bloqueada = _receita(tags=frozenset({"alto_sodio"}))
    receita_livre = _receita(id_="r2", tags=frozenset({"vegetariano"}))

    assert membro.pode_comer(receita_bloqueada) is False
    assert membro.pode_comer(receita_livre) is True


def test_quantidade_devolve_zero_para_par_inexistente() -> None:
    catalogo = Catalogo(
        ingredientes={"1": _ingrediente()},
        receitas={"r1": _receita()},
        matriz_a={("r1", "1"): 0.1},
        nutrientes={},
        lotes={},
        membros={},
    )

    assert catalogo.quantidade("r1", "1") == 0.1
    assert catalogo.quantidade("r1", "999") == 0.0
    assert catalogo.quantidade("inexistente", "1") == 0.0


def test_ingredientes_orfaos_detecta_uso_unico() -> None:
    catalogo = Catalogo(
        ingredientes={"1": _ingrediente("1"), "2": _ingrediente("2", "Feijao")},
        receitas={"r1": _receita("r1"), "r2": _receita("r2")},
        matriz_a={
            ("r1", "1"): 0.1,
            ("r2", "1"): 0.1,
            ("r1", "2"): 0.1,
        },
        nutrientes={},
        lotes={},
        membros={},
    )

    assert catalogo.ingredientes_orfaos() == ["2"]
    assert catalogo.receitas_com_ingrediente("1") == ["r1", "r2"]
    assert catalogo.ingredientes_da_receita("r1") == ["1", "2"]


def test_lotes_do_ingrediente() -> None:
    lote_a = Lote(id="L1", ingrediente_id="1", quantidade=2.0, dia_vencimento=5)
    lote_b = Lote(id="L2", ingrediente_id="2", quantidade=1.0, dia_vencimento=10)
    catalogo = Catalogo(
        ingredientes={},
        receitas={},
        matriz_a={},
        nutrientes={},
        lotes={"L1": lote_a, "L2": lote_b},
        membros={},
    )

    assert catalogo.lotes_do_ingrediente("1") == [lote_a]


def test_receitas_permitidas_filtra_pelas_tags_bloqueadas() -> None:
    membro = _membro(tags_bloqueadas=frozenset({"alto_sodio"}))
    catalogo = Catalogo(
        ingredientes={},
        receitas={
            "r1": _receita("r1", tags=frozenset({"alto_sodio"})),
            "r2": _receita("r2", tags=frozenset({"vegetariano"})),
        },
        matriz_a={},
        nutrientes={},
        lotes={},
        membros={},
    )

    assert catalogo.receitas_permitidas(membro) == ["r2"]


def test_parametros_dias_e_refeicoes_derivados() -> None:
    parametros = Parametros(horizonte=3, refeicoes_por_dia=2)

    assert parametros.dias == (1, 2, 3)
    assert parametros.refeicoes == ("almoco", "jantar")


def test_parametros_refeicoes_sem_nome_padrao_usa_generico() -> None:
    parametros = Parametros(horizonte=1, refeicoes_por_dia=4)

    assert parametros.refeicoes == ("refeicao_1", "refeicao_2", "refeicao_3", "refeicao_4")
