from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from nutricasa2050.dominio import Catalogo, Faixa, Ingrediente, Lote, Membro, Receita

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"


class ErroDeCarga(RuntimeError):
    """Arquivo ou coluna faltando ao carregar os dados do catalogo."""


def _ler_csv(caminho: Path, colunas_esperadas: list[str]) -> pd.DataFrame:
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroDeCarga(f"Arquivo nao encontrado: {caminho}")

    try:
        df = pd.read_csv(caminho, dtype=str)
    except Exception as exc:
        raise ErroDeCarga(f"Erro ao ler {caminho}: {exc}") from exc

    faltando = [coluna for coluna in colunas_esperadas if coluna not in df.columns]
    if faltando:
        raise ErroDeCarga(f"Arquivo {caminho} sem a(s) coluna(s): {', '.join(faltando)}")

    return df


def _ler_json(caminho: Path) -> object:
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroDeCarga(f"Arquivo nao encontrado: {caminho}")

    try:
        with caminho.open(encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except Exception as exc:
        raise ErroDeCarga(f"Erro ao ler {caminho}: {exc}") from exc


def carregar_ingredientes(caminho: Path) -> dict[str, Ingrediente]:
    df = _ler_csv(
        caminho,
        [
            "id",
            "nome",
            "unidade",
            "categoria",
            "validade_dias",
            "preco_embalagem",
            "tamanho_embalagem",
        ],
    )

    ingredientes: dict[str, Ingrediente] = {}
    for linha in df.itertuples(index=False):
        ingredientes[linha.id] = Ingrediente(
            id=linha.id,
            nome=linha.nome,
            unidade=linha.unidade,
            categoria=linha.categoria,
            validade_dias=int(linha.validade_dias),
            preco_embalagem=float(linha.preco_embalagem),
            tamanho_embalagem=float(linha.tamanho_embalagem),
        )
    return ingredientes


def carregar_receitas(caminho: Path) -> dict[str, Receita]:
    df = _ler_csv(caminho, ["id", "nome", "tempo_min", "tags_dieta", "preferencia"])

    receitas: dict[str, Receita] = {}
    for linha in df.itertuples(index=False):
        tags_texto = linha.tags_dieta if pd.notna(linha.tags_dieta) else ""
        tags = frozenset(t for t in tags_texto.split(";") if t)
        receitas[linha.id] = Receita(
            id=linha.id,
            nome=linha.nome,
            tempo_min=int(linha.tempo_min),
            tags=tags,
            preferencia=float(linha.preferencia),
        )
    return receitas


def carregar_matriz_a(caminho: Path) -> dict[tuple[str, str], float]:
    df = _ler_csv(caminho, ["receita_id", "ingrediente_id", "quantidade_por_porcao"])
    return {
        (linha.receita_id, linha.ingrediente_id): float(linha.quantidade_por_porcao)
        for linha in df.itertuples(index=False)
    }


def carregar_nutrientes(caminho: Path) -> dict[tuple[str, str], float]:
    df = _ler_csv(caminho, ["receita_id", "nutriente", "valor"])
    return {
        (linha.receita_id, linha.nutriente): float(linha.valor)
        for linha in df.itertuples(index=False)
    }


def carregar_lotes(caminho: Path) -> list[Lote]:
    df = _ler_csv(caminho, ["lote_id", "ingrediente_id", "quantidade", "dia_vencimento"])
    return [
        Lote(
            id=linha.lote_id,
            ingrediente_id=linha.ingrediente_id,
            quantidade=float(linha.quantidade),
            dia_vencimento=int(linha.dia_vencimento),
        )
        for linha in df.itertuples(index=False)
    ]


def carregar_membros(caminho: Path) -> list[Membro]:
    dados = _ler_json(caminho)
    if not isinstance(dados, list):
        raise ErroDeCarga(f"Arquivo {caminho} deveria conter uma lista de membros.")

    membros: list[Membro] = []
    for item in dados:
        try:
            faixas = {
                nutriente: Faixa(
                    minimo=float(faixa["min"]),
                    maximo=float(faixa["max"]),
                    alvo=float(faixa["alvo"]),
                )
                for nutriente, faixa in item["faixas"].items()
            }
            membros.append(
                Membro(
                    id=item["id"],
                    nome=item["nome"],
                    fator_porcao=float(item["fator_porcao"]),
                    tags_bloqueadas=frozenset(item["tags_bloqueadas"]),
                    faixas=faixas,
                )
            )
        except KeyError as exc:
            raise ErroDeCarga(f"Arquivo {caminho} sem o campo {exc}.") from exc

    return membros


def _garantir_lote_por_ingrediente(
    lotes: dict[str, Lote], ingredientes: dict[str, Ingrediente]
) -> dict[str, Lote]:
    """Garante que todo ingrediente tenha pelo menos um lote (card S2-05: "um
    lote por ingrediente" e necessario para R8/R9 conseguirem contabilizar o
    consumo de QUALQUER ingrediente, mesmo um que nunca tenha vindo com
    estoque inicial. O lote sintetico comeca com quantidade zero e so
    recebe saldo quando o modelo decidir comprar aquele ingrediente."""
    lotes = dict(lotes)
    cobertos = {lote.ingrediente_id for lote in lotes.values()}
    for ingrediente_id, ingrediente in ingredientes.items():
        if ingrediente_id in cobertos:
            continue
        lote_id = f"sem_estoque_{ingrediente_id}"
        lotes[lote_id] = Lote(
            id=lote_id,
            ingrediente_id=ingrediente_id,
            quantidade=0.0,
            dia_vencimento=ingrediente.validade_dias,
        )
    return lotes


def carregar_catalogo(pasta: Path | str | None = None) -> Catalogo:
    pasta = Path(pasta) if pasta is not None else DATA_DIR

    ingredientes = carregar_ingredientes(pasta / "ingredientes.csv")
    receitas = carregar_receitas(pasta / "receitas.csv")
    matriz_a = carregar_matriz_a(pasta / "matriz_a.csv")
    nutrientes = carregar_nutrientes(pasta / "nutrientes.csv")
    lotes = {lote.id: lote for lote in carregar_lotes(pasta / "estoque_inicial.csv")}
    lotes = _garantir_lote_por_ingrediente(lotes, ingredientes)
    membros_lista = carregar_membros(pasta / "perfis" / "familia_demo.json")
    membros = {membro.id: membro for membro in membros_lista}

    return Catalogo(
        ingredientes=ingredientes,
        receitas=receitas,
        matriz_a=matriz_a,
        nutrientes=nutrientes,
        lotes=lotes,
        membros=membros,
    )
