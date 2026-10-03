from io import StringIO

import pandas as pd

# Dados base da TACO convertidos para a unidade de compra
dados_taco = """id,kcal,proteina_g,carboidrato_g,gordura_g,fibra_g,sodio_mg
1,3480,72,788,3,16,10
2,3290,214,612,15,152,20
3,3710,114,752,15,29,0
4,3600,98,760,10,23,10
5,73,6,0.5,5,0,65
6,600,30,45,30,0,500
7,7170,8,0,811,0,10000
8,3300,260,30,240,0,5800
9,1190,215,0,30,0,500
10,2120,267,0,109,0,650
11,400,11,89,1,17,20
12,1490,63,330,2,21,100
13,210,11,43,2,12,10
14,340,13,77,2,32,20
15,650,18,147,1,12,20
16,40,3,5,0,3,10
17,8840,0,0,1000,0,0
18,0,0,0,0,0,390000
19,2550,100,640,30,250,200
20,380,12,70,10,15,4500
21,3240,212,600,12,150,20
22,3710,114,752,15,29,0
23,3610,15,870,2,60,10
24,2500,20,40,250,0,400
25,3600,250,20,280,0,5500
26,600,40,50,30,0,400
27,1760,226,0,88,0,450
28,3000,140,20,260,0,11000
29,960,200,0,17,0,400
30,210,11,43,2,12,10
31,40,3,5,0,3,10
32,300,10,90,0,20,20
33,190,11,40,1,10,10
34,250,10,60,1,30,10
35,190,6,45,1,10,20
36,80,6,10,1,6,20
37,25,2,3,0,2,10
38,250,12,50,1,20,20
39,8840,0,0,1000,0,0
40,3870,0,999,0,0,10
41,0,0,0,0,0,0
42,600,30,130,10,30,8000
43,900,30,190,10,40,2500
44,800,50,140,5,50,3000
45,1100,250,0,10,0,3500
46,3800,140,660,70,90,20
47,1250,40,250,15,15,2000
48,520,2,130,1,20,10
49,890,10,220,1,20,10
50,100,9,15,1,9,20"""


def main():
    df_taco = pd.read_csv(StringIO(dados_taco))
    df_matriz = pd.read_csv("data/matriz_a.csv")

    # Cruza a matriz com a TACO pelo ID do ingrediente
    df_calculo = pd.merge(df_matriz, df_taco, left_on="ingrediente_id", right_on="id", how="inner")

    # Multiplica a composição pela quantidade da porção na receita
    nutrientes = ["kcal", "proteina_g", "carboidrato_g", "gordura_g", "fibra_g", "sodio_mg"]
    for nut in nutrientes:
        df_calculo[nut] = df_calculo[nut] * df_calculo["quantidade_por_porcao"]

    # Soma os totais agrupando por receita
    df_totais = df_calculo.groupby("receita_id")[nutrientes].sum().reset_index()

    # Transforma para o formato longo exigido (receita_id, nutriente, valor)
    df_final = df_totais.melt(
        id_vars=["receita_id"], value_vars=nutrientes, var_name="nutriente", value_name="valor"
    )

    df_final.to_csv("data/nutrientes.csv", index=False)
    print("Arquivo data/nutrientes.csv gerado com sucesso!")


if __name__ == "__main__":
    main()
