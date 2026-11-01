"""Vazio de proposito: so existir aqui, na raiz do projeto, faz o pytest
inserir ESTE diretorio no sys.path ao coletar os testes (e o jeito
idiomatico do pytest resolver isso — carrega o conftest.py de cada
diretorio ancestral dos arquivos de teste, nao so o de dentro de
tests/).

Sem isso, `from app import ...` (tests/unidade/test_app.py e
test_demos.py) so funcionava por acidente quando eu rodava
`python -m pytest` nesta maquina — o `-m` insere o diretorio atual no
sys.path por conta propria. O CI roda `pytest` direto (sem `-m`), que
NAO faz essa insercao, e os dois modulos quebravam com
"ModuleNotFoundError: No module named 'app'".
"""
