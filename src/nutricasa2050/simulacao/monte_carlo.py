"""Monte Carlo (card S4-04): roda o programa centenas de vezes, cada vez
com os dados um pouco diferentes (cenarios.py), para ver se o resultado
se sustenta ou foi sorte com um conjunto especifico de dados.
"""
from __future__ import annotations

import argparse
import time
from dataclasses import asdict

from nutricasa2050.dados.carga import carregar_catalogo
from nutricasa2050.dominio import Catalogo, Parametros
from nutricasa2050.otimizacao.solver import resolver
from nutricasa2050.persistencia.banco import ConfiguracaoBanco, EngineSQLite, conexao, criar_engine
from nutricasa2050.persistencia.repositorio import gravar_cenario, gravar_resultado_completo
from nutricasa2050.serializacao import resultado_para_dict
from nutricasa2050.simulacao.baselines import (
    baseline_guloso,
    baseline_humano,
    catalogo_com_compra_habitual,
)
from nutricasa2050.simulacao.cenarios import aplicar_cenario, gerar_cenario

# As TRES estrategias comparadas (card S4-02/03/S2-09) — sempre rodadas
# sobre os MESMOS dados perturbados (ver rodar_um_cenario). A ordem aqui
# nao importa para o resultado, so para a ordem de gravacao no banco.
ESTRATEGIAS = {
    "otimizado": resolver,
    "humano": baseline_humano,
    "guloso": baseline_guloso,
}

# resultado_para_dict (serializacao.py) ja expande sozinho os lotes de
# compra do OTIMIZADO (restricoes.preparar_catalogo, S3-01) — mas os
# baselines usam um mecanismo de compra proprio ("compra_habitual_*",
# ver baselines.py), que precisa da SUA PROPRIA expansao antes de
# serializar, senao um descarte referenciando esse lote da KeyError.
_EXPANSAO_POR_ESTRATEGIA = {
    "otimizado": lambda catalogo, parametros: catalogo,
    "humano": catalogo_com_compra_habitual,
    "guloso": catalogo_com_compra_habitual,
}


def _proxima_rodada(engine: EngineSQLite) -> int:
    """Le o maior `rodada` ja gravado e soma 1 — assim, rodar a Monte
    Carlo de novo contra o MESMO banco persistido (fora dos testes) nao
    colide com a UNIQUE(rodada, semente) de uma rodada anterior."""
    with conexao(engine) as conn:
        linha = conn.execute("SELECT COALESCE(MAX(rodada), -1) AS maximo FROM cenario").fetchone()
        return linha["maximo"] + 1


def rodar_um_cenario(
    engine: EngineSQLite,
    catalogo: Catalogo,
    parametros: Parametros,
    semente: int,
    rodada: int = 0,
) -> dict:
    """Gera UM cenario a partir da semente, aplica a perturbacao UMA vez
    e roda as tres estrategias sobre o MESMO catalogo/parametros
    perturbados — se cada estrategia rodasse sobre dados diferentes, a
    comparacao entre elas (e a manchete da apresentacao) seria falsa.
    """
    cenario_obj = gerar_cenario(semente)
    catalogo_perturbado, parametros_perturbado = aplicar_cenario(catalogo, parametros, cenario_obj)

    cenario_id = gravar_cenario(
        engine,
        {"rodada": rodada, "semente": semente, "dados_sorteados": asdict(cenario_obj)},
    )

    resumos: dict[str, dict] = {}
    for nome_estrategia, funcao in ESTRATEGIAS.items():
        solucao = funcao(catalogo_perturbado, parametros_perturbado)
        catalogo_para_serializar = _EXPANSAO_POR_ESTRATEGIA[nome_estrategia](
            catalogo_perturbado, parametros_perturbado
        )
        resultado = resultado_para_dict(solucao, catalogo_para_serializar, parametros_perturbado)
        gravar_resultado_completo(
            engine,
            resultado,
            nome_estrategia,
            {"horizonte": parametros_perturbado.horizonte},
            cenario_id=cenario_id,
        )
        resumos[nome_estrategia] = resultado["resumo"]

    return {"cenario_id": cenario_id, "semente": semente, "resumos": resumos}


def rodar_monte_carlo(
    engine: EngineSQLite,
    catalogo: Catalogo,
    parametros: Parametros,
    n_cenarios: int = 500,
    semente_inicial: int = 0,
) -> dict:
    """O laco principal: mostra progresso a cada 50 cenarios (rodar sem
    sinal de vida por minutos parece travado), e um cenario que falha
    NAO para os demais — so e contado e registrado."""
    rodada = _proxima_rodada(engine)
    inicio = time.monotonic()
    sucesso = 0
    falhas: list[dict] = []

    for indice in range(n_cenarios):
        semente = semente_inicial + indice
        try:
            rodar_um_cenario(engine, catalogo, parametros, semente, rodada=rodada)
            sucesso += 1
        except Exception as exc:  # noqa: BLE001 — um cenario ruim nao pode parar os outros 499
            falhas.append({"semente": semente, "erro": str(exc)})

        processados = indice + 1
        if processados % 50 == 0 or processados == n_cenarios:
            print(f"... {processados}/{n_cenarios} cenarios processados")

    return {
        "rodada": rodada,
        "total": n_cenarios,
        "sucesso": sucesso,
        "falhas": len(falhas),
        "detalhe_falhas": falhas,
        "tempo_segundos": time.monotonic() - inicio,
    }


def _carregar_cfg() -> ConfiguracaoBanco:
    import os

    return ConfiguracaoBanco(
        ambiente=os.environ.get("NUTRICASA2050_ENVIRONMENT", "development"),
        url_banco_principal=os.environ.get(
            "NUTRICASA2050_DB_URL", "sqlite:///var/nutricasa2050.db"
        ),
        url_banco_teste=os.environ.get(
            "NUTRICASA2050_TEST_DB_URL", "sqlite:///var-test/nutricasa2050_test.db"
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Roda a simulacao Monte Carlo do NutriCasa 2050")
    parser.add_argument("--n", type=int, default=500, help="numero de cenarios (padrao: 500)")
    parser.add_argument("--semente-inicial", type=int, default=0)
    parser.add_argument("--horizonte", type=int, default=5)
    parser.add_argument("--orcamento", type=float, default=500.0)
    args = parser.parse_args(argv)

    cfg = _carregar_cfg()
    url = cfg.url_banco_teste if cfg.ambiente == "test" else cfg.url_banco_principal
    engine = criar_engine(cfg, url)

    catalogo = carregar_catalogo()
    parametros = Parametros(
        horizonte=args.horizonte, refeicoes_por_dia=3, orcamento=args.orcamento, dias_compra=(1,)
    )

    resumo = rodar_monte_carlo(
        engine, catalogo, parametros, n_cenarios=args.n, semente_inicial=args.semente_inicial
    )
    print(
        f"Rodada {resumo['rodada']}: {resumo['sucesso']}/{resumo['total']} cenarios ok, "
        f"{resumo['falhas']} falharam, {resumo['tempo_segundos']:.1f}s no total."
    )
    return 0 if resumo["falhas"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
