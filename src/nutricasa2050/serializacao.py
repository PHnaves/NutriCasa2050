"""Transforma uma Solucao num dicionario Python simples (so tipos basicos:
texto, numero, lista, dicionario). E o formato unico que a tela, o banco e
os graficos vao usar — ninguem le direto dos dicionarios indexados por
tupla do solver.py.
"""
from __future__ import annotations

from collections import defaultdict

from nutricasa2050.dominio import Catalogo, Parametros, Solucao


def _cardapio(solucao: Solucao, catalogo: Catalogo) -> list[dict]:
    resultado = []
    for (receita_id, dia, refeicao), fracao in solucao.cardapio.items():
        resultado.append(
            {
                "dia": dia,
                "refeicao": refeicao,
                "receita_id": receita_id,
                "receita_nome": catalogo.receitas[receita_id].nome,
                # R10 (FEFO) ainda nao existe (card S3-xx) — por enquanto
                # nenhum prato e "puxado por validade".
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


def _aderencia(solucao: Solucao, catalogo: Catalogo, parametros: Parametros) -> list[dict]:
    """Calculada direto das porcoes realizadas (nao depende das variaveis de
    folga/desvio do R7, que so entram no S3-06) — por isso ja faz sentido
    mesmo nesta fase do projeto.
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
                resultado.append(
                    {
                        "membro_id": membro_id,
                        "dia": dia,
                        "nutriente": nutriente,
                        "valor": valor,
                        "minimo": faixa.minimo,
                        "maximo": faixa.maximo,
                        "alvo": faixa.alvo,
                        "desvio": valor - faixa.alvo,
                        "folga": min(faixa.maximo - valor, valor - faixa.minimo),
                    }
                )
    return resultado


def resultado_para_dict(solucao: Solucao, catalogo: Catalogo, parametros: Parametros) -> dict:
    cardapio = _cardapio(solucao, catalogo)
    porcoes = _porcoes(solucao)
    compras = _compras(solucao, catalogo)
    descartes = _descartes(solucao, catalogo)
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
        "aderencia": aderencia,
    }
