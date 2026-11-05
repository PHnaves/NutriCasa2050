"""Os cinco botoes de demonstracao (card S5-06) — cada um recebe o
estado atual e devolve catalogo/parametros MODIFICADOS. O teste mais
importante é o ultimo: se um botao der Infeasible na feira, a
demonstracao morre na frente do visitante.
"""
from __future__ import annotations

import pytest
from apoio_catalogo import construir_catalogo, ingrediente, lote, membro, receita

from app import (
    demo_afrouxar_sodio,
    demo_chegou_visita,
    demo_filho_celiaco,
    demo_ninguem_jantou,
    demo_orcamento_reduzido,
)
from nutricasa2050.dados.carga import carregar_catalogo
from nutricasa2050.dominio import Faixa, Parametros
from nutricasa2050.otimizacao.solver import resolver


def _catalogo_familia():
    return construir_catalogo(
        ingredientes=[ingrediente("1", "Arroz", preco_embalagem=6.0, tamanho_embalagem=1.0)],
        receitas=[receita("r1", tags=frozenset({"gluten"})), receita("r2")],
        matriz_a={("r1", "1"): 0.2, ("r2", "1"): 0.2},
        membros=[
            membro("adulto", fator_porcao=1.0),
            membro(
                "crianca_8_anos",
                fator_porcao=0.6,
                faixas={"sodio_mg": Faixa(minimo=0, maximo=1000, alvo=500)},
            ),
            membro("idoso_hipertenso", faixas={"sodio_mg": Faixa(minimo=0, maximo=1200, alvo=600)}),
        ],
    )


def test_demo_celiaco_bloqueia_so_a_crianca() -> None:
    catalogo = _catalogo_familia()

    catalogo_depois = demo_filho_celiaco(catalogo, "crianca_8_anos")

    assert "sem_gluten" in catalogo_depois.membros["crianca_8_anos"].tags_exigidas
    assert "sem_gluten" not in catalogo_depois.membros["adulto"].tags_exigidas
    assert "sem_gluten" not in catalogo_depois.membros["idoso_hipertenso"].tags_exigidas


def test_celiaco_so_come_receita_marcada_sem_gluten() -> None:
    """Regressao (Sprint 6): "sem_gluten" nos dados significa que a receita
    NAO tem gluten. O botao bloqueava essa tag, ou seja, proibia a crianca
    de comer exatamente os pratos seguros — e o modelo ficava inviavel."""
    catalogo = demo_filho_celiaco(carregar_catalogo(), "crianca_8_anos")
    crianca = catalogo.membros["crianca_8_anos"]
    adulto = catalogo.membros["adulto_ativo"]

    sem_gluten = catalogo.receitas["arroz_feijao_ovo"]  # vegetariano;sem_gluten;sem_lactose
    com_gluten = catalogo.receitas["sanduiche_quente_queijo_tomate"]  # so vegetariano

    assert crianca.pode_comer(sem_gluten)
    assert not crianca.pode_comer(com_gluten)
    assert adulto.pode_comer(com_gluten)


def test_demo_orcamento_corta_trinta_por_cento() -> None:
    parametros = Parametros(horizonte=7, refeicoes_por_dia=3, orcamento=300.0)

    parametros_depois = demo_orcamento_reduzido(parametros)

    assert parametros_depois.orcamento == pytest.approx(210.0)


def test_demo_visita_aumenta_membros_em_um_dia() -> None:
    catalogo = _catalogo_familia()

    catalogo_depois = demo_chegou_visita(catalogo)

    assert len(catalogo_depois.membros) == len(catalogo.membros) + 1


def test_demo_ninguem_jantou_devolve_ingredientes_ao_estoque() -> None:
    """Depois do demo, o solver nao consome nada naquela refeicao — o
    estoque daquele dia fica mais alto do que ficaria se a refeicao
    tivesse acontecido (nada "gasto" precisa ser "devolvido": ela
    simplesmente nunca e consumida)."""
    catalogo = construir_catalogo(
        ingredientes=[ingrediente("1", "Arroz", tamanho_embalagem=1.0)],
        receitas=[receita("r1")],
        matriz_a={("r1", "1"): 1.0},
        lotes=[lote("L1", "1", quantidade=10.0, dia_vencimento=30)],
        membros=[membro("p1", fator_porcao=1.0)],
    )
    parametros = Parametros(
        horizonte=1, refeicoes_por_dia=1, pratos_por_refeicao=1, orcamento=0.0, dias_compra=()
    )

    dia, refeicao = parametros.dias[0], parametros.refeicoes[0]

    solucao_normal = resolver(catalogo, parametros)
    consumo_normal = solucao_normal.estoque.get(("L1", dia), 10.0)

    catalogo_sem_jantar = demo_ninguem_jantou(catalogo, dia=dia, refeicao=refeicao)
    solucao_sem_jantar = resolver(catalogo_sem_jantar, parametros)
    estoque_sem_jantar = solucao_sem_jantar.estoque.get(("L1", dia), 0.0)

    assert estoque_sem_jantar > consumo_normal


def test_demo_afrouxar_sodio_sobe_o_teto() -> None:
    catalogo = _catalogo_familia()

    catalogo_depois = demo_afrouxar_sodio(catalogo, "idoso_hipertenso", incremento=500.0)

    faixa_antes = catalogo.membros["idoso_hipertenso"].faixas["sodio_mg"]
    faixa_depois = catalogo_depois.membros["idoso_hipertenso"].faixas["sodio_mg"]
    assert faixa_depois.maximo == faixa_antes.maximo + 500.0


@pytest.mark.lento
def test_todos_os_cinco_cenarios_sao_viaveis() -> None:
    """TESTE IMPORTANTE: se um botao der Infeasible na feira, a
    demonstracao morre na frente do visitante. Catalogo real e OS MESMOS
    parametros padrao do app (5 dias, R$ 500) — com horizonte 3 o bug do
    celiaco (Sprint 6) passava despercebido. Exige cardapio nao vazio:
    "Not Solved" sem solucao inteira tambem mata a demo."""
    catalogo_base = carregar_catalogo()
    parametros_base = Parametros(
        horizonte=5, refeicoes_por_dia=3, orcamento=500.0, dias_compra=(1,)
    )

    cenarios = {
        "celiaco": (demo_filho_celiaco(catalogo_base, "crianca_8_anos"), parametros_base),
        "orcamento": (catalogo_base, demo_orcamento_reduzido(parametros_base)),
        "visita": (demo_chegou_visita(catalogo_base), parametros_base),
        "ninguem_jantou": (
            demo_ninguem_jantou(catalogo_base, dia=1, refeicao=parametros_base.refeicoes[0]),
            parametros_base,
        ),
        "afrouxar_sodio": (
            demo_afrouxar_sodio(catalogo_base, "idoso_hipertenso"),
            parametros_base,
        ),
    }

    for nome, (catalogo, parametros) in cenarios.items():
        solucao = resolver(catalogo, parametros)
        assert solucao.status in ("Optimal", "Not Solved"), f"demo '{nome}' deu {solucao.status}"
        assert solucao.cardapio, f"demo '{nome}' terminou sem cardapio ({solucao.status})"
