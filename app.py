"""A tela do NutriCasa 2050 (cards S5-05/06/07). Chama o solver COMO
FUNCAO PYTHON direto — sem HTTP, sem API, sem segundo processo.

REGRA ABSOLUTA: nenhuma conta mora aqui. Toda otimizacao, serializacao
e analise vem de src/nutricasa2050/ — este arquivo so liga widgets a
essas funcoes e desenha o resultado. A unica aritmetica feita aqui e
cosmetica (ex.: porcentagem de uma barra de progresso), nunca modelo.
"""
from __future__ import annotations

from dataclasses import replace

import streamlit as st

from nutricasa2050.dados.carga import carregar_catalogo
from nutricasa2050.dominio import Catalogo, Parametros, Pesos
from nutricasa2050.otimizacao.solver import descrever_status, resolver
from nutricasa2050.serializacao import resultado_para_dict
from nutricasa2050.simulacao.baselines import baseline_humano
from nutricasa2050.simulacao.cenarios import Cenario, adicionar_visita

st.set_page_config(page_title="NutriCasa 2050", page_icon="🥗", layout="wide")


def _injetar_css() -> None:
    """Camada 2 (card S5-07): esconde o menu e o rodape "Made with
    Streamlit", e alarga o container central (por padrao, uma coluna
    estreita no meio da tela). Sozinho, isso ja tira metade da "cara de
    Streamlit"."""
    st.markdown(
        """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {max-width: 1200px; padding-top: 2rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =============================== S5-05 — dados ===============================


@st.cache_resource
def carregar_catalogo_cacheado() -> Catalogo:
    """Guarda o catalogo em cache — sem isso, o Streamlit releria todos
    os CSVs a cada clique e a tela ficaria lenta de um jeito que parece
    bug."""
    return carregar_catalogo()


def montar_parametros(
    orcamento: float,
    tempo_por_dia: float,
    pesos: dict[str, float],
    horizonte: int = 7,
    refeicoes_por_dia: int = 3,
    dias_compra: tuple[int, ...] = (1,),
) -> Parametros:
    """Pura: monta Parametros a partir de VALORES (ja lidos da tela, ou
    passados direto em teste — e por isso que esta funcao existe
    separada de montar_barra_lateral)."""
    return Parametros(
        horizonte=horizonte,
        refeicoes_por_dia=refeicoes_por_dia,
        orcamento=orcamento,
        dias_compra=dias_compra,
        tempo_por_dia=tempo_por_dia,
        pesos=Pesos(**pesos),
    )


def filtrar_membros(catalogo: Catalogo, pessoas: list[str]) -> Catalogo:
    """Pura: devolve um catalogo so com os membros selecionados."""
    membros = {m_id: catalogo.membros[m_id] for m_id in pessoas if m_id in catalogo.membros}
    return replace(catalogo, membros=membros)


def montar_barra_lateral(catalogo: Catalogo) -> tuple[Parametros, list[str]]:
    """Os controles: pessoas presentes, orcamento, tempo por dia e os
    pesos do objetivo. "Pessoas" filtra catalogo.membros — nao e campo
    de Parametros, por isso esta funcao devolve os dois (pequeno desvio
    da assinatura literal do card "-> Parametros", documentado aqui: nao
    ha como aquele unico tipo carregar quem esta em casa)."""
    st.sidebar.header("Quem esta em casa essa semana")
    todos = list(catalogo.membros)
    pessoas = st.sidebar.multiselect("Membros da familia", todos, default=todos)

    st.sidebar.header("Parametros")
    orcamento = st.sidebar.slider("Orcamento semanal (R$)", 50.0, 1000.0, 500.0, step=10.0)
    tempo_por_dia = st.sidebar.slider("Tempo de cozinha por dia (min)", 10, 180, 60, step=5)

    st.sidebar.header("Pesos do objetivo")
    pesos = {
        "custo": st.sidebar.slider("Custo", 0.0, 5.0, 1.0, key="peso_custo"),
        "desperdicio": st.sidebar.slider("Desperdicio", 0.0, 5.0, 1.0, key="peso_desperdicio"),
        "preparo": st.sidebar.slider("Tempo de preparo", 0.0, 5.0, 1.0, key="peso_preparo"),
        "desvio": st.sidebar.slider("Desvio do alvo", 0.0, 5.0, 1.0, key="peso_desvio"),
        "folga": st.sidebar.slider(
            "Folga (penalidade)", 0.0, 2000.0, 1000.0, step=50.0, key="peso_folga"
        ),
        "preferencia": st.sidebar.slider("Preferencia", 0.0, 5.0, 1.0, key="peso_preferencia"),
    }

    parametros = montar_parametros(
        orcamento=orcamento, tempo_por_dia=float(tempo_por_dia), pesos=pesos
    )
    return parametros, pessoas


# ============================ S5-05 — desenho da tela =========================


def desenhar_numeros(resultado: dict, resultado_referencia: dict | None = None) -> None:
    """Tres cartoes: reducao de desperdicio (contra o baseline humano,
    quando fornecido), custo total e valor que venceu sem uso."""
    resumo = resultado["resumo"]
    col1, col2, col3 = st.columns(3)
    with col1:
        reducao_texto = "—"
        if resultado_referencia is not None:
            desperdicio_ref = resultado_referencia["resumo"]["valor_desperdicio"]
            if desperdicio_ref > 1e-9:
                reducao = (desperdicio_ref - resumo["valor_desperdicio"]) / desperdicio_ref * 100
                reducao_texto = f"{reducao:.0f}%"
        st.metric("Reducao de desperdicio", reducao_texto, help="Comparado a uma familia normal")
    with col2:
        st.metric("Custo total", f"R$ {resumo['custo_total']:.2f}")
    with col3:
        st.metric("Valor que venceu sem uso", f"R$ {resumo['valor_desperdicio']:.2f}")


_CARTAO_CARDAPIO = """
<div style="border:1px solid #E3E0D8;border-radius:8px;padding:8px 10px;
            margin-bottom:6px;background:{fundo};">
  <div style="font-size:12px;color:#7A776E;">Dia {dia}</div>
  <div style="font-weight:600;color:#2B2B28;">{nome}{selo}</div>
</div>
"""


def desenhar_cardapio(resultado: dict) -> None:
    """A grade do cardapio (camada 3, HTML proprio — card S5-07), com
    destaque AMBAR nos pratos puxados por validade (R10/S3-01). E o
    elemento mais rico da tela, e impossivel de construir sem o
    modelo."""
    st.subheader("Cardapio da semana")
    cardapio = resultado["cardapio"]
    if not cardapio:
        st.info("Nenhum prato planejado.")
        return

    dias = sorted({item["dia"] for item in cardapio})
    refeicoes = sorted({item["refeicao"] for item in cardapio})
    por_slot: dict[tuple[int, str], list[dict]] = {}
    for item in cardapio:
        por_slot.setdefault((item["dia"], item["refeicao"]), []).append(item)

    colunas = st.columns(len(refeicoes))
    for coluna, refeicao in zip(colunas, refeicoes, strict=False):
        with coluna:
            st.markdown(f"**{refeicao.replace('_', ' ').title()}**")
            for dia in dias:
                itens = por_slot.get((dia, refeicao), [])
                if not itens:
                    st.caption(f"Dia {dia}: —")
                    continue
                for item in itens:
                    puxado = bool(item.get("puxado_por_validade"))
                    html = _CARTAO_CARDAPIO.format(
                        dia=dia,
                        nome=item["receita_nome"],
                        fundo="#FBEBD6" if puxado else "#FFFFFF",
                        selo=" ⚠️" if puxado else "",
                    )
                    st.markdown(html, unsafe_allow_html=True)


_BARRA_DESPENSA = """
<div style="margin-bottom:6px;">
  <div style="display:flex;justify-content:space-between;font-size:13px;">
    <span>{nome}</span><span>{quantidade:.2f} — vence em {dias}d</span>
  </div>
  <div style="background:#EDEAE2;border-radius:4px;height:8px;">
    <div style="background:{cor};width:{largura}%;height:8px;border-radius:4px;"></div>
  </div>
</div>
"""


def desenhar_despensa(resultado: dict) -> None:
    """Barras da despensa no fim da semana (camada 3), coloridas pela
    proximidade do vencimento: vermelho (<=1 dia), ambar (<=3 dias),
    verde (resto)."""
    st.subheader("Despensa")
    estoque = resultado["estoque"]
    if not estoque:
        st.info("Nada em estoque.")
        return

    ultimo_dia = max(item["dia"] for item in estoque)
    itens = [
        item
        for item in estoque
        if item["dia"] == ultimo_dia and item["quantidade"] > 1e-6
    ]
    if not itens:
        st.success("Despensa vazia no fim da semana — nada sobrou.")
        return

    maior_dias = max(item["dias_restantes"] for item in itens) or 1
    for item in sorted(itens, key=lambda i: i["dias_restantes"]):
        dias_restantes = item["dias_restantes"]
        cor = "#D64545" if dias_restantes <= 1 else "#E8912A" if dias_restantes <= 3 else "#1D8A66"
        largura = max(10, min(100, int(100 * dias_restantes / maior_dias)))
        st.markdown(
            _BARRA_DESPENSA.format(
                nome=item["ingrediente_nome"],
                quantidade=item["quantidade"],
                dias=dias_restantes,
                cor=cor,
                largura=largura,
            ),
            unsafe_allow_html=True,
        )


def desenhar_compras(resultado: dict, parametros: Parametros) -> None:
    """A lista de compras, com o total contra o teto do orcamento."""
    st.subheader("Lista de compras")
    compras = resultado["compras"]
    if not compras:
        st.info("Nada para comprar esta semana.")
        return

    for item in sorted(compras, key=lambda i: i["ingrediente_nome"]):
        st.write(
            f"{item['ingrediente_nome']}: {item['embalagens']:.0f} embalagem(ns) "
            f"({item['quantidade']:.2f} {item['unidade']}) — R$ {item['custo']:.2f}"
        )

    total = resultado["resumo"]["custo_total"]
    fracao = min(total / parametros.orcamento, 1.0) if parametros.orcamento else 0.0
    st.progress(fracao)
    st.caption(f"R$ {total:.2f} de R$ {parametros.orcamento:.2f}")


_BARRA_ADERENCIA = """
<div style="margin-bottom:6px;">
  <div style="display:flex;justify-content:space-between;font-size:13px;">
    <span>{nutriente}</span><span>{valor:.0f} (alvo {alvo:.0f}){selo}</span>
  </div>
  <div style="background:#EDEAE2;border-radius:4px;height:8px;position:relative;">
    <div style="background:{cor};width:{largura}%;height:8px;border-radius:4px;"></div>
    <div style="position:absolute;left:{marcador}%;top:-2px;width:2px;height:12px;
                background:#2B2B28;"></div>
  </div>
</div>
"""


def desenhar_aderencia(resultado: dict) -> None:
    """Uma barrinha por membro e nutriente (camada 3, HTML proprio): a
    barra mostra onde o valor entregue caiu dentro da faixa, e um
    tracinho preto marca o alvo prescrito — fechar exatamente no
    tracinho e o ideal; usar folga (S3-06) e mostrado com um aviso."""
    st.subheader("Aderencia nutricional")
    aderencia = resultado["aderencia"]
    if not aderencia:
        st.info("Nenhuma faixa nutricional configurada.")
        return

    por_membro: dict[str, list[dict]] = {}
    for item in aderencia:
        por_membro.setdefault(item["membro_id"], []).append(item)

    for membro_id, itens in por_membro.items():
        st.markdown(f"**{membro_id}**")
        for item in itens:
            faixa = item["maximo"] - item["minimo"]
            posicao = (item["valor"] - item["minimo"]) / faixa if faixa else 0.0
            posicao_marcador = (item["alvo"] - item["minimo"]) / faixa if faixa else 0.0
            usou_folga = item["folga"] > 1e-6
            cor = "#E8912A" if usou_folga else "#1D8A66"
            st.markdown(
                _BARRA_ADERENCIA.format(
                    nutriente=item["nutriente"],
                    valor=item["valor"],
                    alvo=item["alvo"],
                    selo=" ⚠️ usou folga" if usou_folga else "",
                    cor=cor,
                    largura=max(0, min(100, posicao * 100)),
                    marcador=max(0, min(98, posicao_marcador * 100)),
                ),
                unsafe_allow_html=True,
            )


# ============================ S5-06 — os cinco botoes =========================


def demo_filho_celiaco(catalogo: Catalogo, crianca_id: str) -> Catalogo:
    """Acrescenta sem_gluten as tags bloqueadas SO DA CRIANCA — o
    modelo tem que achar pratos que sirvam a casa toda mesmo assim
    (R6, S3-03)."""
    membro = catalogo.membros[crianca_id]
    novo_membro = replace(membro, tags_bloqueadas=membro.tags_bloqueadas | {"sem_gluten"})
    return replace(catalogo, membros={**catalogo.membros, crianca_id: novo_membro})


def demo_orcamento_reduzido(parametros: Parametros, fracao: float = 0.3) -> Parametros:
    """Corta o orcamento em `fracao` (30% por padrao)."""
    return replace(parametros, orcamento=parametros.orcamento * (1 - fracao))


def demo_chegou_visita(catalogo: Catalogo, semente: int = 0) -> Catalogo:
    """Acrescenta um membro visitante — reaproveita a mesma perturbacao
    da Monte Carlo (simulacao.cenarios.adicionar_visita, S4-01)."""
    return adicionar_visita(catalogo, Cenario(semente=semente, membros_extras=1))


def demo_ninguem_jantou(catalogo: Catalogo, dia: int, refeicao: str = "jantar") -> Catalogo:
    """Zera uma refeicao de um dia — o solver replaneja os dias
    restantes porque R1 (restricoes.py) respeita
    Catalogo.refeicoes_puladas: nada e consumido nela, e por isso nada
    precisa ser "devolvido ao estoque" — o estoque simplesmente nunca
    chega a ser gasto naquela refeicao."""
    return replace(catalogo, refeicoes_puladas=catalogo.refeicoes_puladas | {(dia, refeicao)})


def demo_afrouxar_sodio(
    catalogo: Catalogo, membro_id: str, incremento: float = 500.0
) -> Catalogo:
    """Sobe o teto de sodio do membro em `incremento` — o preco-sombra
    (S5-01) e quem mostra quanto isso deveria baratear o resultado."""
    membro = catalogo.membros[membro_id]
    if "sodio_mg" not in membro.faixas:
        return catalogo
    faixa_atual = membro.faixas["sodio_mg"]
    nova_faixa = replace(faixa_atual, maximo=faixa_atual.maximo + incremento)
    novo_membro = replace(membro, faixas={**membro.faixas, "sodio_mg": nova_faixa})
    return replace(catalogo, membros={**catalogo.membros, membro_id: novo_membro})


def botoes_de_demo(catalogo: Catalogo, parametros: Parametros) -> tuple[Catalogo, Parametros]:
    """Desenha os cinco botoes e devolve o catalogo/parametros
    modificados pelo que foi clicado (ou os mesmos recebidos, se nada
    foi clicado)."""
    st.subheader("Demonstracao")
    colunas = st.columns(5)
    criancas = [m for m in catalogo.membros if "crianca" in m]
    idosos = [m for m in catalogo.membros if "idoso" in m]

    if colunas[0].button("Filho celiaco") and criancas:
        catalogo = demo_filho_celiaco(catalogo, criancas[0])
    if colunas[1].button("Orcamento -30%"):
        parametros = demo_orcamento_reduzido(parametros)
    if colunas[2].button("Chegou visita"):
        catalogo = demo_chegou_visita(catalogo)
    if colunas[3].button("Ninguem jantou"):
        catalogo = demo_ninguem_jantou(catalogo, dia=parametros.dias[0])
    if colunas[4].button("Afrouxar sodio") and idosos:
        catalogo = demo_afrouxar_sodio(catalogo, idosos[0])

    return catalogo, parametros


# ===================================== main ====================================


def main() -> None:
    _injetar_css()
    st.title("NutriCasa 2050")
    st.caption("Planejamento semanal otimizado — sem desperdicio por acidente.")

    catalogo_completo = carregar_catalogo_cacheado()
    parametros, pessoas = montar_barra_lateral(catalogo_completo)
    catalogo = filtrar_membros(catalogo_completo, pessoas)
    catalogo, parametros = botoes_de_demo(catalogo, parametros)

    if not catalogo.membros:
        st.warning("Selecione pelo menos uma pessoa na barra lateral.")
        return

    with st.spinner("Resolvendo..."):
        solucao = resolver(catalogo, parametros)

    # "Not Solved" SEM cardapio = tempo esgotado antes de achar qualquer
    # solucao inteira (solver.solucao_e_inteira); nao ha nada para mostrar.
    if solucao.status not in ("Optimal", "Not Solved") or not solucao.cardapio:
        st.error(descrever_status(solucao.status))
        return
    if solucao.status == "Not Solved":
        st.warning(descrever_status(solucao.status))

    resultado = resultado_para_dict(solucao, catalogo, parametros)

    with st.spinner("Calculando o baseline de comparacao..."):
        solucao_referencia = baseline_humano(catalogo, parametros)
    resultado_referencia = resultado_para_dict(solucao_referencia, catalogo, parametros)

    desenhar_numeros(resultado, resultado_referencia)
    desenhar_cardapio(resultado)

    col_despensa, col_compras = st.columns(2)
    with col_despensa:
        desenhar_despensa(resultado)
    with col_compras:
        desenhar_compras(resultado, parametros)

    desenhar_aderencia(resultado)


if __name__ == "__main__":
    main()
