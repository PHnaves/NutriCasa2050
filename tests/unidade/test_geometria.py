"""O desenho da geometria por tras do modelo (card S5-03) — o otimo de
um LP sempre cai num vertice da regiao viavel. Teorema fundamental da
programacao linear, verificado na pratica.
"""
from __future__ import annotations

from pulp import PULP_CBC_CMD, LpStatus

from nutricasa2050.analise.graficos import (
    calcular_regiao_viavel,
    grafico_regiao_viavel,
    modelo_reduzido_2d,
    restricoes_do_modelo_reduzido,
)


def test_regiao_viavel_tem_pelo_menos_tres_vertices() -> None:
    vertices = calcular_regiao_viavel(restricoes_do_modelo_reduzido())

    assert len(vertices) >= 3


def test_otimo_coincide_com_um_vertice() -> None:
    problema, variaveis = modelo_reduzido_2d()
    problema.solve(PULP_CBC_CMD(msg=False))
    assert LpStatus[problema.status] == "Optimal"
    otimo = (variaveis["x1"].varValue, variaveis["x2"].varValue)

    vertices = calcular_regiao_viavel(restricoes_do_modelo_reduzido())

    assert any(
        abs(otimo[0] - v[0]) < 1e-6 and abs(otimo[1] - v[1]) < 1e-6 for v in vertices
    )


def test_grafico_cria_o_arquivo(tmp_path) -> None:
    caminho = tmp_path / "regiao_viavel.png"

    grafico_regiao_viavel(caminho)

    assert caminho.exists()
    assert caminho.stat().st_size > 0
