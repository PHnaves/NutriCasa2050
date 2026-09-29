import json

CAMINHO_PERFIS = "data/perfis/familia_demo.json"


def carregar_dados():
    with open(CAMINHO_PERFIS, encoding="utf-8") as f:
        return json.load(f)


def test_familia_tem_quatro_membros():
    dados = carregar_dados()
    assert len(dados) == 4, "A família deve conter exatamente 4 membros configurados."


def test_toda_faixa_tem_minimo_menor_que_maximo():
    dados = carregar_dados()
    for membro in dados:
        for nutriente, limites in membro["faixas"].items():
            assert limites["min"] < limites["max"], (
                f"No nutriente {nutriente} do membro {membro['id']}, min não é menor que max."
            )


def test_alvo_dentro_da_faixa():
    dados = carregar_dados()
    for membro in dados:
        for nutriente, limites in membro["faixas"].items():
            assert limites["min"] <= limites["alvo"] <= limites["max"], (
                f"O alvo do nutriente {nutriente} do membro {membro['id']} está fora da faixa."
            )


def test_familia_tem_contraste():
    dados = carregar_dados()
    alvos_kcal = [membro["faixas"]["kcal"]["alvo"] for membro in dados]

    maior_kcal = max(alvos_kcal)
    menor_kcal = min(alvos_kcal)

    # Valida se a maior faixa calórica é pelo menos 40% maior que a menor
    assert maior_kcal >= (menor_kcal * 1.4), (
        "O contraste da família falhou. A diferença entre a maior "
        "e a menor dieta precisa ser de pelo menos 40%."
    )
