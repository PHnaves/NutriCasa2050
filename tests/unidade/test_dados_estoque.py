import os

import pandas as pd

CAMINHO_ESTOQUE = "data/estoque_inicial.csv"
CAMINHO_INGREDIENTES = "data/ingredientes.csv"


def test_lotes_referenciam_ingredientes_validos():
    df_estoque = pd.read_csv(CAMINHO_ESTOQUE)

    # Valida se os IDs do estoque existem no arquivo de ingredientes (se ele já existir no ambiente)
    if os.path.exists(CAMINHO_INGREDIENTES):
        df_ingredientes = pd.read_csv(CAMINHO_INGREDIENTES)
        ids_validos = set(df_ingredientes["id"])
        ids_estoque = set(df_estoque["ingrediente_id"])

        assert ids_estoque.issubset(ids_validos), (
            "Há lotes no estoque com ingrediente_id que não existe em ingredientes.csv"
        )
    else:
        # Validação básica de tipo se o arquivo de ingredientes ainda não estiver acessível
        assert df_estoque["ingrediente_id"].notna().all(), "Há lotes sem ingrediente_id definido."


def test_existe_lote_vencendo_em_tres_dias_ou_menos():
    df_estoque = pd.read_csv(CAMINHO_ESTOQUE)
    lotes_curtos = df_estoque[df_estoque["dia_vencimento"] <= 3]

    assert len(lotes_curtos) >= 2, (
        "A regra da S1-08 falhou: deve haver pelo menos 2 lotes vencendo cedo para testar o modelo."
    )


def test_quantidades_positivas():
    df_estoque = pd.read_csv(CAMINHO_ESTOQUE)

    assert (df_estoque["quantidade"] > 0).all(), (
        "Um ou mais lotes possuem quantidade zero ou negativa no estoque inicial."
    )
