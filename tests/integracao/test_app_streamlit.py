"""Roda o app.py DE VERDADE (Streamlit AppTest, sem navegador) — o que um
visitante ve ao abrir o link.

Existe porque os testes de tests/unidade/test_app.py testam as funcoes
separadas, e o app inteiro quebrava ao abrir (KeyError ao serializar o
baseline sem a expansao dos lotes "compra_habitual_*") sem nenhum teste
perceber. Achado no Sprint 6, preparando a hospedagem.

O app tem varias paginas (st.navigation com funcoes); o AppTest so troca
de pagina por ARQUIVO, entao cada pagina e testada chamando a funcao dela
direto num script minimo.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[2]


def _rodar_pagina(nome_funcao: str) -> AppTest:
    script = (
        f"import sys\nsys.path.insert(0, {str(RAIZ)!r})\n"
        f"import app\napp._injetar_css()\napp.{nome_funcao}()\n"
    )
    return AppTest.from_string(script, default_timeout=180).run()


def _sem_erros(app: AppTest) -> None:
    assert not app.exception, [e.value for e in app.exception]
    assert not app.error, [e.value for e in app.error]


def test_app_abre_na_pagina_inicial() -> None:
    app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60).run()
    _sem_erros(app)
    assert any("Planejar minha semana" == botao.label for botao in app.button)


@pytest.mark.parametrize(
    "pagina", ["pagina_inicio", "pagina_resultados", "pagina_problema", "pagina_ingredientes"]
)
def test_paginas_informativas_abrem_sem_erro(pagina: str) -> None:
    _sem_erros(_rodar_pagina(pagina))


@pytest.mark.lento
def test_planejador_abre_com_os_padroes_e_mostra_o_plano() -> None:
    app = _rodar_pagina("pagina_planejar")
    _sem_erros(app)
    abas = [aba.label for aba in app.tabs]
    assert len(abas) == 5
    assert any("Cardápio" in aba for aba in abas)
