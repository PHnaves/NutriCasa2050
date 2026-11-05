"""Procedencia dos precos (Sprint 6): data/precos_coletados.csv tem que
bater com data/ingredientes.csv — senao a pagina "Ingredientes e precos"
mostra uma origem para um preco que o modelo nao usa."""
from __future__ import annotations

import csv
from pathlib import Path

from app import descrever_embalagem, ler_precos_coletados

DATA = Path(__file__).resolve().parents[2] / "data"


def _ingredientes() -> dict[str, dict]:
    with (DATA / "ingredientes.csv").open(encoding="utf-8", newline="") as arquivo:
        return {linha["id"]: linha for linha in csv.DictReader(arquivo)}


def test_todo_ingrediente_tem_procedencia_e_o_preco_bate() -> None:
    ingredientes = _ingredientes()
    precos = ler_precos_coletados()

    assert set(precos) == set(ingredientes)
    for ing_id, linha in ingredientes.items():
        assert float(precos[ing_id]["preco_embalagem"]) == float(linha["preco_embalagem"])
        assert float(precos[ing_id]["tamanho_embalagem"]) == float(linha["tamanho_embalagem"])


def test_preco_coletado_tem_produto_e_link() -> None:
    for linha in ler_precos_coletados().values():
        assert linha["origem"] in ("Atacadão", "estimativa")
        if linha["origem"] == "Atacadão":
            assert linha["produto"]
            assert linha["link"].startswith("https://")


def test_arquivo_ausente_nao_quebra(tmp_path) -> None:
    assert ler_precos_coletados(tmp_path / "nao_existe.csv") == {}


def test_descrever_embalagem() -> None:
    assert descrever_embalagem(0.015, "kg") == "15 g"
    assert descrever_embalagem(0.5, "litro") == "500 ml"
    assert descrever_embalagem(12, "unidade") == "12 unidades"
    assert descrever_embalagem(1, "kg") == "1 kg"
    assert descrever_embalagem(1.03, "kg") == "1,03 kg"
