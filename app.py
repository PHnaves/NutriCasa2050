"""A tela do NutriCasa 2050 (cards S5-05/06/07, redesenhada no Sprint 6).
Chama o solver COMO FUNCAO PYTHON direto — sem HTTP, sem API, sem segundo
processo.

Cinco paginas, num menu no topo (st.navigation):
  Inicio · Planejar a semana · Resultados · O problema · Ingredientes e precos

REGRA ABSOLUTA: nenhuma conta de modelo mora aqui. Otimizacao, serializacao
e analise vem de src/nutricasa2050/ — este arquivo so liga widgets a essas
funcoes e desenha o resultado. A aritmetica feita aqui e cosmetica
(porcentagem de uma barra, formatar R$).
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import replace
from html import escape
from pathlib import Path

# Hospedagem (Streamlit Community Cloud): la so existe `pip install -r
# requirements.txt`, sem o `pip install -e .` do Docker/CI. Colocar src/ no
# sys.path faz `import nutricasa2050` funcionar nos dois casos (onde o
# pacote ja esta instalado isto e inofensivo). Ver docs/HOSPEDAGEM.md.
_RAIZ = Path(__file__).resolve().parent
if str(_RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(_RAIZ / "src"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from nutricasa2050.analise import consultas  # noqa: E402
from nutricasa2050.dados.carga import carregar_catalogo  # noqa: E402
from nutricasa2050.dominio import Catalogo, Parametros, Pesos  # noqa: E402
from nutricasa2050.otimizacao.solver import descrever_status, resolver  # noqa: E402
from nutricasa2050.persistencia.banco import ConfiguracaoBanco, criar_engine  # noqa: E402
from nutricasa2050.serializacao import resultado_para_dict, resumo_nutricional  # noqa: E402
from nutricasa2050.simulacao.baselines import (  # noqa: E402
    baseline_humano,
    catalogo_com_compra_habitual,
)
from nutricasa2050.simulacao.cenarios import Cenario, adicionar_visita  # noqa: E402

LOGO = _RAIZ / "logo-horizontal-nutricasa.png"
ICONE = _RAIZ / "assets" / "icone-nutricasa.png"
CAMINHO_RESULTADOS = _RAIZ / "var" / "results.db"
FONTE_PRECOS = _RAIZ / "data" / "fonte_precos.json"
PRECOS_COLETADOS = _RAIZ / "data" / "precos_coletados.csv"

st.set_page_config(
    page_title="NutriCasa 2050",
    page_icon=str(ICONE) if ICONE.exists() else "🥗",
    layout="wide",
)

# Cores da logo (S5-07) — as mesmas de .streamlit/config.toml.
VERDE = "#1D8A66"
LARANJA = "#E8912B"
VERMELHO = "#C8473D"
TEXTO = "#2B2B28"
TEXTO_SUAVE = "#6B6860"
BORDA = "#E7E3DA"
FUNDO_SUAVE = "#F2EFE9"

NOMES_REFEICAO = {"cafe_da_manha": "Café da manhã", "almoco": "Almoço", "jantar": "Jantar"}
ORDEM_REFEICAO = {"cafe_da_manha": 0, "almoco": 1, "jantar": 2}
NOMES_NUTRIENTE = {
    "kcal": "Energia (kcal)",
    "proteina_g": "Proteína (g)",
    "carboidrato_g": "Carboidrato (g)",
    "gordura_g": "Gordura (g)",
    "sodio_mg": "Sódio (mg)",
    "fibra_g": "Fibra (g)",
}
NOMES_CATEGORIA = {
    "carnes": "Carnes e peixes",
    "folhosos": "Folhosos",
    "hortifruti": "Hortifrúti",
    "laticinios": "Laticínios e ovos",
    "secos": "Secos e enlatados",
}
NOMES_ESTRATEGIA = {
    "otimizado": "NutriCasa (otimizado)",
    "humano": "Família normal",
    "guloso": "Guloso (vence-primeiro)",
}
# Preco da prescricao (S4-06): seguir as faixas da nutricionista vs. nao
# seguir, num cenario base (5 dias, R$ 900, tempo limite 30 s). Nao vem do
# banco da Monte Carlo — e medido a parte com consultas.preco_da_prescricao
# e registrado em docs/resultados.md. Atualize os dois juntos.
PRECO_DA_PRESCRICAO = {"reais_por_semana": 332.54, "minutos_de_cozinha": 301.0}

NOMES_TAG = {
    "vegetariano": "vegetariano",
    "sem_gluten": "sem glúten",
    "sem_lactose": "sem lactose",
    "alto_sodio": "alto em sódio",
}


# ================================== estilo ====================================


_CSS = f"""
<style>
#MainMenu, footer {{visibility: hidden;}}
.block-container {{max-width: 1180px; padding-top: 4.5rem; padding-bottom: 3rem;}}
h1, h2, h3 {{color: {TEXTO}; letter-spacing: -0.01em;}}
.nc-eyebrow {{color: {VERDE}; font-weight: 700; font-size: .78rem; letter-spacing: .08em;
  text-transform: uppercase; margin-bottom: .2rem;}}
.nc-lead {{color: {TEXTO_SUAVE}; font-size: 1.08rem; line-height: 1.55; max-width: 62ch;}}
h1.nc-titulo {{font-size: 2.6rem; line-height: 1.12; margin: .4rem 0 .9rem 0; font-weight: 800;}}
h1.nc-titulo .verde, .nc-verde {{color: {VERDE};}}
.nc-card {{background: #FFFFFF; border: 1px solid {BORDA}; border-radius: 14px;
  padding: 18px 20px; height: 100%; box-shadow: 0 1px 2px rgba(43,43,40,.04);}}
.nc-card h4 {{margin: .3rem 0 .4rem 0; font-size: 1.05rem; color: {TEXTO};}}
.nc-card p {{color: {TEXTO_SUAVE}; font-size: .93rem; line-height: 1.5; margin: 0;}}
.nc-card .nc-num {{display: inline-flex; width: 28px; height: 28px; border-radius: 50%;
  background: {VERDE}; color: #fff; font-weight: 700; align-items: center;
  justify-content: center; font-size: .9rem;}}
.nc-kpi {{background: #FFFFFF; border: 1px solid {BORDA}; border-radius: 14px;
  padding: 16px 18px; height: 100%;}}
.nc-kpi .rotulo {{color: {TEXTO_SUAVE}; font-size: .82rem; font-weight: 600;}}
.nc-kpi .valor {{color: {TEXTO}; font-size: 1.75rem; font-weight: 750; line-height: 1.2;
  margin-top: 4px; font-variant-numeric: tabular-nums;}}
.nc-kpi .valor.verde {{color: {VERDE};}}
.nc-kpi .valor.laranja {{color: {LARANJA};}}
.nc-kpi .nota {{color: {TEXTO_SUAVE}; font-size: .8rem; margin-top: 4px;}}
.nc-destaque {{background: {VERDE}; color: #fff; border-radius: 16px; padding: 22px 24px;}}
.nc-destaque .grande {{font-size: 3rem; font-weight: 800; line-height: 1;}}
.nc-destaque p {{color: #E5F3EE; margin: .5rem 0 0 0; line-height: 1.45;}}
.nc-destaque .fonte {{font-size: .75rem; color: #BFE3D6; margin-top: .8rem;}}
.nc-chip {{display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: .74rem;
  font-weight: 600; margin: 2px 4px 2px 0; background: {FUNDO_SUAVE}; color: {TEXTO_SUAVE};}}
.nc-chip.verde {{background: #E3F2EC; color: #13684C;}}
.nc-chip.laranja {{background: #FCEBD5; color: #9A5A0E;}}
.nc-chip.vermelho {{background: #F8E1DE; color: #9A2F27;}}
.nc-grade {{overflow-x: auto; border: 1px solid {BORDA}; border-radius: 14px; background: #fff;}}
.nc-grade table {{border-collapse: collapse; width: 100%; min-width: 640px;}}
.nc-grade th {{background: {FUNDO_SUAVE}; color: {TEXTO}; font-size: .82rem; font-weight: 700;
  padding: 10px; text-align: left; border-bottom: 1px solid {BORDA};}}
.nc-grade th.refeicao {{width: 120px; background: #FAF8F4;}}
.nc-grade td {{padding: 8px; vertical-align: top; border-bottom: 1px solid {BORDA};
  border-left: 1px solid {BORDA};}}
.nc-prato {{background: #fff; border: 1px solid {BORDA}; border-left: 4px solid {VERDE};
  border-radius: 8px; padding: 7px 9px; margin-bottom: 6px; font-size: .86rem;
  font-weight: 600; color: {TEXTO}; line-height: 1.3;}}
.nc-prato.vence {{border-left-color: {LARANJA}; background: #FFF8EE;}}
.nc-prato .quem {{display: block; font-weight: 500; color: {TEXTO_SUAVE}; font-size: .74rem;
  margin-top: 3px;}}
.nc-vazio {{color: #B5B1A7; font-size: .8rem;}}
.nc-barra {{margin: 10px 0 14px 0;}}
.nc-barra .topo {{display: flex; justify-content: space-between; font-size: .86rem;
  color: {TEXTO}; margin-bottom: 5px; gap: 8px;}}
.nc-barra .trilho {{position: relative; height: 10px; background: #EDEAE2; border-radius: 6px;}}
.nc-barra .faixa {{position: absolute; top: 0; height: 10px; background: #CFE8DD;
  border-radius: 6px;}}
.nc-barra .ponto {{position: absolute; top: -3px; width: 16px; height: 16px; border-radius: 50%;
  border: 3px solid #fff; box-shadow: 0 0 0 1px rgba(0,0,0,.15); transform: translateX(-50%);}}
.nc-barra .alvo {{position: absolute; top: -4px; width: 2px; height: 18px; background: {TEXTO};
  transform: translateX(-50%);}}
.nc-rodape {{margin-top: 3rem; padding-top: 1rem; border-top: 1px solid {BORDA};
  color: {TEXTO_SUAVE}; font-size: .8rem;}}
.nc-legenda {{color: {TEXTO_SUAVE}; font-size: .8rem; margin: .4rem 0 .8rem 0;}}
.nc-legenda .q {{display: inline-block; width: 10px; height: 10px; border-radius: 2px;
  margin: 0 4px 0 10px; vertical-align: middle;}}
</style>
"""


def _injetar_css() -> None:
    """Camada 2 (card S5-07): esconde o menu e o rodape do Streamlit, limita a
    largura e define os componentes visuais (cartoes, grade, barras)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def _html(conteudo: str) -> None:
    st.markdown(conteudo, unsafe_allow_html=True)


def _reais(valor: float, casas: int = 2) -> str:
    """R$ no formato brasileiro: 1.234,56."""
    texto = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _numero(valor: float, casas: int = 0) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _kpi(rotulo: str, valor: str, nota: str = "", cor: str = "") -> str:
    nota_html = f'<div class="nota">{nota}</div>' if nota else ""
    return (
        f'<div class="nc-kpi"><div class="rotulo">{rotulo}</div>'
        f'<div class="valor {cor}">{valor}</div>{nota_html}</div>'
    )


def _cartao(titulo: str, texto: str, numero: str = "") -> str:
    numero_html = f'<span class="nc-num">{numero}</span>' if numero else ""
    return f'<div class="nc-card">{numero_html}<h4>{titulo}</h4><p>{texto}</p></div>'


def _cabecalho(sobrancelha: str, titulo: str, texto: str = "") -> None:
    _html(f'<div class="nc-eyebrow">{sobrancelha}</div>')
    st.title(titulo)
    if texto:
        _html(f'<p class="nc-lead">{texto}</p>')


def _rodape() -> None:
    _html(
        '<div class="nc-rodape">NutriCasa 2050 · projeto acadêmico de Pesquisa Operacional · '
        "programação linear inteira mista (PuLP + CBC) · "
        '<a href="https://github.com/PHnaves/NutriCasa2050" target="_blank">código no GitHub</a>'
        "</div>"
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
    passados direto em teste)."""
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


def nomes_dos_membros(catalogo: Catalogo) -> dict[str, str]:
    return {m_id: membro.nome for m_id, membro in catalogo.membros.items()}


@st.cache_data(show_spinner=False, max_entries=32)
def resolver_cacheado(catalogo: Catalogo, parametros: Parametros):
    """O Streamlit reexecuta o script a cada clique; sem cache, voltar a uma
    configuracao ja vista custaria outros ~10 s de solver."""
    return resolver(catalogo, parametros)


@st.cache_data(show_spinner=False, max_entries=32)
def baseline_cacheado(catalogo: Catalogo, parametros: Parametros):
    return baseline_humano(catalogo, parametros)


# ============================ S5-06 — os imprevistos ==========================


def demo_filho_celiaco(catalogo: Catalogo, crianca_id: str) -> Catalogo:
    """A crianca passa a EXIGIR a tag sem_gluten (so come receitas marcadas
    sem gluten) — o modelo tem que achar pratos que sirvam a casa toda
    mesmo assim (R6, S3-03). Exigir, nao bloquear: nos dados, "sem_gluten"
    significa que a receita NAO tem gluten (correcao do Sprint 6)."""
    membro = catalogo.membros[crianca_id]
    novo_membro = replace(membro, tags_exigidas=membro.tags_exigidas | {"sem_gluten"})
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
    restantes porque R1 respeita Catalogo.refeicoes_puladas."""
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


SEM_IMPREVISTO = "Semana normal"
IMPREVISTOS = {
    SEM_IMPREVISTO: "Nada fora do comum: a família inteira, o orçamento e as dietas de sempre.",
    "Filho celíaco": (
        "A criança só pode comer pratos sem glúten. O modelo precisa achar pratos que "
        "sirvam a ela sem obrigar a casa toda a mudar o que come."
    ),
    "Orçamento −30%": "O dinheiro da semana encolhe 30%. Onde o modelo corta?",
    "Chegou visita": "Uma pessoa a mais come em casa a semana toda.",
    "Ninguém jantou": "O jantar do primeiro dia não aconteceu. O resto da semana é replanejado.",
    "Afrouxar sódio": (
        "O teto de sódio do idoso sobe 500 mg. Mostra quanto aquela regra estava "
        "custando (é o preço-sombra, ao vivo)."
    ),
}


def aplicar_imprevisto(
    catalogo: Catalogo, parametros: Parametros, imprevisto: str | None
) -> tuple[Catalogo, Parametros]:
    """Pura: aplica UM dos imprevistos de demonstracao (S5-06). Se a pessoa
    afetada nao estiver em casa, devolve tudo como veio."""
    criancas = [m for m in catalogo.membros if "crianca" in m]
    idosos = [m for m in catalogo.membros if "idoso" in m]
    if imprevisto == "Filho celíaco" and criancas:
        catalogo = demo_filho_celiaco(catalogo, criancas[0])
    elif imprevisto == "Orçamento −30%":
        parametros = demo_orcamento_reduzido(parametros)
    elif imprevisto == "Chegou visita":
        catalogo = demo_chegou_visita(catalogo)
    elif imprevisto == "Ninguém jantou":
        catalogo = demo_ninguem_jantou(catalogo, dia=parametros.dias[0])
    elif imprevisto == "Afrouxar sódio" and idosos:
        catalogo = demo_afrouxar_sodio(catalogo, idosos[0])
    return catalogo, parametros


# ============================ desenho dos resultados ==========================


def desenhar_numeros(resultado: dict, resultado_referencia: dict | None = None) -> None:
    """Os cartoes do topo: compras, desperdicio, comparacao com a familia
    normal (quando fornecida) e tempo de cozinha."""
    resumo = resultado["resumo"]
    reducao_texto, nota_reducao = "—", "sem comparação disponível"
    if resultado_referencia is not None:
        desperdicio_ref = resultado_referencia["resumo"]["valor_desperdicio"]
        if desperdicio_ref > 1e-9:
            reducao = (desperdicio_ref - resumo["valor_desperdicio"]) / desperdicio_ref * 100
            reducao_texto = f"{reducao:.0f}% menos"
            nota_reducao = f"a família normal jogaria fora {_reais(desperdicio_ref)}"
    dias = len({item["dia"] for item in resultado["cardapio"]}) or 1
    minutos = resumo.get("tempo_cozinha_minutos", 0)

    colunas = st.columns(4)
    cartoes = [
        _kpi("Compras da semana", _reais(resumo["custo_total"]), "lista completa na aba Compras"),
        _kpi(
            "Comida que vence sem uso",
            _reais(resumo["valor_desperdicio"]),
            "valor descartado na semana",
            "laranja" if resumo["valor_desperdicio"] > 0.01 else "verde",
        ),
        _kpi("Desperdício vs. família normal", reducao_texto, nota_reducao, "verde"),
        _kpi("Tempo de cozinha", f"{minutos / dias:.0f} min/dia", f"{minutos} min na semana"),
    ]
    for coluna, cartao in zip(colunas, cartoes, strict=False):
        with coluna:
            _html(cartao)


def desenhar_cardapio(resultado: dict, nomes: dict[str, str] | None = None) -> None:
    """A grade do cardapio (dias nas colunas, refeicoes nas linhas). Prato
    com borda laranja usa algo que estava na despensa vencendo em ate 2
    dias. Embaixo de cada prato: quem come dele (com o celiaco, por exemplo,
    a crianca aparece num prato diferente do resto da casa)."""
    cardapio = resultado["cardapio"]
    if not cardapio:
        st.info("Nenhum prato planejado.")
        return

    nomes = nomes or {}
    quem_come: dict[tuple[int, str, str], list[str]] = {}
    for porcao in resultado.get("porcoes", []):
        if porcao["fracao"] > 0.05:
            chave = (porcao["dia"], porcao["refeicao"], porcao["receita_id"])
            nome = nomes.get(porcao["membro_id"], porcao["membro_id"]).split(" (")[0]
            quem_come.setdefault(chave, []).append(nome)

    dias = sorted({item["dia"] for item in cardapio})
    refeicoes = sorted(
        {item["refeicao"] for item in cardapio}, key=lambda r: ORDEM_REFEICAO.get(r, 9)
    )
    por_slot: dict[tuple[int, str], list[dict]] = {}
    for item in cardapio:
        por_slot.setdefault((item["dia"], item["refeicao"]), []).append(item)

    linhas = []
    for refeicao in refeicoes:
        celulas = []
        for dia in dias:
            pratos = []
            for item in por_slot.get((dia, refeicao), []):
                classe = "nc-prato vence" if item.get("puxado_por_validade") else "nc-prato"
                pessoas = quem_come.get((dia, refeicao, item["receita_id"]), [])
                quem = f'<span class="quem">{escape(", ".join(pessoas))}</span>' if pessoas else ""
                pratos.append(f'<div class="{classe}">{escape(item["receita_nome"])}{quem}</div>')
            celulas.append(f"<td>{''.join(pratos) or '<span class=nc-vazio>—</span>'}</td>")
        rotulo = NOMES_REFEICAO.get(refeicao, refeicao.replace("_", " ").title())
        linhas.append(f'<tr><th class="refeicao">{rotulo}</th>{"".join(celulas)}</tr>')

    cabecalho = "".join(f"<th>Dia {dia}</th>" for dia in dias)
    _html(
        f'<div class="nc-grade"><table><thead><tr><th class="refeicao"></th>{cabecalho}</tr>'
        f'</thead><tbody>{"".join(linhas)}</tbody></table></div>'
    )
    _html(
        '<div class="nc-legenda"><span class="q" style="background:#1D8A66"></span>prato do '
        'plano<span class="q" style="background:#E8912B"></span>usa algo da despensa que vence '
        "em até 2 dias · embaixo de cada prato, quem come dele</div>"
    )


def desenhar_despensa(resultado: dict) -> None:
    """O que sobra na despensa no fim da semana, colorido pela proximidade
    do vencimento: vermelho (<=1 dia), laranja (<=3 dias), verde (resto)."""
    estoque = resultado["estoque"]
    if not estoque:
        st.info("Nada em estoque.")
        return

    ultimo_dia = max(item["dia"] for item in estoque)
    itens = [item for item in estoque if item["dia"] == ultimo_dia and item["quantidade"] > 1e-6]
    if not itens:
        st.success("A despensa termina a semana vazia: nada sobrou.")
        return

    st.caption(f"O que sobra na despensa no fim do dia {ultimo_dia}, do que vence antes ao depois.")
    maior_dias = max(max(item["dias_restantes"] for item in itens), 1)
    for item in sorted(itens, key=lambda i: i["dias_restantes"]):
        dias_restantes = item["dias_restantes"]
        if dias_restantes <= 1:
            cor, chip = VERMELHO, '<span class="nc-chip vermelho">vence já</span>'
        elif dias_restantes <= 3:
            cor, chip = LARANJA, '<span class="nc-chip laranja">vence logo</span>'
        else:
            cor, chip = VERDE, ""
        largura = max(6, min(100, int(100 * dias_restantes / maior_dias)))
        _html(
            f'<div class="nc-barra"><div class="topo"><span>{escape(item["ingrediente_nome"])} '
            f"{chip}</span><span>{_numero(item['quantidade'], 2)} · vence em "
            f"{dias_restantes} dia(s)</span></div><div class=\"trilho\"><div class=\"faixa\" "
            f'style="left:0;width:{largura}%;background:{cor};opacity:.85"></div></div></div>'
        )


def desenhar_descartes(resultado: dict, catalogo: Catalogo) -> None:
    """O que venceu e foi para o lixo (R10), com o valor em reais."""
    descartes = resultado.get("descartes", [])
    if not descartes:
        st.success("Nada venceu na despensa durante a semana. Desperdício zero.")
        return
    linhas = [
        {
            "Ingrediente": catalogo.ingredientes[item["ingrediente_id"]].nome
            if item["ingrediente_id"] in catalogo.ingredientes
            else item["ingrediente_id"],
            "Dia": item["dia"],
            "Quantidade": _numero(item["quantidade"], 2),
            "Valor": _reais(item["valor"]),
        }
        for item in descartes
    ]
    st.dataframe(pd.DataFrame(linhas), hide_index=True)


def desenhar_compras(resultado: dict, parametros: Parametros) -> None:
    """A lista de compras, com o total contra o teto do orcamento."""
    compras = resultado["compras"]
    if not compras:
        st.info("Nada para comprar esta semana: a despensa já dá conta.")
        return

    total = resultado["resumo"]["custo_total"]
    fracao = min(total / parametros.orcamento, 1.0) if parametros.orcamento else 0.0
    st.progress(fracao, text=f"{_reais(total)} de {_reais(parametros.orcamento)} do orçamento")
    tabela = pd.DataFrame(
        [
            {
                "Ingrediente": item["ingrediente_nome"],
                "Embalagens": int(round(item["embalagens"])),
                "Quantidade": f"{_numero(item['quantidade'], 2)} {item['unidade']}",
                "Custo": _reais(item["custo"]),
            }
            for item in sorted(compras, key=lambda i: i["ingrediente_nome"])
        ]
    )
    st.dataframe(tabela, hide_index=True)


def _barra_nutriente(item: dict) -> str:
    """Uma barra: trilho cinza, faixa permitida em verde-claro, tracinho no
    alvo e bolinha na media entregue (verde dentro da faixa, laranja fora)."""
    minimo, maximo, alvo, media = item["minimo"], item["maximo"], item["alvo"], item["media"]
    escala = max(maximo * 1.3, media * 1.05, 1.0)

    def pos(valor: float) -> float:
        return max(0.0, min(100.0, valor / escala * 100))

    fora = item["dias_fora_da_faixa"]
    cor = VERDE if fora == 0 else LARANJA
    chip = (
        '<span class="nc-chip verde">dentro da faixa</span>'
        if fora == 0
        else f'<span class="nc-chip laranja">fora em {fora} de {item["dias"]} dia(s)</span>'
    )
    nome = NOMES_NUTRIENTE.get(item["nutriente"], item["nutriente"])
    return (
        f'<div class="nc-barra"><div class="topo"><span><b>{nome}</b> {chip}</span>'
        f"<span>média {_numero(media)} · faixa {_numero(minimo)}–{_numero(maximo)}</span></div>"
        f'<div class="trilho"><div class="faixa" style="left:{pos(minimo)}%;'
        f'width:{pos(maximo) - pos(minimo)}%"></div>'
        f'<div class="alvo" style="left:{pos(alvo)}%"></div>'
        f'<div class="ponto" style="left:{pos(media)}%;background:{cor}"></div></div></div>'
    )


def desenhar_aderencia(resultado: dict, nomes: dict[str, str] | None = None) -> None:
    """Uma barra por pessoa e nutriente com a MEDIA diaria entregue contra a
    faixa prescrita (S3-06). Fora da faixa = o modelo usou folga: nao havia
    como cumprir a regra com o que estava disponivel, e ele mostra onde
    cedeu em vez de esconder."""
    aderencia = resultado["aderencia"]
    if not aderencia:
        st.info("Nenhuma faixa nutricional configurada.")
        return

    nomes = nomes or {}
    por_membro: dict[str, list[dict]] = {}
    for item in resumo_nutricional(aderencia):
        por_membro.setdefault(item["membro_id"], []).append(item)

    colunas = st.columns(2)
    for indice, (membro_id, itens) in enumerate(por_membro.items()):
        with colunas[indice % 2], st.container(border=True):
            st.markdown(f"**{nomes.get(membro_id, membro_id)}**")
            _html("".join(_barra_nutriente(item) for item in itens))


def desenhar_comparacao(resultado: dict, resultado_referencia: dict) -> None:
    """NutriCasa contra a familia normal (baseline humano, S4-02), nos
    mesmos dados."""
    otimo, humano = resultado["resumo"], resultado_referencia["resumo"]
    tabela = pd.DataFrame(
        [
            {
                "": "Compras da semana",
                "NutriCasa": _reais(otimo["custo_total"]),
                "Família normal": _reais(humano["custo_total"]),
            },
            {
                "": "Comida que venceu",
                "NutriCasa": _reais(otimo["valor_desperdicio"]),
                "Família normal": _reais(humano["valor_desperdicio"]),
            },
            {
                "": "Total gasto + perdido",
                "NutriCasa": _reais(otimo["custo_total"] + otimo["valor_desperdicio"]),
                "Família normal": _reais(humano["custo_total"] + humano["valor_desperdicio"]),
            },
        ]
    )
    st.dataframe(tabela, hide_index=True)
    st.caption(
        "A família normal escolhe pelo gosto, compra a lista de sempre (sem olhar o "
        "cardápio) e não confere o que vence primeiro. As duas rodam com os mesmos preços, "
        "a mesma despensa e as mesmas pessoas."
    )


# ============================ simulacao (Monte Carlo) =========================


def ler_resultados_da_simulacao(caminho: Path = CAMINHO_RESULTADOS) -> dict | None:
    """Le os numeros da Monte Carlo do banco publicado junto com o app
    (var/results.db, docs/SQLITE.md secao 6). None se o arquivo nao existe.
    So leitura: toda conta mora em analise/consultas.py."""
    if not caminho.exists():
        return None
    url = f"sqlite:///{caminho}"
    engine = criar_engine(ConfiguracaoBanco("development", url, "sqlite:///:memory:"), url)
    return {
        "desperdicio": consultas.desperdicio_por_estrategia(engine),
        "reducao": consultas.reducao_de_desperdicio(engine),
        "economia": consultas.economia_mensal(engine),
        "folgas": consultas.folgas_mais_frequentes(engine)[:6],
        "cenarios": consultas.numero_de_cenarios(engine),
    }


@st.cache_data(show_spinner=False)
def _resultados_cacheados() -> dict | None:
    return ler_resultados_da_simulacao()


def regra_mais_dificil(dados: dict | None, nomes: dict[str, str]) -> tuple[str, str]:
    """("Fibra", "de João (Idoso)") a partir da folga mais frequente."""
    if not dados or not dados["folgas"]:
        return "—", ""
    primeira = dados["folgas"][0]
    nutriente = NOMES_NUTRIENTE.get(primeira["nutriente"], primeira["nutriente"]).split(" (")[0]
    return nutriente, f"de {nomes.get(primeira['membro_id'], primeira['membro_id'])}"


def desenhar_resultados_da_simulacao(dados: dict | None) -> None:
    """Os numeros da Monte Carlo (S4-06, revalidados no Sprint 6)."""
    if dados is None:
        st.info(
            "Ainda não há resultados publicados (var/results.db). Rode `make resultados` e "
            "`make publicar-resultados` — ver docs/HOSPEDAGEM.md."
        )
        return

    media, inferior, superior = dados["economia"]
    desperdicio = dados["desperdicio"]
    colunas = st.columns(3)
    cartoes = [
        _kpi(
            "Desperdício vs. família normal",
            f"−{_numero(dados['reducao'], 1)}%",
            f"{_reais(desperdicio.get('otimizado', 0))} contra "
            f"{_reais(desperdicio.get('humano', 0))} por semana, em média",
            "verde",
        ),
        _kpi(
            "Semanas simuladas",
            str(dados["cenarios"]),
            "× 3 estratégias, com os mesmos dados sorteados",
        ),
        _kpi(
            "Regra mais difícil de cumprir",
            " ".join(regra_mais_dificil(dados, nomes_dos_membros(carregar_catalogo_cacheado()))),
            "a meta nutricional que a realidade mais atropela",
            "laranja",
        ),
    ]
    for coluna, cartao in zip(colunas, cartoes, strict=False):
        with coluna:
            _html(cartao)

    st.subheader("Desperdício médio por semana, por estratégia")
    cores = {"otimizado": VERDE, "humano": LARANJA, "guloso": "#9A968C"}
    maior = max(desperdicio.values()) or 1.0
    barras = []
    for nome, valor in sorted(desperdicio.items(), key=lambda item: -item[1]):
        largura = max(1.5, valor / maior * 100)
        barras.append(
            f'<div class="nc-barra"><div class="topo"><span><b>'
            f"{NOMES_ESTRATEGIA.get(nome, nome)}</b></span><span>{_reais(valor)} por semana"
            f'</span></div><div class="trilho" style="height:18px;border-radius:9px">'
            f'<div class="faixa" style="left:0;width:{largura:.1f}%;height:18px;'
            f'border-radius:9px;background:{cores.get(nome, VERDE)}"></div></div></div>'
        )
    _html("".join(barras))
    with st.container(border=True):
        st.markdown(
            "**Leitura honesta do gráfico.** A estratégia gulosa (cozinhar sempre o que vence "
            "primeiro) desperdiça praticamente o mesmo, mas **ignora a dieta**: não olha o "
            "sódio do idoso nem se a criança comeu o suficiente, e compra a lista habitual da "
            "família normal. O NutriCasa chega ao mesmo desperdício **cumprindo a dieta de "
            "cada pessoa** e gastando menos no mercado."
        )

    if dados["folgas"]:
        st.subheader("Onde a dieta prescrita mais cede")
        st.caption(
            f"Em quantas pessoas×dias, somando as 3 estratégias e os {dados['cenarios']} cenários, "
            "o nutriente "
            "ficou fora da faixa da nutricionista."
        )
        catalogo = carregar_catalogo_cacheado()
        nomes = nomes_dos_membros(catalogo)
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Pessoa": nomes.get(folga["membro_id"], folga["membro_id"]),
                        "Nutriente": NOMES_NUTRIENTE.get(folga["nutriente"], folga["nutriente"]),
                        "Vezes fora da faixa": folga["vezes_com_folga"],
                        "Quanto faltou/sobrou, em média": _numero(folga["folga_media"], 1),
                    }
                    for folga in dados["folgas"]
                ]
            ),
            hide_index=True,
        )

    with st.expander("Outros números e ressalvas"):
        st.markdown(
            f"- **Economia projetada por mês** (compras + desperdício, NutriCasa vs. família "
            f"normal): {_reais(media, 0)}, intervalo de confiança de 95% de "
            f"{_reais(inferior, 0)} a {_reais(superior, 0)}. É alto porque a família normal "
            "da simulação compra a lista habitual com 30% de folga. Por isso defendemos a "
            "**porcentagem**, que compara cenários idênticos.\n"
            "- **Preço da prescrição:** seguir as faixas da nutricionista custa cerca de "
            f"**{_reais(PRECO_DA_PRESCRICAO['reais_por_semana'], 0)} a mais por semana** e "
            f"{PRECO_DA_PRESCRICAO['minutos_de_cozinha']:.0f} min de cozinha (ordem de grandeza, "
            "medido num "
            "cenário base).\n"
            "- **Sem prova de ótimo:** o solver roda com tempo limite (30 s na simulação) e "
            "devolve a melhor resposta *encontrada*.\n"
            "- Detalhes em `docs/resultados.md` e `docs/relatorio.md`."
        )


# ================================== paginas ===================================


_PAGINAS: dict[str, st.Page] = {}


def pagina_inicio() -> None:
    esquerda, direita = st.columns([1.55, 1], gap="large")
    with esquerda:
        if LOGO.exists():
            st.image(str(LOGO), width=300)
        _html(
            '<h1 class="nc-titulo">A semana de comida da família, planejada para '
            '<span class="verde">não jogar nada fora</span>.</h1>'

            '<p class="nc-lead">Você diz quem está em casa, quanto pode gastar e quanto tempo '
            "tem para cozinhar. O NutriCasa decide o cardápio, a porção de cada pessoa e a "
            "lista de compras, respeitando a dieta de cada um e usando primeiro o que vence "
            "primeiro.</p>"
        )
        botao, link, _ = st.columns([1.1, 1.1, 0.6])
        if botao.button("Planejar minha semana", type="primary", icon=":material/restaurant_menu:",
                        width="stretch") and "planejar" in _PAGINAS:
            st.switch_page(_PAGINAS["planejar"])
        if link.button("Entender o problema", icon=":material/menu_book:",
                       width="stretch") and "problema" in _PAGINAS:
            st.switch_page(_PAGINAS["problema"])
    with direita:
        _html(
            '<div class="nc-destaque"><div class="grande">41,6 kg</div>'
            "<p>de comida jogada fora <b>por pessoa, por ano</b>, dentro de casa no Brasil. "
            "Arroz, carne, feijão e frango lideram a lista.</p>"
            '<div class="fonte">Fonte: Embrapa e FGV, pesquisa "Intercâmbio Brasil–União '
            'Europeia sobre desperdício de alimentos" (Porpino et al., 2018).</div></div>'
        )
    st.write("")
    st.subheader("Como funciona")
    passos = [
        (
            "Conte como é a sua casa",
            "Quem come em casa, o orçamento da semana e quanto tempo dá para cozinhar por dia.",
        ),
        (
            "O modelo faz as contas",
            "Um modelo de otimização testa as combinações de pratos, porções e compras e "
            "escolhe a de menor custo total, contando o que iria para o lixo.",
        ),
        (
            "Receba o plano pronto",
            "Cardápio da semana, lista de compras, o que sobra na despensa e como ficou a "
            "nutrição de cada pessoa.",
        ),
    ]
    for coluna, (numero, (titulo, texto)) in zip(
        st.columns(3), enumerate(passos, start=1), strict=False
    ):
        with coluna:
            _html(_cartao(titulo, texto, str(numero)))

    st.write("")
    dados = _resultados_cacheados()
    semanas = dados["cenarios"] if dados else 0
    st.subheader(f"O que {semanas} semanas simuladas mostraram")
    colunas = st.columns(3)
    reducao = f"−{dados['reducao']:.0f}%" if dados else "—"
    with colunas[0]:
        _html(
            _kpi("Desperdício", reducao, "contra uma família que compra a lista de sempre", "verde")
        )
    with colunas[1]:
        _html(
            _kpi(
                "Seguir a dieta custa",
                f"≈ {_reais(PRECO_DA_PRESCRICAO['reais_por_semana'], 0)}",
                "a mais por semana: o preço da prescrição",
            )
        )
    with colunas[2]:
        nomes = nomes_dos_membros(carregar_catalogo_cacheado())
        nutriente, de_quem = regra_mais_dificil(dados, nomes)
        _html(_kpi("Mais difícil de cumprir", nutriente, de_quem, "laranja"))
    if "resultados" in _PAGINAS:
        st.page_link(
            _PAGINAS["resultados"], label="Ver os resultados completos", icon=":material/insights:"
        )

    st.write("")
    st.subheader("Por trás da tela")
    colunas = st.columns(3)
    blocos = [
        (
            "Pesquisa Operacional",
            "Programação linear inteira mista, a mesma família de técnicas usada em logística "
            "e escala de produção. Resolvida pelo solver CBC.",
        ),
        (
            "12 regras",
            "Cardápio, nutrição, estoque com validade e limites de tempo e dinheiro. Cada uma "
            "existe por um motivo do mundo real.",
        ),
        (
            "Base de 1945",
            "Parte do problema da dieta de George Stigler e acrescenta tempo, validade dos "
            "alimentos e uma família com dietas diferentes.",
        ),
    ]
    for coluna, (titulo, texto) in zip(colunas, blocos, strict=False):
        with coluna:
            _html(_cartao(titulo, texto))
    _rodape()


def formulario_da_semana(catalogo: Catalogo) -> tuple[list[str], Parametros, str]:
    """O formulario: quem esta em casa, limites da semana, imprevisto e o
    ajuste fino dos pesos. Dentro de st.form, nada e recalculado ate clicar
    em "Planejar a semana" — mexer num controle nao dispara o solver."""
    nomes = nomes_dos_membros(catalogo)
    with st.form("semana", border=True):
        st.markdown("**1. Quem está em casa esta semana?**")
        pessoas = st.pills(
            "Pessoas",
            options=list(nomes),
            format_func=lambda m_id: nomes[m_id],
            selection_mode="multi",
            default=list(nomes),
            label_visibility="collapsed",
        )

        st.markdown("**2. Os limites da semana**")
        col1, col2, col3 = st.columns(3)
        orcamento = col1.slider(
            "Orçamento para compras (R$)", 200.0, 1500.0, 900.0, step=10.0, format="R$ %.0f",
            help="Teto do que pode ser gasto no mercado na semana (regra R12).",
        )
        tempo_por_dia = col2.slider(
            "Tempo de cozinha por dia (min)", 20, 180, 60, step=5,
            help="Soma do tempo de preparo dos pratos de um dia (regra R11).",
        )
        # Padrao 5 dias: com 7 o solver demora mais para achar a primeira
        # resposta e, num servidor lento, pode estourar o tempo limite.
        horizonte = col3.select_slider(
            "Dias planejados", options=[3, 4, 5, 6, 7], value=5,
            help="Mais dias = mais combinações. Com 7 dias a resposta leva mais tempo.",
        )

        st.markdown("**3. Aconteceu algum imprevisto?**")
        imprevisto = st.segmented_control(
            "Imprevisto",
            options=list(IMPREVISTOS),
            default=SEM_IMPREVISTO,
            required=True,
            label_visibility="collapsed",
        )

        with st.expander("Ajuste fino: o que pesa mais para você?"):
            st.caption(
                "Tudo no modelo é convertido em reais. Estes pesos multiplicam cada parte da "
                "conta; 1 é o padrão. Aumente o que você quer que o modelo evite mais."
            )
            a, b = st.columns(2)
            pesos = {
                "custo": a.slider("Gastar dinheiro", 0.0, 5.0, 1.0, key="peso_custo"),
                "desperdicio": b.slider(
                    "Jogar comida fora", 0.0, 5.0, 1.0, key="peso_desperdicio"
                ),
                "preparo": a.slider("Tempo na cozinha", 0.0, 5.0, 1.0, key="peso_preparo"),
                "desvio": b.slider(
                    "Ficar longe do alvo nutricional", 0.0, 5.0, 1.0, key="peso_desvio"
                ),
                "preferencia": a.slider(
                    "Comer pratos menos preferidos", 0.0, 5.0, 1.0, key="peso_preferencia"
                ),
                "folga": b.slider(
                    "Sair da faixa da nutricionista", 0.0, 2000.0, 1000.0, step=50.0,
                    key="peso_folga",
                    help="Penalidade por unidade fora da faixa. Alta de propósito: só sai da "
                    "faixa quando não há outro jeito.",
                ),
            }

        st.form_submit_button("Planejar a semana", type="primary", width="stretch")

    parametros = montar_parametros(
        orcamento=orcamento, tempo_por_dia=float(tempo_por_dia), pesos=pesos, horizonte=horizonte
    )
    return list(pessoas or []), parametros, imprevisto or SEM_IMPREVISTO


def pagina_planejar() -> None:
    _cabecalho(
        "Planejador",
        "Planejar a semana",
        "Configure a semana e clique em <b>Planejar a semana</b>. A primeira resposta leva "
        "de 10 a 20 segundos: o modelo está testando combinações. Repetir uma configuração "
        "já vista é instantâneo.",
    )
    catalogo_completo = carregar_catalogo_cacheado()
    pessoas, parametros, imprevisto = formulario_da_semana(catalogo_completo)

    if not pessoas:
        st.warning("Selecione pelo menos uma pessoa.")
        return

    catalogo = filtrar_membros(catalogo_completo, pessoas)
    catalogo, parametros = aplicar_imprevisto(catalogo, parametros, imprevisto)
    if imprevisto != SEM_IMPREVISTO:
        st.info(f"**{imprevisto}.** {IMPREVISTOS[imprevisto]}", icon="⚡")

    with st.spinner("Montando o melhor plano que o modelo encontrar..."):
        solucao = resolver_cacheado(catalogo, parametros)

    # "Not Solved" SEM cardapio = tempo esgotado antes de achar qualquer
    # solucao inteira (solver.solucao_e_inteira); nao ha nada para mostrar.
    if solucao.status not in ("Optimal", "Not Solved") or not solucao.cardapio:
        st.error(f"Não foi possível montar um plano: {descrever_status(solucao.status)}")
        st.markdown(
            "Tente **aumentar o orçamento**, **dar mais tempo de cozinha** ou **planejar "
            "menos dias**."
        )
        return
    if solucao.status == "Not Solved":
        st.warning(descrever_status(solucao.status))

    resultado = resultado_para_dict(solucao, catalogo, parametros)
    with st.spinner("Comparando com uma família normal..."):
        solucao_referencia = baseline_cacheado(catalogo, parametros)
    # O baseline compra por um mecanismo proprio (lotes "compra_habitual_*"),
    # que precisa da sua expansao antes de serializar — igual a Monte Carlo
    # faz (_EXPANSAO_POR_ESTRATEGIA). Sem isto: KeyError ao abrir o app.
    resultado_referencia = resultado_para_dict(
        solucao_referencia, catalogo_com_compra_habitual(catalogo, parametros), parametros
    )

    st.write("")
    desenhar_numeros(resultado, resultado_referencia)
    st.write("")

    nomes = nomes_dos_membros(catalogo)
    aba_cardapio, aba_compras, aba_despensa, aba_nutricao, aba_comparacao = st.tabs(
        ["🍽️ Cardápio", "🛒 Compras", "🥫 Despensa e descarte", "🥗 Nutrição", "⚖️ Comparação"]
    )
    with aba_cardapio:
        desenhar_cardapio(resultado, nomes)
    with aba_compras:
        st.caption("Tudo é comprado no dia 1, em embalagens inteiras: ninguém compra meio pacote.")
        desenhar_compras(resultado, parametros)
    with aba_despensa:
        esquerda, direita = st.columns(2, gap="large")
        with esquerda:
            st.markdown("**Sobra na despensa**")
            desenhar_despensa(resultado)
        with direita:
            st.markdown("**Venceu e foi para o lixo**")
            desenhar_descartes(resultado, catalogo)
    with aba_nutricao:
        st.caption(
            "Bolinha = média diária entregue · faixa verde-clara = o que a nutricionista "
            "permite · tracinho = alvo. Fora da faixa significa que o modelo não conseguiu "
            "cumprir a regra com o que havia, e mostra onde cedeu."
        )
        desenhar_aderencia(resultado, nomes)
    with aba_comparacao:
        desenhar_comparacao(resultado, resultado_referencia)
    _rodape()


def pagina_resultados() -> None:
    _cabecalho(
        "Simulação Monte Carlo",
        "O que a simulação mostrou",
        "Um caso só pode ser sorte. Por isso rodamos <b>cem semanas diferentes</b>: em "
        "cada uma, os preços variam até 15%, pode chegar visita, refeições deixam de "
        "acontecer, itens são esquecidos na compra e alguns alimentos estragam antes. As "
        "três estratégias rodam sobre os <b>mesmos</b> dados sorteados.",
    )
    with st.expander("As três estratégias comparadas"):
        st.markdown(
            "- **NutriCasa (otimizado):** o modelo completo, com as 12 regras.\n"
            "- **Família normal:** escolhe pelo gosto, compra a lista de sempre sem olhar o "
            "cardápio e não confere o que vence primeiro. É a referência da manchete.\n"
            "- **Guloso:** a mesma compra da família normal, mas sempre cozinha primeiro o "
            "que vence primeiro. Responde à pergunta: *uma regra simples já não resolveria?*"
        )
    desenhar_resultados_da_simulacao(_resultados_cacheados())
    _rodape()


_REGRAS = {
    "A · Cardápio": [
        ("R1 · Cobertura", "Cada pessoa come exatamente uma porção por refeição.",
         "alguém poderia ficar sem comer, ou comer duas vezes."),
        ("R2 · Vínculo", "Ninguém come de um prato que não foi cozinhado.",
         "o modelo serviria porções de pratos que não existem."),
        ("R3 · Limite de pratos", "No máximo 2 pratos por refeição.",
         "a casa cozinharia um prato diferente para cada pessoa."),
        ("R4 · Variedade", "Nenhuma receita mais de 2× na semana, nem em dias seguidos.",
         "o mais barato e nutritivo se repetiria a semana toda."),
    ],
    "B · Nutrição": [
        ("R5 · Faixas com folga", "Cada nutriente dentro da faixa de cada pessoa; sair dela "
         "é permitido, mas custa caro.", "a dieta da nutricionista sumiria do modelo."),
        ("R6 · Restrição individual", "Prato proibido para uma pessoa não vai para o prato dela, "
         "mas pode ir para os outros.", "o idoso hipertenso comeria prato alto em sódio."),
        ("R7 · Desvio do alvo", "Mede a distância do valor prescrito (valor absoluto "
         "linearizado).", "bastaria ficar na beirada da faixa, longe do ideal."),
    ],
    "C · Estoque e validade": [
        ("R8 · Consumo derivado", "Liga o que se come ao que sai da despensa.",
         "o cardápio usaria ingredientes que nunca foram comprados."),
        ("R9 · Balanço por lote", "Estoque de hoje = ontem + chegada − consumo − descarte.",
         "comida apareceria ou sumiria da despensa sem explicação."),
        ("R10 · Validade", "Não se come o que venceu; o que vence sai como descarte e "
         "custa dinheiro. **É o coração do projeto.**",
         "o modelo comeria tomate podre no papel e o desperdício seria sempre zero."),
    ],
    "D · Tempo e dinheiro": [
        ("R11 · Tempo de preparo", "O tempo de cozinha do dia cabe no tempo disponível.",
         "o plano exigiria horas de cozinha num dia de semana."),
        ("R12 · Orçamento", "O gasto com compras não passa do orçamento.",
         "o plano seria ótimo e impagável."),
    ],
}


def pagina_problema() -> None:
    _cabecalho(
        "A problemática",
        "Por que planejar comida é um problema de otimização",
        "O desperdício doméstico quase nunca é descuido na hora de comer. Ele nasce antes, "
        "no planejamento: compra-se por hábito, sem saber o que vai ser cozinhado, e o que "
        "vence primeiro não é usado primeiro.",
    )

    col1, col2 = st.columns([1, 1.4], gap="large")
    with col1:
        _html(
            '<div class="nc-destaque"><div class="grande">128 kg</div>'
            "<p>de alimentos desperdiçados por ano por uma família de até três pessoas no "
            "Brasil. Por pessoa, 41,6 kg.</p>"
            '<div class="fonte">Embrapa e FGV (Porpino et al., 2018). O índice da ONU de 2024 '
            "estima 94 kg por pessoa, mas conta também partes não comestíveis.</div></div>"
        )
    with col2:
        st.markdown(
            "#### Sugerir receitas não resolve\n"
            "Um app que sugere receitas responde *“o que eu poderia cozinhar?”*. A família "
            "precisa decidir **ao mesmo tempo**:\n\n"
            "- **o cardápio** da semana,\n"
            "- **quanto cada pessoa come** (a criança come menos, o idoso não pode sódio),\n"
            "- **o que comprar**, em embalagens inteiras,\n"
            "- **o que usar primeiro** da despensa, antes que vença.\n\n"
            "Uma decisão mexe nas outras: escolher um prato muda o estoque, que muda a "
            "compra, que muda o custo. Testar tudo é impossível: só a decisão “cozinhar ou "
            "não” já tem 2⁵⁰⁴ combinações em 5 dias. Por isso usamos **otimização**."
        )

    st.write("")
    st.subheader("A base: o problema da dieta de Stigler (1945)")
    col1, col2 = st.columns([1.4, 1], gap="large")
    with col1:
        st.markdown(
            "Em 1945, o economista **George Stigler** perguntou: *qual a dieta mais barata que "
            "atende às necessidades de nutrientes de uma pessoa?* Ele tinha **77 alimentos** "
            "e **9 nutrientes**. A pergunta virou um dos problemas fundadores da "
            "**programação linear**, resolvida depois com o método simplex.\n\n"
            "O NutriCasa parte exatamente dessa pergunta e acrescenta o que a vida real tem "
            "e o problema original não tinha:"
        )
    with col2:
        _html(
            _cartao(
                "Stigler (1945)",
                "1 pessoa · 77 alimentos · 9 nutrientes · objetivo: menor custo. Sem tempo, "
                "sem validade, sem família.",
            )
        )
    colunas = st.columns(3)
    dimensoes = [
        ("⏱️ Tempo", "Cada receita tem tempo de preparo e há um limite por dia (R11). O tempo "
         "também entra na conta, a R$ 0,10 por minuto."),
        ("🥬 Validade", "A despensa é controlada por lote, cada um com data de vencimento "
         "(R9). O que vence vira descarte e custa dinheiro (R10)."),
        ("👨‍👩‍👧‍👦 Família", "Quatro pessoas com faixas nutricionais, porções e restrições "
         "diferentes (R5–R7), comendo dos mesmos pratos."),
    ]
    for coluna, (titulo, texto) in zip(colunas, dimensoes, strict=False):
        with coluna:
            _html(_cartao(titulo, texto))

    st.write("")
    st.subheader("Como o modelo decide")
    st.markdown(
        "O modelo minimiza **uma única conta, toda em reais**: compras + comida que vence + "
        "tempo de cozinha + distância do alvo nutricional + pratos menos preferidos + "
        "penalidade por sair da faixa da nutricionista. Converter tudo para reais deixa "
        "explícito quanto vale cada coisa. Ninguém programou *“use primeiro o que vence "
        "antes”*: o modelo faz isso sozinho, porque **jogar comida fora custa dinheiro**."
    )

    st.write("")
    st.subheader("As 12 regras")
    st.caption("Cada regra existe por um motivo do mundo real. Abra um bloco para ver o que "
               "aconteceria se ela saísse do modelo.")
    for bloco, regras in _REGRAS.items():
        with st.expander(bloco):
            for nome, faz, se_sair in regras:
                st.markdown(f"**{nome}.** {faz}  \n*Se saísse:* {se_sair}")

    st.write("")
    st.subheader("A família de exemplo")
    catalogo = carregar_catalogo_cacheado()
    colunas = st.columns(len(catalogo.membros) or 1)
    for coluna, membro in zip(colunas, catalogo.membros.values(), strict=False):
        kcal = membro.faixas.get("kcal")
        sodio = membro.faixas.get("sodio_mg")
        detalhes = [f"Porção: {_numero(membro.fator_porcao * 100)}% da de um adulto"]
        if kcal:
            detalhes.append(f"Energia: {_numero(kcal.minimo)}–{_numero(kcal.maximo)} kcal/dia")
        if sodio:
            detalhes.append(f"Sódio: até {_numero(sodio.maximo)} mg/dia")
        if membro.tags_bloqueadas:
            bloqueios = ", ".join(NOMES_TAG.get(t, t) for t in sorted(membro.tags_bloqueadas))
            detalhes.append(f"Não come: pratos {bloqueios}")
        with coluna:
            _html(_cartao(escape(membro.nome), "<br>".join(detalhes)))
    st.caption("Faixas: Dietary Reference Intakes e Guia Alimentar para a População Brasileira; "
               "teto de sódio do idoso alinhado à Sociedade Brasileira de Cardiologia.")

    st.write("")
    st.subheader("Limitações que assumimos")
    st.markdown(
        "- Preços de **um único mercado, numa única data** (a simulação varia ±15%).\n"
        "- Numa refeição, **todos comem dos mesmos pratos** (no máximo 2).\n"
        "- **Sem reaproveitamento de sobras** entre refeições.\n"
        "- O solver roda com **tempo limite**: a resposta é a melhor encontrada, sem prova de "
        "que seja a ótima."
    )
    _rodape()


def _ler_fonte_precos() -> dict:
    try:
        return json.loads(FONTE_PRECOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ler_precos_coletados(caminho: Path = PRECOS_COLETADOS) -> dict[str, dict]:
    """Procedencia de cada preco (data/precos_coletados.csv): produto de
    referencia, link e se e coleta real ou estimativa. {} se nao existir."""
    try:
        with caminho.open(encoding="utf-8", newline="") as arquivo:
            return {linha["id"]: linha for linha in csv.DictReader(arquivo)}
    except OSError:
        return {}


def descrever_embalagem(tamanho: float, unidade: str) -> str:
    """0.015 kg -> "15 g"; 0.5 litro -> "500 ml"; 12 unidade -> "12 unidades"."""
    if unidade == "kg" and tamanho < 1:
        return f"{_numero(tamanho * 1000)} g"
    if unidade == "litro" and tamanho < 1:
        return f"{_numero(tamanho * 1000)} ml"
    texto = _numero(tamanho, 2).rstrip("0").rstrip(",")
    if unidade == "unidade":
        return f"{texto} unidade" + ("s" if tamanho != 1 else "")
    return f"{texto} {unidade}"


_FONTES_VALIDADE = [
    ("Folhosos", 4, "orientações de refrigeração para folhas frescas"),
    ("Carnes e frango frescos", 3, "segurança alimentar: 2 a 3 dias na geladeira"),
    ("Peixe fresco", 2, "vida útil curta do pescado cru"),
    ("Laticínios", 10, "rótulos e conservação após abertura"),
    ("Ovos", 21, "cerca de 3 semanas refrigerados"),
    ("Legumes e frutas", 15, "guias de conservação de hortifrúti"),
    ("Secos", 180, "rótulos de grãos, farinhas e óleos"),
    ("Enlatados", 365, "rótulos de produtos de prateleira"),
]


def pagina_ingredientes() -> None:
    _cabecalho(
        "Os dados",
        "Ingredientes e preços",
        "Os preços, validades e nutrientes que o modelo usa. O preço é o da "
        "<b>embalagem</b>, porque ninguém compra 137 g de arroz: o modelo decide quantas "
        "embalagens inteiras comprar.",
    )

    fonte = _ler_fonte_precos()
    local, data = fonte.get("local"), fonte.get("data_da_coleta")
    with st.container(border=True):
        st.markdown("**De onde vêm os preços**")
        if local and data:
            cidade = f" ({fonte['cidade']})" if fonte.get("cidade") else ""
            link = f" · [ver fonte]({fonte['link']})" if fonte.get("link") else ""
            st.markdown(f"Coletados em **{local}**{cidade}, em **{data}**.{link}")
        else:
            st.warning(
                "Local e data da coleta **a preencher** em `data/fonte_precos.json` "
                "(o grupo ainda não registrou). Até lá, trate os preços como estimativas.",
                icon="📝",
            )
        if fonte.get("por_que_este_mercado"):
            st.markdown(fonte["por_que_este_mercado"])
        if fonte.get("como_foi_coletado"):
            st.caption(fonte["como_foi_coletado"])
        precos = ler_precos_coletados()
        if precos:
            coletados = sum(1 for p in precos.values() if p["origem"] != "estimativa")
            st.caption(
                f"**{coletados} de {len(precos)}** preços coletados no site; os demais não "
                "tinham oferta disponível no dia e ficaram como estimativa (marcados na tabela)."
            )

    catalogo = carregar_catalogo_cacheado()
    ingredientes = list(catalogo.ingredientes.values())
    categorias = sorted({i.categoria for i in ingredientes})
    filtro_col, busca_col = st.columns([2, 1])
    escolhidas = filtro_col.pills(
        "Categorias",
        options=categorias,
        format_func=lambda c: NOMES_CATEGORIA.get(c, c.title()),
        selection_mode="multi",
        default=categorias,
    )
    busca = busca_col.text_input("Buscar ingrediente", placeholder="ex.: tomate")

    precos = ler_precos_coletados()
    linhas = [
        {
            "Ingrediente": i.nome,
            "Categoria": NOMES_CATEGORIA.get(i.categoria, i.categoria),
            "Embalagem": descrever_embalagem(i.tamanho_embalagem, i.unidade),
            "Preço da embalagem": _reais(i.preco_embalagem),
            "Preço por unidade": f"{_reais(i.preco_unitario)}/{i.unidade}",
            "Validade (dias)": i.validade_dias,
            "Origem do preço": "estimativa"
            if precos.get(i.id, {}).get("origem", "estimativa") == "estimativa"
            else precos[i.id]["origem"],
            "Produto de referência": precos.get(i.id, {}).get("produto", ""),
            "Link": precos.get(i.id, {}).get("link") or None,
        }
        for i in ingredientes
        if i.categoria in (escolhidas or [])
        and (not busca or busca.lower() in i.nome.lower())
    ]
    st.caption(f"{len(linhas)} de {len(ingredientes)} ingredientes")
    st.dataframe(
        pd.DataFrame(linhas),
        hide_index=True,
        column_config={
            "Preço por unidade": st.column_config.TextColumn(
                help="Preço da embalagem dividido pelo tamanho (R$/kg, R$/litro…)"
            ),
            "Link": st.column_config.LinkColumn(display_text="ver no site"),
        },
    )

    st.write("")
    st.subheader("Receitas do catálogo")
    receitas = [
        {
            "Receita": r.nome,
            "Tempo (min)": r.tempo_min,
            "Ingredientes": len(catalogo.ingredientes_da_receita(r.id)),
            "Marcações": ", ".join(NOMES_TAG.get(t, t) for t in sorted(r.tags)),
            "Preferência da família": r.preferencia,
        }
        for r in catalogo.receitas.values()
    ]
    st.dataframe(
        pd.DataFrame(receitas),
        hide_index=True,
        column_config={
            "Preferência da família": st.column_config.ProgressColumn(
                min_value=0.0, max_value=1.0, format="%.2f"
            )
        },
    )

    st.write("")
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.subheader("Validades usadas")
        st.dataframe(
            pd.DataFrame(
                [{"Categoria": c, "Dias": d, "Base": b} for c, d, b in _FONTES_VALIDADE]
            ),
            hide_index=True,
            )
        st.caption("Regra conservadora por categoria; não substitui a data do rótulo. "
                   "Detalhes em docs/fontes.md.")
    with col2:
        st.subheader("Nutrientes e dietas")
        st.markdown(
            "- **Composição dos alimentos:** Tabela Brasileira de Composição de Alimentos "
            "(**TACO**, 4ª edição, NEPA/Unicamp), convertida para as unidades de compra.\n"
            "- **Faixas por pessoa:** *Dietary Reference Intakes* (Food and Nutrition Board) "
            "e Guia Alimentar para a População Brasileira (Ministério da Saúde).\n"
            "- **Sódio do idoso hipertenso:** teto de 1.400 mg/dia, alinhado às diretrizes da "
            "Sociedade Brasileira de Cardiologia.\n"
            "- **Porção da criança:** 60% da de um adulto, pela proporção calórica diária."
        )
    _rodape()


# ===================================== main ====================================


def main() -> None:
    _injetar_css()
    if LOGO.exists():
        st.logo(str(LOGO), size="large", icon_image=str(ICONE) if ICONE.exists() else None)

    _PAGINAS.update(
        {
            "inicio": st.Page(
                pagina_inicio, title="Início", icon=":material/home:", default=True,
            ),
            "planejar": st.Page(
                pagina_planejar, title="Planejar a semana", icon=":material/restaurant_menu:",
                url_path="planejar",
            ),
            "resultados": st.Page(
                pagina_resultados, title="Resultados", icon=":material/insights:",
                url_path="resultados",
            ),
            "problema": st.Page(
                pagina_problema, title="O problema", icon=":material/menu_book:",
                url_path="problema",
            ),
            "ingredientes": st.Page(
                pagina_ingredientes, title="Ingredientes e preços",
                icon=":material/shopping_basket:", url_path="ingredientes",
            ),
        }
    )
    st.navigation(list(_PAGINAS.values()), position="top").run()


if __name__ == "__main__":
    main()
