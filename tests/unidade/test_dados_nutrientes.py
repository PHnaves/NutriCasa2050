import pandas as pd

CAMINHO = "data/nutrientes.csv"


def test_todas_as_receitas_tem_seis_nutrientes():
    df = pd.read_csv(CAMINHO)
    contagem = df.groupby("receita_id")["nutriente"].nunique()

    for receita, qtd in contagem.items():
        assert qtd == 6, f"A receita {receita} possui {qtd} nutrientes em vez de 6."


def test_nutrientes_sem_valor_negativo():
    df = pd.read_csv(CAMINHO)
    negativos = df[df["valor"] < 0]

    assert negativos.empty, f"Encontrados valores negativos: \n{negativos}"


def test_calorias_por_porcao_plausiveis():
    df = pd.read_csv(CAMINHO)
    # Filtra apenas as linhas referentes a calorias
    calorias = df[df["nutriente"] == "kcal"]

    # O teste mais importante da tarefa, barra erros de unidade (kg vs g)
    for _, linha in calorias.iterrows():
        valor = linha["valor"]
        receita = linha["receita_id"]
        assert 100 <= valor <= 1500, (
            f"Calorias implausíveis na receita {receita}: {valor} kcal por porção."
        )
