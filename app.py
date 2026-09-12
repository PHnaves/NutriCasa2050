import streamlit as st

from nutricasa2050.config import database_path, environment

st.title("NutriCasa 2050")
st.caption("Esqueleto inicial — a simulacao ainda vai ser construida aqui.")

st.subheader("Configuracao carregada")
st.write("Ambiente:", environment())
st.write("Banco de dados:", database_path())
