"""O "coracao" do projeto (card S3-08): ninguem programa "use primeiro o
que vence antes" — o comportamento EMERGE da otimizacao, porque jogar
comida fora custa dinheiro e o solver esta minimizando custo. Com um
lote de tomate vencendo no dia 3, as receitas que usam tomate aparecem
sozinhas nos dias 1 a 3, e nada e desperdicado.

ESTE TESTE NAO PODE QUEBRAR NUNCA MAIS. Se ficar vermelho, alguma coisa
fundamental do modelo se perdeu — nao marcar como skip para o CI passar.
"""
from __future__ import annotations

from nutricasa2050.dominio import Catalogo, Ingrediente, Lote, Membro, Parametros, Receita
from nutricasa2050.otimizacao.solver import resolver


def _catalogo_tomate_vencendo() -> Catalogo:
    tomate = Ingrediente(
        id="tomate",
        nome="Tomate",
        unidade="kg",
        categoria="hortifruti",
        validade_dias=3,
        preco_embalagem=1.0,
        tamanho_embalagem=1.0,
    )
    receitas = {
        "salada_de_tomate": Receita(
            id="salada_de_tomate", nome="Salada de tomate", tempo_min=10,
            tags=frozenset(), preferencia=0.0,
        ),
        "molho_de_tomate": Receita(
            id="molho_de_tomate", nome="Molho de tomate", tempo_min=15,
            tags=frozenset(), preferencia=0.0,
        ),
        "tomate_assado": Receita(
            id="tomate_assado", nome="Tomate assado", tempo_min=20,
            tags=frozenset(), preferencia=0.0,
        ),
        "arroz_simples": Receita(
            id="arroz_simples", nome="Arroz simples", tempo_min=20,
            tags=frozenset(), preferencia=0.0,
        ),
        "feijao_simples": Receita(
            id="feijao_simples", nome="Feijao simples", tempo_min=30,
            tags=frozenset(), preferencia=0.0,
        ),
    }
    matriz_a = {
        ("salada_de_tomate", "tomate"): 1.0,
        ("molho_de_tomate", "tomate"): 1.0,
        ("tomate_assado", "tomate"): 1.0,
    }
    lote_tomate = Lote(id="lote_tomate", ingrediente_id="tomate", quantidade=3.0, dia_vencimento=3)
    membro_unico = Membro(
        id="p1", nome="Pessoa", fator_porcao=1.0, tags_bloqueadas=frozenset(), faixas={}
    )
    return Catalogo(
        ingredientes={"tomate": tomate},
        receitas=receitas,
        matriz_a=matriz_a,
        nutrientes={},
        lotes={"lote_tomate": lote_tomate},
        membros={"p1": membro_unico},
    )


def test_coracao_antidesperdicio() -> None:
    catalogo = _catalogo_tomate_vencendo()
    parametros = Parametros(
        horizonte=5, refeicoes_por_dia=1, pratos_por_refeicao=1, orcamento=0.0, dias_compra=()
    )

    solucao = resolver(catalogo, parametros)

    assert solucao.status == "Optimal"

    receitas_de_tomate = {"salada_de_tomate", "molho_de_tomate", "tomate_assado"}
    dias_com_tomate = sorted(
        dia
        for (receita_id, dia, _refeicao) in solucao.cardapio
        if receita_id in receitas_de_tomate
    )

    # As tres receitas de tomate aparecem, e nenhuma depois do vencimento (dia 3).
    assert len(dias_com_tomate) == 3
    assert all(dia <= 3 for dia in dias_com_tomate)
    # Nada do tomate sobra para ser jogado fora.
    assert sum(solucao.descartes.values()) < 1e-6
