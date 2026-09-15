import os


def test_premissas_existe_e_formatado():
    """Verifica se o arquivo de premissas foi criado e possui todas as seções obrigatórias."""
    caminho_arquivo = "docs/premissas.md"
    assert os.path.exists(caminho_arquivo), "Erro: Arquivo docs/premissas.md não encontrado."
    
    with open(caminho_arquivo, encoding="utf-8") as f:
        conteudo = f.read().lower()
        
    termos_obrigatorios = [
        "adulto ativo", 
        "sedentário", 
        "criança", 
        "idoso", 
        "coleta de preços", 
        "tempo_min", 
        "vegetariano", 
        "sem_gluten"
    ]
    
    for termo in termos_obrigatorios:
        assert termo in conteudo, f"Erro: Termo obrigatório '{termo}' foi removido das premissas."