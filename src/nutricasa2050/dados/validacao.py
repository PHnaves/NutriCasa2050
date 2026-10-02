from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"

ARQUIVO_INGREDIENTES = DATA_DIR / "ingredientes.csv"
ARQUIVO_RECEITAS = DATA_DIR / "receitas.csv"
ARQUIVO_MATRIZ = DATA_DIR / "matriz_a.csv"
ARQUIVO_LOTES = DATA_DIR / "estoque_inicial.csv"
ARQUIVO_FAIXAS = DATA_DIR / "faixas.csv"

COLUNAS_NUTRIENTES = (
	"calorias_kcal",
	"proteina_g",
	"carboidrato_g",
	"gordura_g",
	"fibra_g",
	"sodio_mg",
)


@dataclass
class Relatorio:
	erros: list[str] = field(default_factory=list)
	avisos: list[str] = field(default_factory=list)

	def erro(self, mensagem: str) -> None:
		self.erros.append(mensagem)

	def aviso(self, mensagem: str) -> None:
		self.avisos.append(mensagem)

	@property
	def ok(self) -> bool:
		return not self.erros

	def imprimir(self) -> None:
		for mensagem in self.avisos:
			print(f"AVISO: {mensagem}")
		for mensagem in self.erros:
			print(f"ERRO: {mensagem}", file=sys.stderr)


def _carregar_csv(caminho: Path) -> list[dict[str, str]]:
	if not caminho.exists():
		return []

	with caminho.open(encoding="utf-8", newline="") as arquivo:
		return list(csv.DictReader(arquivo))


def _texto(valor: Any) -> str:
	if valor is None:
		return ""
	return str(valor).strip()


def _valor_decimal(valor: Any) -> float | None:
	texto = _texto(valor)
	if not texto:
		return None
	return float(texto)


def _valor_inteiro(valor: Any) -> int | None:
	texto = _texto(valor)
	if not texto:
		return None
	return int(texto)


def _campo_id(item: dict[str, str]) -> str:
	return _texto(item.get("id"))


def _campo_lote_id(item: dict[str, str]) -> str:
	return _texto(item.get("lote_id") or item.get("id"))


def _ingredientes_por_id(ingredientes: list[dict[str, str]]) -> dict[str, dict[str, str]]:
	return {_campo_id(item): item for item in ingredientes if _campo_id(item)}


def _receitas_por_id(receitas: list[dict[str, str]]) -> dict[str, dict[str, str]]:
	return {_campo_id(item): item for item in receitas if _campo_id(item)}


def _receitas_por_ingrediente(matriz: list[dict[str, str]]) -> dict[str, set[str]]:
	receitas_por_ingrediente: dict[str, set[str]] = defaultdict(set)
	for item in matriz:
		receita_id = _texto(item.get("receita_id"))
		ingrediente_id = _texto(item.get("ingrediente_id"))
		if receita_id and ingrediente_id:
			receitas_por_ingrediente[ingrediente_id].add(receita_id)
	return receitas_por_ingrediente


def _ingredientes_por_receita(matriz: list[dict[str, str]]) -> dict[str, set[str]]:
	ingredientes_por_receita: dict[str, set[str]] = defaultdict(set)
	for item in matriz:
		receita_id = _texto(item.get("receita_id"))
		ingrediente_id = _texto(item.get("ingrediente_id"))
		if receita_id and ingrediente_id:
			ingredientes_por_receita[receita_id].add(ingrediente_id)
	return ingredientes_por_receita


def _verificar_ids_unicos(
	itens: list[dict[str, str]],
	relatorio: Relatorio,
	campo_id: str,
	rotulo: str,
) -> None:
	ids = [_texto(item.get(campo_id)) for item in itens]
	vazios = [indice + 1 for indice, valor in enumerate(ids) if not valor]
	if vazios:
		relatorio.erro(
			f"{rotulo}: registros sem {campo_id} nas linhas {', '.join(map(str, vazios))}."
		)

	duplicados = sorted(
		valor
		for valor, quantidade in Counter(valor for valor in ids if valor).items()
		if quantidade > 1
	)
	if duplicados:
		relatorio.erro(f"{rotulo}: IDs duplicados encontrados: {', '.join(duplicados)}.")


def checar_ids_unicos(
	ingredientes: list[dict[str, str]],
	receitas: list[dict[str, str]],
	lotes: list[dict[str, str]],
	relatorio: Relatorio,
) -> None:
	_verificar_ids_unicos(ingredientes, relatorio, "id", "Ingredientes")
	_verificar_ids_unicos(receitas, relatorio, "id", "Receitas")
	campo_lote = "lote_id" if lotes and "lote_id" in lotes[0] else "id"
	_verificar_ids_unicos(lotes, relatorio, campo_lote, "Lotes")


def checar_ingredientes_existem(
	ingredientes: list[dict[str, str]],
	receitas: list[dict[str, str]],
	matriz: list[dict[str, str]],
	relatorio: Relatorio,
) -> None:
	ingredientes_conhecidos = set(_ingredientes_por_id(ingredientes))
	receitas_conhecidas = set(_receitas_por_id(receitas))

	for indice, item in enumerate(matriz, start=2):
		receita_id = _texto(item.get("receita_id"))
		ingrediente_id = _texto(item.get("ingrediente_id"))

		if receita_id not in receitas_conhecidas:
			relatorio.erro(
				f"Linha {indice}: receita desconhecida na matriz: {receita_id or '[vazio]'}."
			)
		if ingrediente_id not in ingredientes_conhecidos:
			relatorio.erro(
				"Linha "
				f"{indice}: ingrediente desconhecido na matriz: {ingrediente_id or '[vazio]'}."
			)


def checar_receitas_nao_vazias(
	receitas: list[dict[str, str]],
	matriz: list[dict[str, str]],
	relatorio: Relatorio,
) -> None:
	ingredientes_por_receita = _ingredientes_por_receita(matriz)
	for receita in receitas:
		receita_id = _campo_id(receita)
		quantidade = len(ingredientes_por_receita.get(receita_id, set()))
		if quantidade < 2:
			relatorio.erro(
				f"Receita {receita_id or '[vazio]'} tem apenas {quantidade} ingrediente(s)."
			)


def checar_ingredientes_orfaos(
	ingredientes: list[dict[str, str]],
	matriz: list[dict[str, str]],
	relatorio: Relatorio,
) -> None:
	receitas_por_ingrediente = _receitas_por_ingrediente(matriz)
	nomes_por_id = {
		_campo_id(item): _texto(item.get("nome")) or _campo_id(item)
		for item in ingredientes
		if _campo_id(item)
	}

	for ingrediente_id, nome in nomes_por_id.items():
		quantidade_receitas = len(receitas_por_ingrediente.get(ingrediente_id, set()))
		if quantidade_receitas < 2:
			relatorio.erro(
				f"Ingrediente {nome} aparece em apenas {quantidade_receitas} receita(s)."
			)


def checar_precos_e_embalagens(
	ingredientes: list[dict[str, str]],
	relatorio: Relatorio,
) -> None:
	for item in ingredientes:
		nome = _texto(item.get("nome")) or _campo_id(item) or "[sem nome]"
		preco = _valor_decimal(item.get("preco_embalagem"))
		tamanho = _valor_decimal(item.get("tamanho_embalagem"))

		if preco is None:
			relatorio.erro(f"Ingrediente {nome} sem preco_embalagem.")
		elif preco <= 0:
			relatorio.erro(f"Ingrediente {nome} com preco_embalagem inválido: {preco}.")

		if tamanho is None:
			relatorio.erro(f"Ingrediente {nome} sem tamanho_embalagem.")
		elif tamanho <= 0:
			relatorio.erro(f"Ingrediente {nome} com tamanho_embalagem inválido: {tamanho}.")


def checar_validades(
	ingredientes: list[dict[str, str]],
	relatorio: Relatorio,
) -> None:
	for item in ingredientes:
		nome = _texto(item.get("nome")) or _campo_id(item) or "[sem nome]"
		validade = _valor_inteiro(item.get("validade_dias"))

		if validade is None:
			relatorio.erro(f"Ingrediente {nome} sem validade_dias.")
		elif validade <= 0:
			relatorio.erro(f"Ingrediente {nome} com validade_dias inválida: {validade}.")


def checar_nutrientes_completos(
	ingredientes: list[dict[str, str]],
	relatorio: Relatorio,
) -> None:
	for item in ingredientes:
		nome = _texto(item.get("nome")) or _campo_id(item) or "[sem nome]"
		faltando = [campo for campo in COLUNAS_NUTRIENTES if not _texto(item.get(campo))]
		if faltando:
			relatorio.erro(
				f"Ingrediente {nome} sem nutrientes completos: {', '.join(faltando)}."
			)


def checar_calorias_plausiveis(
	ingredientes: list[dict[str, str]],
	receitas: list[dict[str, str]],
	matriz: list[dict[str, str]],
	relatorio: Relatorio,
	minimo: float = 100.0,
	maximo: float = 1500.0,
) -> None:
	ingredientes_por_id = _ingredientes_por_id(ingredientes)
	linhas_por_receita: dict[str, list[dict[str, str]]] = defaultdict(list)
	for item in matriz:
		receita_id = _texto(item.get("receita_id"))
		if receita_id:
			linhas_por_receita[receita_id].append(item)

	for receita in receitas:
		receita_id = _campo_id(receita)
		calorias = 0.0
		conseguiu_calcular = True

		for item in linhas_por_receita.get(receita_id, []):
			ingrediente_id = _texto(item.get("ingrediente_id"))
			ingrediente = ingredientes_por_id.get(ingrediente_id)
			if not ingrediente:
				conseguiu_calcular = False
				continue

			calorias_ingrediente = _valor_decimal(ingrediente.get("calorias_kcal"))
			quantidade = _valor_decimal(item.get("quantidade_por_porcao"))
			if calorias_ingrediente is None or quantidade is None:
				conseguiu_calcular = False
				continue

			calorias += calorias_ingrediente * quantidade

		if conseguiu_calcular and not (minimo <= calorias <= maximo):
			relatorio.erro(
				f"Receita {receita_id or '[vazio]'} com {calorias:.1f} kcal por porção, "
				f"fora do intervalo {minimo:.0f}-{maximo:.0f}."
			)


def checar_lotes_validos(
	lotes: list[dict[str, str]],
	ingredientes: list[dict[str, str]],
	relatorio: Relatorio,
) -> None:
	ingredientes_conhecidos = set(_ingredientes_por_id(ingredientes))

	for indice, item in enumerate(lotes, start=2):
		lote_id = _campo_lote_id(item) or f"linha {indice}"
		ingrediente_id = _texto(item.get("ingrediente_id"))
		quantidade = _valor_decimal(item.get("quantidade"))
		dia_vencimento = _valor_inteiro(item.get("dia_vencimento"))

		if not lote_id:
			relatorio.erro(f"Lote sem identificador na linha {indice}.")
		if ingrediente_id not in ingredientes_conhecidos:
			relatorio.erro(
				"Lote "
				f"{lote_id} referencia ingrediente desconhecido: {ingrediente_id or '[vazio]'}."
			)
		if quantidade is None or quantidade <= 0:
			relatorio.erro(f"Lote {lote_id} com quantidade inválida: {item.get('quantidade')!r}.")
		if dia_vencimento is None or dia_vencimento <= 0:
			relatorio.erro(
				f"Lote {lote_id} com dia_vencimento inválido: {item.get('dia_vencimento')!r}."
			)


def checar_tem_lote_vencendo_cedo(
	lotes: list[dict[str, str]],
	relatorio: Relatorio,
	limite_dias: int = 3,
) -> None:
	vencendo_cedo = []
	for item in lotes:
		lote_id = _campo_lote_id(item) or "[sem lote_id]"
		dia_vencimento = _valor_inteiro(item.get("dia_vencimento"))
		if dia_vencimento is not None and dia_vencimento <= limite_dias:
			vencendo_cedo.append(f"{lote_id} ({dia_vencimento} dia(s))")

	if vencendo_cedo:
		relatorio.aviso("Lotes vencendo cedo: " + ", ".join(vencendo_cedo) + ".")


def checar_faixas_coerentes(
	faixas: list[dict[str, str]],
	relatorio: Relatorio,
) -> None:
	for indice, item in enumerate(faixas, start=2):
		nome = _texto(item.get("nutriente")) or f"linha {indice}"
		minimo = _valor_decimal(item.get("minimo"))
		maximo = _valor_decimal(item.get("maximo"))

		if minimo is None or maximo is None:
			relatorio.erro(f"Faixa {nome} com minimo/maximo ausentes.")
			continue

		if minimo > maximo:
			relatorio.erro(
				f"Faixa {nome} incoerente: minimo {minimo} maior que maximo {maximo}."
			)


def validar(
	ingredientes: list[dict[str, str]] | None = None,
	receitas: list[dict[str, str]] | None = None,
	matriz: list[dict[str, str]] | None = None,
	lotes: list[dict[str, str]] | None = None,
	faixas: list[dict[str, str]] | None = None,
) -> Relatorio:
	ingredientes = _carregar_csv(ARQUIVO_INGREDIENTES) if ingredientes is None else ingredientes
	receitas = _carregar_csv(ARQUIVO_RECEITAS) if receitas is None else receitas
	matriz = _carregar_csv(ARQUIVO_MATRIZ) if matriz is None else matriz
	lotes = _carregar_csv(ARQUIVO_LOTES) if lotes is None else lotes
	faixas = _carregar_csv(ARQUIVO_FAIXAS) if faixas is None else faixas

	relatorio = Relatorio()
	checar_ids_unicos(ingredientes, receitas, lotes, relatorio)
	checar_ingredientes_existem(ingredientes, receitas, matriz, relatorio)
	checar_receitas_nao_vazias(receitas, matriz, relatorio)
	checar_ingredientes_orfaos(ingredientes, matriz, relatorio)
	checar_precos_e_embalagens(ingredientes, relatorio)
	checar_validades(ingredientes, relatorio)
	checar_nutrientes_completos(ingredientes, relatorio)
	checar_calorias_plausiveis(ingredientes, receitas, matriz, relatorio)
	checar_lotes_validos(lotes, ingredientes, relatorio)
	checar_tem_lote_vencendo_cedo(lotes, relatorio)
	checar_faixas_coerentes(faixas, relatorio)
	return relatorio


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Valida os CSVs do NutriCasa 2050")
	parser.add_argument("--validar", action="store_true", help="executa as checagens")
	args = parser.parse_args(argv)

	if not args.validar:
		parser.print_help()
		return 1

	relatorio = validar()
	relatorio.imprimir()
	return 0 if relatorio.ok else 1


if __name__ == "__main__":
	raise SystemExit(main())
