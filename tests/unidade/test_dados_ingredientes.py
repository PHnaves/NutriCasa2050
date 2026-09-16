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
