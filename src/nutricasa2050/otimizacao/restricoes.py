"""As restricoes do modelo (ver docs/formulacao.md, Secao 5).

Convencao: toda funcao rNN_* recebe (problema, variaveis, catalogo,
parametros), nao devolve nada, e adiciona as regras dentro de `problema`.
Isso deixa `otimizacao/modelo.py` como uma lista limpa de chamadas.
"""
from __future__ import annotations

from dataclasses import replace

from pulp import LpAffineExpression, LpProblem, lpSum

from nutricasa2050.dominio import Catalogo, Lote, Membro, Parametros
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


def r4_variedade(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Duas partes: (1) nenhuma receita aparece mais de 2 vezes na
    semana inteira (soma de x sobre todos os dias e refeicoes <= 2); (2)
    nenhuma receita aparece em dois dias consecutivos na mesma refeicao
    (x do dia + x do dia seguinte <= 1).

    (b) Se sair: nada impede o solver de repetir a receita mais barata
    (ou a de menor desvio) todos os dias — matematicamente otimo, mas
    ningue aguenta comer a mesma coisa sete dias seguidos. E o exemplo
    classico de que bom senso humano tambem e modelagem.
    """
    dias = parametros.dias
    for receita_id in catalogo.receitas:
        problema += (
            lpSum(
                variaveis.x[(receita_id, dia, refeicao)]
                for dia in dias
                for refeicao in parametros.refeicoes
            )
            <= 2,
            f"R4_max_duas_vezes_{receita_id}",
        )
        for dia, dia_seguinte in zip(dias, dias[1:], strict=False):
            for refeicao in parametros.refeicoes:
                problema += (
                    variaveis.x[(receita_id, dia, refeicao)]
                    + variaveis.x[(receita_id, dia_seguinte, refeicao)]
                    <= 1,
                    f"R4_nao_consecutivo_{receita_id}_{dia}_{refeicao}",
                )


def r6_restricao_alimentar_individual(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada membro, cada receita que ele NAO pode comer (segundo
    Membro.pode_comer), e cada dia/refeicao: a fracao servida aquele
    membro daquela receita e ZERO. Note a diferenca de filtrar o
    catalogo: a receita continua podendo ser cozinhada (x) e servida
    para os OUTROS membros — so aquele membro fica de fora.

    (b) Se sair: um membro com restricao (ex.: celiaco) poderia ser
    "servido" uma fracao de uma receita com gluten so porque ela foi
    escolhida para o resto da familia — quebra a restricao alimentar na
    pratica, mesmo que o catalogo soubesse da tag.
    """
    for membro_id, membro in catalogo.membros.items():
        for receita_id, receita in catalogo.receitas.items():
            if membro.pode_comer(receita):
                continue
            for dia in parametros.dias:
                for refeicao in parametros.refeicoes:
                    problema += (
                        variaveis.y[(membro_id, receita_id, dia, refeicao)] == 0,
                        f"R6_restricao_alimentar_{membro_id}_{receita_id}_{dia}_{refeicao}",
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
    """Quanto chega no lote `lote` no dia `dia`.

    Um lote so recebe chegada se ele FOR o lote de compra daquele dia
    exato (lote.dia_compra == dia) — um lote de estoque inicial
    (dia_compra=None) nunca recebe nada, e um lote de compra de outro
    dia tambem nao (S3-01, item 3). Sem essa checagem, com mais de um
    lote por ingrediente (estoque inicial + varios lotes de compra), a
    MESMA compra seria creditada em todos eles ao mesmo tempo —
    duplicando comida que nunca existiu.
    """
    if lote.dia_compra != dia:
        return 0.0

    chave = (lote.ingrediente_id, dia)
    if chave not in variaveis.b:
        return 0.0

    ingrediente = catalogo.ingredientes[lote.ingrediente_id]
    return ingrediente.tamanho_embalagem * variaveis.b[chave]


def criar_lotes_de_compra(catalogo: Catalogo, parametros: Parametros) -> list[Lote]:
    """Um lote novo para cada par (ingrediente, dia de compra), vencendo em
    (dia da compra + validade tipica do ingrediente). Comecam com
    quantidade 0.0 porque nao existe nada neles até o dia da compra
    chegar — e `chegada_do_lote` quem credita o que foi comprado.
    """
    return [
        Lote(
            id=f"compra_{ingrediente_id}_{dia}",
            ingrediente_id=ingrediente_id,
            quantidade=0.0,
            dia_vencimento=dia + ingrediente.validade_dias,
            dia_compra=dia,
        )
        for ingrediente_id, ingrediente in catalogo.ingredientes.items()
        for dia in parametros.dias_compra
    ]


def preparar_catalogo(catalogo: Catalogo, parametros: Parametros) -> Catalogo:
    """Devolve uma copia do catalogo com os lotes de compra (S3-01) juntados
    aos de estoque inicial — "esses lotes entram no modelo junto com os do
    estoque inicial", como diz o card.

    E pura e deterministica: chamar de novo com o mesmo (catalogo,
    parametros) sempre gera os mesmos ids de lote. Por isso
    `modelo.construir`, `solver.resolver`, `serializacao.resultado_para_dict`
    e `objetivo.descrever_objetivo` podem cada um chamar isso por conta
    propria sem se preocupar em repassar o catalogo "expandido" de um para
    o outro — todos chegam no mesmo resultado.
    """
    lotes_de_compra = {lote.id: lote for lote in criar_lotes_de_compra(catalogo, parametros)}
    return replace(catalogo, lotes={**catalogo.lotes, **lotes_de_compra})


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


def _total_nutriente(
    variaveis: Variaveis,
    catalogo: Catalogo,
    parametros: Parametros,
    membro_id: str,
    membro: Membro,
    nutriente: str,
) -> dict[int, LpAffineExpression]:
    """O total daquele nutriente entregue aquele membro, por dia — soma
    sobre receitas e refeicoes de (nutriente da receita) x (fator de
    porcao do membro) x (fracao servida). Compartilhado por R5 e R7
    (S3-06) para as duas restricoes nunca discordarem sobre o que "total
    entregue" significa.
    """
    return {
        dia: lpSum(
            catalogo.nutriente(receita_id, nutriente)
            * membro.fator_porcao
            * variaveis.y[(membro_id, receita_id, dia, refeicao)]
            for receita_id in catalogo.receitas
            for refeicao in parametros.refeicoes
        )
        for dia in parametros.dias
    }


def r5_faixas_nutricionais(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada nutriente, cada membro e cada dia, o total entregue
    fica entre (minimo - folga_falta) e (maximo + folga_sobra), em vez de
    exigir minimo/maximo direto (S3-06). As variaveis de folga sao
    sempre >= 0, entram no objetivo com peso bem alto (Pesos.folga), e so
    o solver usa quando NAO existe jeito de fechar a faixa de verdade.

    (b) Se sair: o modelo nao teria nenhuma garantia de que o cardapio
    alimenta adequadamente cada pessoa — poderia escolher so pelo custo e
    deixar alguem subnutrido ou com excesso calorico. Sem a folga
    especificamente (so a faixa rigida do S2-06), qualquer cenario onde
    nao existe cardapio que feche a faixa de alguem (ex.: familia de 4
    com restricoes individuais) vira Infeasible em vez de "a melhor
    resposta possivel, com um aviso de onde precisou ceder".
    """
    for membro_id, membro in catalogo.membros.items():
        for nutriente, faixa in membro.faixas.items():
            total_por_dia = _total_nutriente(
                variaveis, catalogo, parametros, membro_id, membro, nutriente
            )
            for dia, total in total_por_dia.items():
                chave = (nutriente, membro_id, dia)
                problema += (
                    total >= faixa.minimo - variaveis.folga_falta[chave],
                    f"R5_minimo_{nutriente}_{membro_id}_{dia}",
                )
                problema += (
                    total <= faixa.maximo + variaveis.folga_sobra[chave],
                    f"R5_maximo_{nutriente}_{membro_id}_{dia}",
                )


def r7_desvio_do_alvo(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada nutriente, membro e dia: (total entregue - alvo) e
    IGUAL a (desvio_acima - desvio_abaixo), as duas nao-negativas. Como o
    objetivo minimiza a soma das duas, so uma fica positiva por vez — a
    linearizacao padrao de modulo em programacao linear (|total - alvo|
    nao e linear; essa troca de variaveis e). Citar isso na banca.

    (b) Se sair: o modelo saberia se esta DENTRO da faixa (R5), mas nao
    teria como medir distancia do alvo prescrito — duas solucoes nos
    extremos opostos da mesma faixa pareceriam igualmente boas, quando
    na pratica uma esta bem mais perto do que foi prescrito.
    """
    for membro_id, membro in catalogo.membros.items():
        for nutriente, faixa in membro.faixas.items():
            total_por_dia = _total_nutriente(
                variaveis, catalogo, parametros, membro_id, membro, nutriente
            )
            for dia, total in total_por_dia.items():
                chave = (nutriente, membro_id, dia)
                problema += (
                    total - faixa.alvo
                    == variaveis.desvio_acima[chave] - variaveis.desvio_abaixo[chave],
                    f"R7_desvio_{nutriente}_{membro_id}_{dia}",
                )


def r10_validade_por_lote(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada lote e cada dia: se o dia e DEPOIS do vencimento, o
    consumo daquele lote naquele dia e zero (nao dá para comer o que já
    venceu); se o dia e IGUAL OU DEPOIS do vencimento, o estoque restante
    daquele lote e zero (nao pode sobrar lote vencido — tem que ter sido
    consumido ou descartado até o dia do vencimento, inclusive).

    (b) Se sair: o modelo poderia empurrar o consumo de um ingrediente
    para depois do seu vencimento como se nada tivesse acontecido — nao
    haveria pressao nenhuma para usar primeiro o que vence primeiro (o
    "coracao" do projeto, card S3-08, simplesmente nao aconteceria).
    """
    for lote in catalogo.lotes.values():
        for dia in parametros.dias:
            if dia > lote.dia_vencimento:
                problema += (
                    variaveis.u[(lote.id, dia)] == 0,
                    f"R10_consumo_pos_vencimento_{lote.id}_{dia}",
                )
            if dia >= lote.dia_vencimento:
                problema += (
                    variaveis.s[(lote.id, dia)] == 0,
                    f"R10_estoque_pos_vencimento_{lote.id}_{dia}",
                )


def r11_tempo_de_preparo(
    problema: LpProblem, variaveis: Variaveis, catalogo: Catalogo, parametros: Parametros
) -> None:
    """(a) Para cada dia, a soma do tempo de preparo dos pratos cozinhados
    naquele dia e menor ou igual ao tempo disponivel do dia
    (parametros.tempo_por_dia). Quando tempo_por_dia e infinito (padrao),
    a restricao e vazia por definicao e nem e adicionada — um teto
    infinito no PuLP/CBC e um jeito garantido de dar problema numerico
    por nada.

    (b) Se sair: o modelo poderia escalar uma receita de duas horas numa
    terca-feira corrida, porque nada mede quanto tempo de cozinha aquele
    dia realmente tem disponivel.
    """
    if parametros.tempo_por_dia == float("inf"):
        return

    for dia in parametros.dias:
        tempo_do_dia = lpSum(
            catalogo.receitas[receita_id].tempo_min * variaveis.x[(receita_id, dia, refeicao)]
            for receita_id in catalogo.receitas
            for refeicao in parametros.refeicoes
        )
        problema += (tempo_do_dia <= parametros.tempo_por_dia, f"R11_tempo_de_preparo_{dia}")


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
