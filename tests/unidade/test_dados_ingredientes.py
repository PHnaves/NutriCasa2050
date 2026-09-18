import csv
from pathlib import Path


def _carregar_ingredientes():
    caminho = Path(__file__).resolve().parents[2] / "data" / "ingredientes.csv"
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def test_validades_preenchidas():
    ingredientes = _carregar_ingredientes()

    assert ingredientes, "O arquivo de ingredientes está vazio."
    for item in ingredientes:
        assert item["validade_dias"], f"Ingrediente sem validade: {item['nome']}"


def test_validades_positivas():
    ingredientes = _carregar_ingredientes()

    for item in ingredientes:
        validade = int(item["validade_dias"])
        assert validade > 0, f"Validade inválida para {item['nome']}: {item['validade_dias']}"


def test_precos_preenchidos_e_positivos():
    ingredientes = _carregar_ingredientes()

    for item in ingredientes:
        assert item["preco_embalagem"], f"Preço da embalagem ausente para {item['nome']}."
        preco = float(item["preco_embalagem"])
        assert preco > 0, f"Preço inválido para {item['nome']}: {item['preco_embalagem']}"


def test_tamanhos_de_embalagem_preenchidos():
    ingredientes = _carregar_ingredientes()

    for item in ingredientes:
        assert item["tamanho_embalagem"], f"Tamanho da embalagem ausente para {item['nome']}."
        tamanho = float(item["tamanho_embalagem"])
        assert tamanho > 0, f"Tamanho inválido para {item['nome']}: {item['tamanho_embalagem']}"
