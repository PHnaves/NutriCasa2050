"""Preco-sombra (card S5-01): quanto o resultado MELHORARIA se uma regra
afrouxasse em uma unidade. E uma derivada — a taxa de variacao do
objetivo em relacao ao limite da restricao.

ACHADO IMPORTANTE, antes de ler o resto deste arquivo: o card assume que
"o solver calcula isso de graca quando resolve" — verdade para um LP
puro (LpConstraint.pi depois de resolver), mas o NOSSO modelo tem
variaveis binarias (x) e inteiras (b). Testei na mao: ate uma restricao
genuinamente BINDING (ex.: R12/orcamento com folga exatamente zero)
volta com `.pi == 0.0` quando ela depende de uma variavel inteira — o
dual de MIP via essa API simplesmente nao existe/nao e confiavel. Isso
NAO e um detalhe tecnico menor: e a diferenca entre o numero certo e um
zero sem sentido numa pergunta de banca.

A tecnica que funciona de verdade para MIP, e a que este arquivo usa:
resolver o modelo DUAS VEZES, com o limite da restricao perturbado em 1
unidade na segunda vez, e medir a diferenca no objetivo (diferenca
finita — a definicao literal de derivada que o card cita). Custa um
solve extra por numero que se quer, mas e sempre correto,
independentemente de quais variaveis sao inteiras.
"""
from __future__ import annotations

from dataclasses import replace

from pulp import LpProblem

from nutricasa2050.dominio import Catalogo, Parametros
from nutricasa2050.otimizacao.modelo import construir
from nutricasa2050.otimizacao.solver import resolver_problema


def extrair_precos_sombra(problema: LpProblem) -> dict[str, float]:
    """Le LpConstraint.pi de cada restricao do problema JA RESOLVIDO,
    indexado pelo nome dela — o que o card pede literalmente.

    AVISO: isso e sensibilidade de programacao linear PURA. So e
    confiavel se o problema resolvido nao tiver nenhuma variavel
    binaria/inteira ativa (ex.: depois de fixa-las, como
    preco_sombra_do_orcamento faz por fora). No MIP original, pode
    devolver 0.0 ate para restricoes binding — ver o docstring do
    modulo. Para um numero que SEMPRE significa algo, use
    preco_sombra_do_orcamento ou preco_sombra_por_membro_e_nutriente.
    """
    return {nome: restricao.pi for nome, restricao in problema.constraints.items()}


def _valor_objetivo(problema: LpProblem) -> float:
    valor = problema.objective.value()
    if valor is None:
        valor = float(problema.objective.constant)
    return valor


def preco_sombra_do_orcamento(catalogo: Catalogo, parametros: Parametros) -> float:
    """Quanto o objetivo melhoraria se o orcamento fosse R$ 1,00 maior
    por semana. Resolve o modelo duas vezes (ver aviso no topo do
    arquivo) — nunca positivo: dar mais dinheiro nunca pode PIORAR o
    resultado (dai o sinal: diferenca = depois - antes, e "melhorar"
    para uma minimizacao e diminuir).
    """
    problema_antes, _ = construir(catalogo, parametros)
    resolver_problema(problema_antes, parametros)
    valor_antes = _valor_objetivo(problema_antes)

    parametros_depois = replace(parametros, orcamento=parametros.orcamento + 1.0)
    problema_depois, _ = construir(catalogo, parametros_depois)
    resolver_problema(problema_depois, parametros_depois)
    valor_depois = _valor_objetivo(problema_depois)

    return valor_depois - valor_antes


def preco_sombra_por_membro_e_nutriente(
    catalogo: Catalogo,
    parametros: Parametros,
    membro_id: str | None = None,
    nutriente: str | None = None,
) -> dict[tuple[str, str, str], float]:
    """Preco-sombra de afrouxar o minimo (sobe 1 unidade o MINIMO exigido
    — testa o custo de EXIGIR mais) e o maximo (sobe 1 unidade o TETO
    permitido — testa o custo de UM LIMITE, como o sodio do idoso
    hipertenso) de cada faixa nutricional, uma restricao de cada vez.

    Custa 2 resolucoes extras por combinacao (membro, nutriente) — passe
    membro_id/nutriente para calcular so uma combinacao especifica
    (ex.: a pergunta do demo_afrouxar_sodio, S5-06) em vez de todas; com
    o catalogo real isso evita dezenas de resolucoes desnecessarias.
    """
    problema_base, _ = construir(catalogo, parametros)
    resolver_problema(problema_base, parametros)
    valor_base = _valor_objetivo(problema_base)

    combinacoes = [
        (m_id, nome)
        for m_id, membro in catalogo.membros.items()
        for nome in membro.faixas
        if (membro_id is None or m_id == membro_id) and (nutriente is None or nome == nutriente)
    ]

    resultado: dict[tuple[str, str, str], float] = {}
    for m_id, nome in combinacoes:
        membro = catalogo.membros[m_id]
        faixa = membro.faixas[nome]

        for lado, delta_minimo, delta_maximo in (("minimo", 1.0, 0.0), ("maximo", 0.0, 1.0)):
            faixa_perturbada = replace(
                faixa, minimo=faixa.minimo + delta_minimo, maximo=faixa.maximo + delta_maximo
            )
            membros_perturbados = {
                **catalogo.membros,
                m_id: replace(membro, faixas={**membro.faixas, nome: faixa_perturbada}),
            }
            catalogo_perturbado = replace(catalogo, membros=membros_perturbados)

            problema_perturbado, _ = construir(catalogo_perturbado, parametros)
            resolver_problema(problema_perturbado, parametros)
            valor_perturbado = _valor_objetivo(problema_perturbado)

            resultado[(m_id, nome, lado)] = valor_perturbado - valor_base

    return resultado


def interpretar_preco_sombra(nome: str, valor: float) -> str:
    """Devolve a FRASE em portugues — e ela que vai no slide, nao o
    numero cru."""
    if abs(valor) < 1e-9:
        return (
            f"'{nome}' nao esta apertando o resultado agora — afrouxar em 1 "
            "unidade mudaria R$ 0,00 no resultado da semana."
        )

    if "orcamento" in nome.lower() or "orçamento" in nome.lower():
        if valor < 0:
            return (
                f"Se o orcamento fosse R$ 1,00 maior por semana, o resultado "
                f"melhoraria R$ {abs(valor):.2f} na mesma semana."
            )
        return (
            f"Aumentar o orcamento em R$ 1,00 por semana pioraria o resultado "
            f"em R$ {valor:.2f} nessa semana — sinal inesperado, revise o modelo."
        )

    direcao = "melhoraria" if valor < 0 else "pioraria"
    return (
        f"Afrouxar '{nome}' em 1 unidade {direcao} o resultado em "
        f"R$ {abs(valor):.2f} por semana."
    )
