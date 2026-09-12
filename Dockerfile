# ---------------------------------------------------------------------------
# NutriCasa 2050 — imagem de desenvolvimento
#
# Projeto sem ambiente de producao: uma unica imagem, com tudo que e
# necessario para rodar o app E para testar (ruff, pytest, pasta tests/).
#
#   docker build -t nutricasa2050:dev .
# ---------------------------------------------------------------------------

FROM python:3.11-slim

# PYTHONUNBUFFERED        -> print aparece na hora no log
# PYTHONDONTWRITEBYTECODE -> nao cria __pycache__ dentro do container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# coinor-cbc: o solver. O PuLP traz um binario proprio, mas em imagem slim
#             ele as vezes falha. Instalar pelo apt e a rede de seguranca.
# curl:       usado pelo HEALTHCHECK mais abaixo.
RUN apt-get update && apt-get install -y --no-install-recommends \
        coinor-cbc \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# As dependencias vem ANTES do codigo de proposito. O Docker guarda cada
# passo em cache: mudar uma linha de src/ nao reinstala o pandas.
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt

# Instala o pacote em modo editavel para que "import nutricasa" funcione
# de qualquer lugar, sem mexer em sys.path.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install -e . --no-deps

COPY data/ ./data/
COPY app.py ./
COPY tests/ ./tests/

# Pastas onde os DOIS bancos SQLite vivem. Sao os pontos de montagem dos
# volumes declarados no docker-compose.yml.
#   /app/var       -> banco principal
#   /app/var-test  -> banco de teste
RUN mkdir -p /app/var /app/var-test

EXPOSE 8501

# Permite ao CI e ao docker-compose verificarem que o container SUBIU,
# e nao apenas que a imagem foi construida.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

# --server.headless=false
#     Sem isso o Streamlit se acha um servidor publico: alem das duas URLs
#     uteis, ele consulta um servico externo para descobrir o IP da internet
#     e anuncia uma terceira, a "External URL". Esse endereco nao abre — o
#     roteador nao encaminha a porta 8501 para esta maquina — entao so
#     confunde. Este app roda na maquina de quem desenvolve, nao num
#     servidor: dizer isso ao Streamlit deixa apenas a Local e a Network URL.
# --server.showEmailPrompt=false
#     Fora do modo headless o Streamlit pede um e-mail na primeira execucao.
#     Dentro do container nao ha ninguem para responder.
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=false", \
     "--server.showEmailPrompt=false"]
