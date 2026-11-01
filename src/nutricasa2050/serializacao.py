"""Transforma uma Solucao num dicionario Python simples (so tipos basicos:
texto, numero, lista, dicionario). E o formato unico que a tela, o banco e
os graficos vao usar — ninguem le direto dos dicionarios indexados por
tupla do solver.py.
"""
from __future__ import annotations

from collections import defaultdict

from nutricasa2050.dominio import Catalogo, Parametros, Solucao
from nutricasa2050.otimizacao.restricoes import preparar_catalogo


def _cardapio(solucao: Solucao, catalogo: Catalogo) -> list[dict]:
    resultado = []
    for (receita_id, dia, refeicao), fracao in solucao.cardapio.items():
        resultado.append(
            {
                "dia": dia,
                "refeicao": refeicao,
                "receita_id": receita_id,
                "receita_nome": catalogo.receitas[receita_id].nome,
                # R10 (FEFO, S3-01) ja existe no modelo, mas aqui so
                # sabemos QUANTO foi cozinhado (x), nao de qual lote veio
                # cada grama consumida (R8 so soma por ingrediente). Marcar
                # isso com confianca exigiria rastrear lote por receita, o
                # que nenhum card do Sprint 3 pede — o comportamento
                # anti-desperdicio aparece no CARDAPIO em si (S3-08), nao
                # numa flag por prato.
                "puxado_por_validade": False,
                "preparado": fracao > 0,
            }
        )
    return resultado


def _porcoes(solucao: Solucao) -> list[dict]:
    return [
        {
            "membro_id": membro_id,
            "dia": dia,
            "refeicao": refeicao,
            "receita_id": receita_id,
            "fracao": fracao,
        }
        for (membro_id, receita_id, dia, refeicao), fracao in solucao.porcoes.items()
    ]


def _compras(solucao: Solucao, catalogo: Catalogo) -> list[dict]:
    resultado = []
    for (ingrediente_id, dia), embalagens in solucao.compras.items():
        ingrediente = catalogo.ingredientes[ingrediente_id]
        resultado.append(
            {
                "ingrediente_id": ingrediente_id,
                "ingrediente_nome": ingrediente.nome,
                "dia": dia,
                "embalagens": embalagens,
                "quantidade": embalagens * ingrediente.tamanho_embalagem,
                "unidade": ingrediente.unidade,
                "custo": embalagens * ingrediente.preco_embalagem,
            }
        )
    return resultado


def _descartes(solucao: Solucao, catalogo: Catalogo) -> list[dict]:
    resultado = []
    for (lote_id, dia), quantidade in solucao.descartes.items():
        lote = catalogo.lotes[lote_id]
        ingrediente = catalogo.ingredientes[lote.ingrediente_id]
        resultado.append(
            {
                "lote_id": lote_id,
                "ingrediente_id": lote.ingrediente_id,
                "dia": dia,
                "quantidade": quantidade,
                "valor": quantidade * ingrediente.preco_unitario,
            }
        )
    return resultado


def _estoque(solucao: Solucao, catalogo: Catalogo) -> list[dict]:
    """A despensa dia a dia: quanto resta de cada lote, e quantos dias
    faltam para vencer A PARTIR daquele dia — e o que a tela (S5-05)
    usa para colorir as barras pela proximidade do vencimento.
    """
    resultado = []
    for (lote_id, dia), quantidade in solucao.estoque.items():
        lote = catalogo.lotes[lote_id]
        ingrediente = catalogo.ingredientes[lote.ingrediente_id]
        resultado.append(
            {
                "lote_id": lote_id,
                "ingrediente_id": lote.ingrediente_id,
                "ingrediente_nome": ingrediente.nome,
                "dia": dia,
                "quantidade": quantidade,
                "dia_vencimento": lote.dia_vencimento,
                "dias_restantes": lote.dia_vencimento - dia,
            }
        )
    return resultado


def _aderencia(solucao: Solucao, catalogo: Catalogo, parametros: Parametros) -> list[dict]:
    """"valor" vem das porcoes realizadas (nao e uma variavel de decisao em
    si). "desvio" e "folga" vem das variaveis de R7/R5 (S3-06) —
    desvio_acima/desvio_abaixo e folga_falta/folga_sobra — porque sao elas
    que o solver de fato decidiu usar, e nao uma distancia recalculada por
    fora que poderia dar numero negativo se a faixa tivesse sido violada.
    """
    consumo: dict[tuple[str, str, int], float] = defaultdict(float)
    for (membro_id, receita_id, dia, refeicao), fracao in solucao.porcoes.items():
        membro = catalogo.membros[membro_id]
        for nutriente in membro.faixas:
            valor_receita = catalogo.nutriente(receita_id, nutriente)
            if valor_receita:
                consumo[(membro_id, nutriente, dia)] += valor_receita * membro.fator_porcao * fracao

    resultado = []
    for membro_id, membro in catalogo.membros.items():
        for nutriente, faixa in membro.faixas.items():
            for dia in parametros.dias:
                valor = consumo.get((membro_id, nutriente, dia), 0.0)
                chave = (nutriente, membro_id, dia)
                desvio_acima = solucao.aderencia["desvio_acima"].get(chave, 0.0)
                desvio_abaixo = solucao.aderencia["desvio_abaixo"].get(chave, 0.0)
                folga_falta = solucao.aderencia["folga_falta"].get(chave, 0.0)
                folga_sobra = solucao.aderencia["folga_sobra"].get(chave, 0.0)
                resultado.append(
                    {
                        "membro_id": membro_id,
                        "dia": dia,
                        "nutriente": nutriente,
                        "valor": valor,
                        "minimo": faixa.minimo,
                        "maximo": faixa.maximo,
                        "alvo": faixa.alvo,
                        "desvio": desvio_acima - desvio_abaixo,
                        "folga": folga_falta + folga_sobra,
                    }
                )
    return resultado


def resultado_para_dict(solucao: Solucao, catalogo: Catalogo, parametros: Parametros) -> dict:
    # preparar_catalogo e pura/deterministica (ver seu docstring): chamar
    # de novo aqui garante que os ids de lote de compra em
    # solucao.descartes (ex.: "compra_arroz_2") existam no catalogo usado
    # para serializar, mesmo que o chamador tenha passado o catalogo
    # original sem os lotes de compra.
    catalogo = preparar_catalogo(catalogo, parametros)
    cardapio = _cardapio(solucao, catalogo)
    porcoes = _porcoes(solucao)
    compras = _compras(solucao, catalogo)
    descartes = _descartes(solucao, catalogo)
    estoque = _estoque(solucao, catalogo)
    aderencia = _aderencia(solucao, catalogo, parametros)

    resumo = {
        "status": solucao.status,
        "tempo_segundos": solucao.tempo_segundos,
        "custo_total": sum(item["custo"] for item in compras),
        "valor_desperdicio": sum(item["valor"] for item in descartes),
        "tempo_cozinha_minutos": sum(
            catalogo.receitas[item["receita_id"]].tempo_min for item in cardapio
        ),
        "folga_total": sum(item["folga"] for item in aderencia),
    }

    return {
        "resumo": resumo,
        "cardapio": cardapio,
        "porcoes": porcoes,
        "compras": compras,
        "descartes": descartes,
        "estoque": estoque,
        "aderencia": aderencia,
    }
