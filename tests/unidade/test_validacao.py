from __future__ import annotations

import csv
import shutil
from pathlib import Path

from nutricasa2050.dados import validacao as cli_validacao
from nutricasa2050.dados import validacao as core_validacao

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "validacao"


def carregar(nome: str) -> list[dict[str, str]]:
    with (FIXTURES / nome).open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def salvar(caminho: Path, linhas: list[dict[str, str]], campos: list[str]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def test_detecta_ingrediente_orfao() -> None:
    ingredientes = carregar("ingredientes.csv")
    matriz = carregar("matriz.csv")
    relatorio = core_validacao.Relatorio()

    matriz = [
        item
        for item in matriz
        if not (item["receita_id"] == "r2" and item["ingrediente_id"] == "3")
    ]

    core_validacao.checar_ingredientes_orfaos(ingredientes, matriz, relatorio)

    assert any("ingrediente" in erro.lower() for erro in relatorio.erros)


def test_detecta_ingrediente_inexistente() -> None:
    ingredientes = carregar("ingredientes.csv")
    receitas = carregar("receitas.csv")
    matriz = carregar("matriz.csv")
    relatorio = core_validacao.Relatorio()

    matriz.append(
        {
            "receita_id": "r1",
            "ingrediente_id": "999",
            "quantidade_por_porcao": "0.1",
        }
    )

    core_validacao.checar_ingredientes_existem(ingredientes, receitas, matriz, relatorio)

    assert any("ingrediente desconhecido" in erro.lower() for erro in relatorio.erros)


def test_detecta_receita_vazia() -> None:
    receitas = carregar("receitas.csv")
    matriz = carregar("matriz.csv")
    relatorio = core_validacao.Relatorio()

    matriz = [
        item
        for item in matriz
        if not (item["receita_id"] == "r1" and item["ingrediente_id"] in {"2", "3"})
    ]

    core_validacao.checar_receitas_nao_vazias(receitas, matriz, relatorio)

    assert any("apenas 1 ingrediente" in erro.lower() for erro in relatorio.erros)


def test_detecta_preco_nulo() -> None:
    ingredientes = carregar("ingredientes.csv")
    relatorio = core_validacao.Relatorio()

    ingredientes[1]["preco_embalagem"] = ""

    core_validacao.checar_precos_e_embalagens(ingredientes, relatorio)

    assert any("preco_embalagem" in erro.lower() for erro in relatorio.erros)


def test_detecta_nutriente_faltante() -> None:
    receitas = carregar("receitas.csv")
    nutrientes = carregar("nutrientes.csv")
    relatorio = core_validacao.Relatorio()

    nutrientes = [
        item
        for item in nutrientes
        if not (item["receita_id"] == "r1" and item["nutriente"] == "fibra_g")
    ]

    core_validacao.checar_nutrientes_completos(receitas, nutrientes, relatorio)

    assert any("sem nutrientes completos" in erro.lower() for erro in relatorio.erros)


def test_detecta_caloria_implausivel() -> None:
    receitas = carregar("receitas.csv")
    nutrientes = carregar("nutrientes.csv")
    relatorio = core_validacao.Relatorio()

    for item in nutrientes:
        if item["receita_id"] == "r1" and item["nutriente"] == "kcal":
            item["valor"] = "3000"

    core_validacao.checar_calorias_plausiveis(receitas, nutrientes, relatorio)

    assert any("fora do intervalo" in erro.lower() for erro in relatorio.erros)


def test_detecta_faixa_invertida() -> None:
    faixas = carregar("faixas.csv")
    relatorio = core_validacao.Relatorio()

    faixas[0]["minimo"] = "10"
    faixas[0]["maximo"] = "5"

    core_validacao.checar_faixas_coerentes(faixas, relatorio)

    assert any("incoerente" in erro.lower() for erro in relatorio.erros)


def test_aceita_catalogo_valido() -> None:
    ingredientes = carregar("ingredientes.csv")
    receitas = carregar("receitas.csv")
    matriz = carregar("matriz.csv")
    lotes = carregar("lotes.csv")
    faixas = carregar("faixas.csv")
    nutrientes = carregar("nutrientes.csv")

    relatorio = core_validacao.validar(
        ingredientes=ingredientes,
        receitas=receitas,
        matriz=matriz,
        lotes=lotes,
        faixas=faixas,
        nutrientes=nutrientes,
    )

    assert relatorio.ok
    assert not relatorio.erros


def test_main_sai_com_erro_quando_invalido(tmp_path, monkeypatch, capsys) -> None:
    nomes = (
        "ingredientes.csv",
        "receitas.csv",
        "matriz.csv",
        "lotes.csv",
        "faixas.csv",
        "nutrientes.csv",
    )
    for nome in nomes:
        shutil.copyfile(FIXTURES / nome, tmp_path / nome)

    ingredientes = carregar("ingredientes.csv")
    ingredientes[1]["preco_embalagem"] = ""
    salvar(
        tmp_path / "ingredientes.csv",
        ingredientes,
        list(ingredientes[0].keys()),
    )

    monkeypatch.setattr(core_validacao, "ARQUIVO_INGREDIENTES", tmp_path / "ingredientes.csv")
    monkeypatch.setattr(core_validacao, "ARQUIVO_RECEITAS", tmp_path / "receitas.csv")
    monkeypatch.setattr(core_validacao, "ARQUIVO_MATRIZ", tmp_path / "matriz.csv")
    monkeypatch.setattr(core_validacao, "ARQUIVO_LOTES", tmp_path / "lotes.csv")
    monkeypatch.setattr(core_validacao, "ARQUIVO_FAIXAS", tmp_path / "faixas.csv")
    monkeypatch.setattr(core_validacao, "ARQUIVO_NUTRIENTES", tmp_path / "nutrientes.csv")

    codigo = cli_validacao.main(["--validar"])
    saida = capsys.readouterr()

    assert codigo == 1
    assert "preco_embalagem" in saida.err.lower()
