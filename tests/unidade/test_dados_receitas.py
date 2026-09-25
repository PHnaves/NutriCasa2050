import csv
from collections import Counter
from pathlib import Path


ARQUIVO_RECEITAS = Path(__file__).resolve().parents[2] / "data" / "receitas.csv"
ARQUIVO_MATRIZ = Path(__file__).resolve().parents[2] / "data" / "matriz_a.csv"
ARQUIVO_INGREDIENTES = Path(__file__).resolve().parents[2] / "data" / "ingredientes.csv"
TAGS_CONHECIDAS = {"vegetariano", "sem_gluten", "sem_lactose", "alto_sodio"}


def _carregar_csv(caminho):
	with caminho.open(encoding="utf-8", newline="") as arquivo:
		return list(csv.DictReader(arquivo))


def test_catalogo_tem_24_receitas():
	receitas = _carregar_csv(ARQUIVO_RECEITAS)

	assert len(receitas) == 24, f"Esperadas 24 receitas, mas foram encontradas {len(receitas)}."


def test_receitas_usam_ingredientes_conhecidos():
	receitas = _carregar_csv(ARQUIVO_RECEITAS)
	matriz = _carregar_csv(ARQUIVO_MATRIZ)
	ingredientes = _carregar_csv(ARQUIVO_INGREDIENTES)

	receitas_conhecidas = {item["id"] for item in receitas}
	ingredientes_conhecidos = {item["id"] for item in ingredientes}

	for item in matriz:
		assert item["receita_id"] in receitas_conhecidas, f"Receita desconhecida na matriz: {item['receita_id']}"
		assert (
			item["ingrediente_id"] in ingredientes_conhecidos
		), f"Ingrediente desconhecido na matriz: {item['ingrediente_id']}"


def test_nenhuma_receita_com_menos_de_dois_ingredientes():
	receitas = _carregar_csv(ARQUIVO_RECEITAS)
	matriz = _carregar_csv(ARQUIVO_MATRIZ)

	contagem_por_receita = Counter(item["receita_id"] for item in matriz)

	for receita in receitas:
		quantidade = contagem_por_receita[receita["id"]]
		assert quantidade >= 2, f"Receita {receita['id']} tem apenas {quantidade} ingrediente(s)."


def test_tags_de_dieta_sao_conhecidas():
	receitas = _carregar_csv(ARQUIVO_RECEITAS)

	for receita in receitas:
		tags = {tag.strip() for tag in receita["tags_dieta"].split(";") if tag.strip()}
		assert tags <= TAGS_CONHECIDAS, f"Tags inválidas em {receita['id']}: {tags - TAGS_CONHECIDAS}"


def test_preferencia_entre_zero_e_um():
	receitas = _carregar_csv(ARQUIVO_RECEITAS)

	for receita in receitas:
		preferencia = float(receita["preferencia"])
		assert 0 <= preferencia <= 1, f"Preferência inválida em {receita['id']}: {receita['preferencia']}"
