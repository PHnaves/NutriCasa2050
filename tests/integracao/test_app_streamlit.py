"""Roda o app.py DE VERDADE (Streamlit AppTest, sem navegador) com os
parametros padrao — o que um visitante ve ao abrir o link.

Existe porque os testes de tests/unidade/test_app.py testam as funcoes
separadas, e o app inteiro quebrava ao abrir (KeyError ao serializar o
baseline sem a expansao dos lotes "compra_habitual_*") sem nenhum teste
perceber. Achado no Sprint 6, preparando a hospedagem.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "app.py"


@pytest.mark.lento
def test_app_abre_com_os_padroes_e_mostra_cardapio() -> None:
    app = AppTest.from_file(str(APP), default_timeout=180).run()

    assert not app.exception, [e.value for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    assert [aba.label for aba in app.tabs] == ["Planejar a semana", "Resultados da simulacao"]
    rotulos = {metrica.label for metrica in app.metric}
    assert "Custo total" in rotulos  # a aba da semana desenhou os numeros do cardapio
