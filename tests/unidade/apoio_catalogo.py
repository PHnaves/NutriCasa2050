"""Fabrica de catalogos pequenos para os testes de otimizacao. Nao e um
modulo de teste em si (sem prefixo test_), so apoio compartilhado."""
from __future__ import annotations

from nutricasa2050.dominio import Catalogo, Faixa, Ingrediente, Lote, Membro, Receita


def ingrediente(
    id_: str,
    nome: str | None = None,
    preco_embalagem: float = 5.0,
    tamanho_embalagem: float = 1.0,
    validade_dias: int = 30,
    categoria: str = "secos",
    unidade: str = "kg",
) -> Ingrediente:
    return Ingrediente(
        id=id_,
        nome=nome or f"Ingrediente {id_}",
        unidade=unidade,
        categoria=categoria,
        validade_dias=validade_dias,
        preco_embalagem=preco_embalagem,
        tamanho_embalagem=tamanho_embalagem,
    )


def receita(
    id_: str,
    nome: str | None = None,
    tempo_min: int = 20,
    tags: frozenset[str] = frozenset(),
    preferencia: float = 0.5,
) -> Receita:
    return Receita(
        id=id_,
        nome=nome or f"Receita {id_}",
        tempo_min=tempo_min,
        tags=tags,
        preferencia=preferencia,
    )


def membro(
    id_: str,
    nome: str | None = None,
    fator_porcao: float = 1.0,
    tags_bloqueadas: frozenset[str] = frozenset(),
    faixas: dict[str, Faixa] | None = None,
) -> Membro:
    return Membro(
        id=id_,
        nome=nome or f"Membro {id_}",
        fator_porcao=fator_porcao,
        tags_bloqueadas=tags_bloqueadas,
        faixas=faixas or {},
    )


def lote(
    id_: str, ingrediente_id: str, quantidade: float = 1.0, dia_vencimento: int = 30
) -> Lote:
    return Lote(
        id=id_,
        ingrediente_id=ingrediente_id,
        quantidade=quantidade,
        dia_vencimento=dia_vencimento,
    )


def construir_catalogo(
    ingredientes: list[Ingrediente] | None = None,
    receitas: list[Receita] | None = None,
    matriz_a: dict[tuple[str, str], float] | None = None,
    nutrientes: dict[tuple[str, str], float] | None = None,
    lotes: list[Lote] | None = None,
    membros: list[Membro] | None = None,
) -> Catalogo:
    return Catalogo(
        ingredientes={i.id: i for i in (ingredientes or [])},
        receitas={r.id: r for r in (receitas or [])},
        matriz_a=matriz_a or {},
        nutrientes=nutrientes or {},
        lotes={lote_item.id: lote_item for lote_item in (lotes or [])},
        membros={membro_item.id: membro_item for membro_item in (membros or [])},
    )
