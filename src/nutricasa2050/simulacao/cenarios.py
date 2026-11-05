"""Gerador de cenarios (card S4-01): cada cenario e uma semana levemente
diferente da "padrao", para a Monte Carlo (S4-04) mostrar se um resultado
se sustenta ou foi sorte com um conjunto especifico de dados.

Duas etapas separadas de proposito:
  1. gerar_cenario(semente) decide OS NUMEROS do sorteio (quantos itens
     esquecer, quantos lotes estragam antes, etc.) usando so a semente —
     nao precisa (nem pode) saber ainda quais ingredientes/lotes existem.
  2. aplicar_cenario(catalogo, parametros, cenario) e quem de fato escolhe
     QUAIS ingredientes/lotes/dias, porque so ela tem o catalogo real em
     maos. Cada perturbacao usa seu PROPRIO gerador (random.Random(semente
     + deslocamento), nunca o random global do Python) para nao
     correlacionar os sorteios entre si nem com chamadas de fora.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace

from nutricasa2050.dominio import Catalogo, Membro, Parametros

# Nomes "tipicos" assumidos por pular_refeicoes — a funcao recebe so
# (catalogo, cenario), sem os parametros reais, entao nao tem como saber
# os nomes de refeicao em uso; cobre o padrao de 3 refeicoes/dia do
# projeto (ver dominio.NOMES_REFEICOES_PADRAO).
_REFEICOES_TIPICAS = ("cafe_da_manha", "almoco", "jantar")
_DIAS_TIPICOS = range(1, 8)


@dataclass(frozen=True)
class Cenario:
    semente: int
    perturbacao_preco: float = 0.15  # amplitude maxima (+-) de cada preco
    membros_extras: int = 0  # quantos visitantes entram nesta semana
    refeicoes_puladas: int = 0  # quantas refeicoes do horizonte nao aconteceram
    itens_esquecidos: int = 0  # quantos ingredientes ficaram fora da compra
    estragou_antes: int = 0  # quantos lotes tiveram a validade reduzida


def gerar_cenario(semente: int) -> Cenario:
    rng = random.Random(semente)
    return Cenario(
        semente=semente,
        perturbacao_preco=0.15,
        membros_extras=rng.choice([0, 0, 0, 1]),
        refeicoes_puladas=rng.randint(0, 2),
        itens_esquecidos=rng.randint(0, 3),
        estragou_antes=rng.randint(0, 2),
    )


def perturbar_precos(catalogo: Catalogo, cenario: Cenario) -> Catalogo:
    """Cada preco varia, individualmente, em até `cenario.perturbacao_preco`
    (15% por padrao) para cima ou para baixo."""
    rng = random.Random(cenario.semente + 1)
    ingredientes = dict(catalogo.ingredientes)
    for ingrediente_id in sorted(catalogo.ingredientes):
        ingrediente = ingredientes[ingrediente_id]
        fator = 1.0 + rng.uniform(-cenario.perturbacao_preco, cenario.perturbacao_preco)
        ingredientes[ingrediente_id] = replace(
            ingrediente, preco_embalagem=ingrediente.preco_embalagem * fator
        )
    return replace(catalogo, ingredientes=ingredientes)


def adicionar_visita(catalogo: Catalogo, cenario: Cenario) -> Catalogo:
    """Acrescenta membro(s) visitante(s). Simplificacao assumida: o
    visitante fica a semana toda (o modelo nao tem como representar
    presenca parcial sem reescrever R1 — ver Catalogo.refeicoes_puladas
    para o mesmo tipo de limite)."""
    if cenario.membros_extras <= 0:
        return catalogo
    membros = dict(catalogo.membros)
    for indice in range(cenario.membros_extras):
        visitante_id = f"visita_{cenario.semente}_{indice}"
        membros[visitante_id] = Membro(
            id=visitante_id,
            nome=f"Visita {indice + 1}",
            fator_porcao=1.0,
            tags_bloqueadas=frozenset(),
            faixas={},
        )
    return replace(catalogo, membros=membros)


def pular_refeicoes(catalogo: Catalogo, cenario: Cenario) -> Catalogo:
    """Marca algumas refeicoes como "nao aconteceram"
    (Catalogo.refeicoes_puladas) — os baselines (S4-02/03) e o R1 do
    solver otimizado (atualizado no S5-06, ver restricoes.r1_cobertura)
    honram isso: ninguem come nessa refeicao, em nenhuma estrategia."""
    if cenario.refeicoes_puladas <= 0:
        return catalogo
    rng = random.Random(cenario.semente + 3)
    puladas = set(catalogo.refeicoes_puladas)
    tentativas = 0
    alvo = len(puladas) + cenario.refeicoes_puladas
    while len(puladas) < alvo and tentativas < 50:
        puladas.add((rng.choice(list(_DIAS_TIPICOS)), rng.choice(_REFEICOES_TIPICAS)))
        tentativas += 1
    return replace(catalogo, refeicoes_puladas=frozenset(puladas))


def esquecer_itens(catalogo: Catalogo, cenario: Cenario) -> Catalogo:
    """Remove alguns itens da compra planejada: marca os ids em
    Catalogo.itens_esquecidos, que as TRES estrategias respeitam — os
    baselines (S4-02/03) pulam o item na compra habitual, e o solver nao
    pode compra-lo (variaveis.criar_variaveis fixa b = 0).

    O preco NAO muda. Ate o Sprint 6 o solver era impedido de comprar com
    um preco x1000 — e esse mesmo preco valorava o descarte do estoque
    inicial do item, inflando o desperdicio de todas as estrategias (88%
    do desperdicio medido era esse artefato; ver docs/resultados.md).
    """
    if cenario.itens_esquecidos <= 0 or not catalogo.ingredientes:
        return catalogo
    rng = random.Random(cenario.semente + 4)
    candidatos = sorted(catalogo.ingredientes)
    quantidade = min(cenario.itens_esquecidos, len(candidatos))
    esquecidos = rng.sample(candidatos, quantidade)
    return replace(
        catalogo,
        itens_esquecidos=catalogo.itens_esquecidos | frozenset(esquecidos),
    )


def estragar_antes(catalogo: Catalogo, cenario: Cenario) -> Catalogo:
    """Reduz o dia de vencimento de alguns lotes — testa se R10/o
    desperdicio reagem a uma validade pior que a esperada."""
    if cenario.estragou_antes <= 0 or not catalogo.lotes:
        return catalogo
    rng = random.Random(cenario.semente + 5)
    candidatos = sorted(catalogo.lotes)
    quantidade = min(cenario.estragou_antes, len(candidatos))
    afetados = rng.sample(candidatos, quantidade)

    lotes = dict(catalogo.lotes)
    for lote_id in afetados:
        lote_atual = lotes[lote_id]
        reducao = rng.randint(1, max(1, lote_atual.dia_vencimento // 2) or 1)
        lotes[lote_id] = replace(
            lote_atual, dia_vencimento=max(0, lote_atual.dia_vencimento - reducao)
        )
    return replace(catalogo, lotes=lotes)


def aplicar_cenario(
    catalogo: Catalogo, parametros: Parametros, cenario: Cenario
) -> tuple[Catalogo, Parametros]:
    """Aplica as cinco perturbacoes em sequencia, sempre sobre catalogos
    NOVOS (nenhuma delas muta o `catalogo` original recebido)."""
    catalogo_perturbado = catalogo
    for perturbacao in (
        perturbar_precos,
        adicionar_visita,
        pular_refeicoes,
        esquecer_itens,
        estragar_antes,
    ):
        catalogo_perturbado = perturbacao(catalogo_perturbado, cenario)
    return catalogo_perturbado, parametros
