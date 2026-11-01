from __future__ import annotations

from pathlib import Path

import pytest

from nutricasa2050.dados.carga import (
    ErroDeCarga,
    carregar_catalogo,
    carregar_ingredientes,
    carregar_lotes,
    carregar_matriz_a,
    carregar_membros,
    carregar_nutrientes,
    carregar_receitas,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "carga"


def test_carregar_ingredientes_indexa_por_id() -> None:
    ingredientes = carregar_ingredientes(FIXTURES / "ingredientes.csv")

    assert set(ingredientes) == {"1", "2", "3"}
    assert ingredientes["1"].nome == "Arroz"
    assert ingredientes["1"].preco_unitario == 6.0


def test_tags_de_dieta_viram_conjunto() -> None:
    receitas = carregar_receitas(FIXTURES / "receitas.csv")

    assert receitas["r1"].tags == frozenset({"vegetariano", "sem_gluten"})
    assert receitas["r2"].tags == frozenset({"vegetariano"})


def test_matriz_a_indexada_por_tupla() -> None:
    matriz = carregar_matriz_a(FIXTURES / "matriz_a.csv")

    assert matriz[("r1", "1")] == 0.1
    assert matriz[("r1", "2")] == 2.0
    assert ("r2", "999") not in matriz


def test_carregar_nutrientes_indexado_por_tupla() -> None:
    nutrientes = carregar_nutrientes(FIXTURES / "nutrientes.csv")

    assert nutrientes[("r1", "kcal")] == 400.0
    assert nutrientes[("r2", "proteina_g")] == 10.0


def test_carregar_lotes() -> None:
    lotes = carregar_lotes(FIXTURES / "estoque_inicial.csv")

    assert len(lotes) == 2
    assert {lote.id for lote in lotes} == {"L01", "L02"}


def test_carregar_membros_monta_as_faixas() -> None:
    membros = carregar_membros(FIXTURES / "perfis" / "familia_demo.json")

    assert len(membros) == 1
    membro = membros[0]
    assert membro.faixas["kcal"].minimo == 1500
    assert membro.faixas["kcal"].alvo == 1800
    assert membro.tags_bloqueadas == frozenset()


def test_carregar_catalogo_junta_tudo() -> None:
    catalogo = carregar_catalogo(FIXTURES)

    assert catalogo.total_ingredientes() == 3
    assert catalogo.total_receitas() == 2
    assert catalogo.quantidade("r1", "1") == 0.1
    assert catalogo.nutriente("r1", "kcal") == 400.0
    assert "p1" in catalogo.membros
    # ingrediente "2" (ovo) nao tem lote em estoque_inicial.csv, mas o
    # catalogo precisa sintetizar um para R8/R9 conseguirem contabilizar.
    assert catalogo.lotes_do_ingrediente("2")


def test_arquivo_ausente_levanta_erro_de_carga() -> None:
    with pytest.raises(ErroDeCarga, match="nao encontrado"):
        carregar_ingredientes(FIXTURES / "nao_existe.csv")


def test_coluna_ausente_levanta_erro_de_carga(tmp_path: Path) -> None:
    caminho = tmp_path / "ingredientes.csv"
    caminho.write_text("id,nome\n1,Arroz\n", encoding="utf-8")

    with pytest.raises(ErroDeCarga, match="preco_embalagem"):
        carregar_ingredientes(caminho)
