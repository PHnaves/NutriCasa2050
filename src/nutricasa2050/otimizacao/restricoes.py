"""As restricoes do modelo (ver docs/formulacao.md, Secao 5).

Convencao: toda funcao rNN_* recebe (problema, variaveis, catalogo,
parametros), nao devolve nada, e adiciona as regras dentro de `problema`.
Isso deixa `otimizacao/modelo.py` como uma lista limpa de chamadas.
"""
from __future__ import annotations

from pulp import LpAffineExpression, LpProblem, lpSum

from nutricasa2050.dominio import Catalogo, Lote, Parametros
from nutricasa2050.otimizacao.variaveis import Variaveis


def r1_cobertura(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada membro, dia e refeicao, a soma das fracoes que ele
    recebe de todos os pratos e EXATAMENTE 1 — ninguem fica sem comer e
    ninguem come porcao dupla.

    (b) Se sair: a soma poderia ficar em zero sempre que qualquer prato
    custasse mais que zero, e a solucao "mais barata" seria a familia nao
    comer — o que esvazia a funcao objetivo como medida de custo de vida.
    """
    for membro_id in catalogo.membros:
        for dia in parametros.dias:
            for refeicao in parametros.refeicoes:
                problema += (
                    lpSum(
                        variaveis.y[(membro_id, receita_id, dia, refeicao)]
                        for receita_id in catalogo.receitas
                    )
                    == 1,
                    f"R1_cobertura_{membro_id}_{dia}_{refeicao}",
                )


def r2_vinculo(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada membro, prato, dia e refeicao, a fracao servida e MENOR
    OU IGUAL a variavel que diz se o prato foi preparado — se o prato nao
    foi cozinhado, ninguem come dele.

    (b) Se sair: o modelo poderia "alimentar" alguem com um prato que nunca
    entrou no cardapio, quebrando a ligacao causal entre o que foi cozinhado
    (x) e o que foi comido (y) — custo e nutricao deixariam de corresponder
    a qualquer cardapio real.
    """
    for membro_id in catalogo.membros:
        for receita_id in catalogo.receitas:
            for dia in parametros.dias:
                for refeicao in parametros.refeicoes:
                    problema += (
                        variaveis.y[(membro_id, receita_id, dia, refeicao)]
                        <= variaveis.x[(receita_id, dia, refeicao)],
                        f"R2_vinculo_{membro_id}_{receita_id}_{dia}_{refeicao}",
                    )


def r3_limite_de_pratos(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada dia e refeicao, o numero de pratos preparados e menor
    ou igual ao limite (2, por padrao) — a restricao mais importante do
    projeto, porque obriga o solver a achar pratos que sirvam varias pessoas
    ao mesmo tempo.

    (b) Se sair: o solver prepara um prato sob medida para cada pessoa em
    cada refeicao — tecnicamente viavel, mas elimina o problema de
    portfolio que torna o projeto interessante (vira N problemas de dieta
    independentes, nao um problema de familia).
    """
    for dia in parametros.dias:
        for refeicao in parametros.refeicoes:
            problema += (
                lpSum(
                    variaveis.x[(receita_id, dia, refeicao)] for receita_id in catalogo.receitas
                )
                <= parametros.pratos_por_refeicao,
                f"R3_limite_de_pratos_{dia}_{refeicao}",
            )


def r8_consumo_derivado(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada ingrediente e cada dia, a soma do consumo de todos os
    lotes daquele ingrediente e igual a soma, sobre receitas, membros e
    refeicoes, de (quantidade na receita) x (fator de porcao do membro) x
    (fracao servida) — a ponte entre o cardapio/porcao (demanda) e o
    estoque/lote (oferta).

    (b) Se sair: nao haveria elo matematico entre o que a familia "pede"
    para comer e o que precisa existir na despensa — o cardapio poderia
    usar ingredientes que nunca foram comprados.
    """
    for ingrediente_id in catalogo.ingredientes:
        for dia in parametros.dias:
            lado_esquerdo_dia = lpSum(
                variaveis.u[(lote.id, dia)]
                for lote in catalogo.lotes_do_ingrediente(ingrediente_id)
            )
            lado_direito_dia = lpSum(
                catalogo.quantidade(receita_id, ingrediente_id)
                * catalogo.membros[membro_id].fator_porcao
                * variaveis.y[(membro_id, receita_id, dia, refeicao)]
                for receita_id in catalogo.receitas_com_ingrediente(ingrediente_id)
                for membro_id in catalogo.membros
                for refeicao in parametros.refeicoes
            )
            problema += (
                lado_esquerdo_dia == lado_direito_dia,
                f"R8_consumo_derivado_{ingrediente_id}_{dia}",
            )


def chegada_do_lote(
    lote: Lote, dia: int, variaveis: Variaveis, catalogo: Catalogo
) -> LpAffineExpression | float:
    """Quanto chega no lote `lote` no dia `dia`. Para um lote inicial, so e
    diferente de zero se aquele ingrediente tiver uma compra programada
    para esse dia (variaveis.b so existe para os dias de parametros.dias_compra
    — isso evita precisar passar `parametros` aqui tambem). Isolar essa
    logica num lugar so e o que vai permitir o S3-01 lidar com reposicao em
    varios dias sem reescrever R9.
    """
    chave = (lote.ingrediente_id, dia)
    if chave not in variaveis.b:
        return 0.0

    ingrediente = catalogo.ingredientes[lote.ingrediente_id]
    return ingrediente.tamanho_embalagem * variaveis.b[chave]


def r9_balanco_de_estoque(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada lote e cada dia: o que resta hoje = o que restava
    ontem + o que chegou hoje - o que foi consumido - o que foi descartado.
    No primeiro dia do horizonte, "o que restava ontem" e a quantidade
    inicial do lote. E a equacao que amarra os dias do horizonte num
    sistema so — sem ela, a sobra de um dia nao teria como ser usada no
    dia seguinte.

    (b) Se sair: o solver consumiria ingredientes "no ar", sem respeitar
    lotes individuais nem o que realmente havia em estoque — poderia
    inclusive "inventar" comida que nunca existiu na despensa.
    """
    dias = parametros.dias
    for lote in catalogo.lotes.values():
        for indice, dia in enumerate(dias):
            estoque_anterior = (
                lote.quantidade if indice == 0 else variaveis.s[(lote.id, dias[indice - 1])]
            )
            chegada = chegada_do_lote(lote, dia, variaveis, catalogo)
            consumido = variaveis.u[(lote.id, dia)]
            descartado = variaveis.w[(lote.id, dia)]
            problema += (
                variaveis.s[(lote.id, dia)] == estoque_anterior + chegada - consumido - descartado,
                f"R9_balanco_de_estoque_{lote.id}_{dia}",
            )


def r5_faixas_nutricionais(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada nutriente, cada membro e cada dia, o total entregue
    (soma sobre receitas e refeicoes de nutriente da receita x fator de
    porcao do membro x fracao servida) fica entre o minimo e o maximo da
    faixa daquele membro. Nesta versao, sem folga (ela entra no S3-06).

    (b) Se sair: o modelo nao teria nenhuma garantia de que o cardapio
    alimenta adequadamente cada pessoa — poderia escolher so pelo custo e
    deixar alguem subnutrido ou com excesso calorico.
    """
    for membro_id, membro in catalogo.membros.items():
        for nutriente, faixa in membro.faixas.items():
            for dia in parametros.dias:
                total = lpSum(
                    catalogo.nutriente(receita_id, nutriente)
                    * membro.fator_porcao
                    * variaveis.y[(membro_id, receita_id, dia, refeicao)]
                    for receita_id in catalogo.receitas
                    for refeicao in parametros.refeicoes
                )
                problema += (
                    total >= faixa.minimo,
                    f"R5_minimo_{nutriente}_{membro_id}_{dia}",
                )
                problema += (
                    total <= faixa.maximo,
                    f"R5_maximo_{nutriente}_{membro_id}_{dia}",
                )


def r12_orcamento(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) A soma, sobre todos os ingredientes e dias de compra, de (preco
    da embalagem) x (embalagens compradas) e menor ou igual ao orcamento.

    (b) Se sair: o modelo minimizaria desperdicio e desvio nutricional sem
    nenhum freio de gasto, o que descaracteriza o problema como um problema
    real de economia domestica.
    """
    custo_total = lpSum(
        catalogo.ingredientes[ingrediente_id].preco_embalagem * variaveis.b[(ingrediente_id, dia)]
        for ingrediente_id in catalogo.ingredientes
        for dia in parametros.dias_compra
    )
    problema += (custo_total <= parametros.orcamento, "R12_orcamento")
