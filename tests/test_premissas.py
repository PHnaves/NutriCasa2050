import os

def test_arquivo_premissas_existe_e_tem_conteudo():
    """Verifica se o arquivo de premissas foi criado e possui as justificativas."""
    caminho_arquivo = "docs/premissas.md"
    
    assert os.path.exists(caminho_arquivo), "Erro: Arquivo docs/premissas.md não encontrado."
    
    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        conteudo = f.read()
    
    assert len(conteudo) > 50, "Erro: O arquivo de premissas está muito curto."
    assert "adulto ativo" in conteudo.lower(), "Erro: Perfil do adulto ativo ausente."