TABELAS = [
    "cenario",
    "execucao",
    "cardapio",
    "porcao",
    "compra",
    "descarte",
    "aderencia",
]

ORDEM_LIMPEZA_DADOS = [
    "aderencia",
    "descarte",
    "compra",
    "porcao",
    "cardapio",
    "execucao",
    "cenario",
]

SQL_CRIAR_TABELAS = [
    """
    CREATE TABLE IF NOT EXISTS cenario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rodada INTEGER NOT NULL,
        semente INTEGER NOT NULL,
        dados_sorteados TEXT,
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (rodada, semente)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS execucao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cenario_id INTEGER NOT NULL,
        estrategia TEXT NOT NULL,
        parametros TEXT,
        pesos TEXT,
        status TEXT NOT NULL,
        tempo_ms INTEGER,
        total_custo REAL,
        total_descarte REAL,
        total_preparo REAL,
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cenario_id) REFERENCES cenario(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cardapio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        execucao_id INTEGER NOT NULL,
        dia INTEGER NOT NULL,
        refeicao TEXT NOT NULL,
        prato TEXT NOT NULL,
        puxado_por_validade INTEGER NOT NULL DEFAULT 0,
        UNIQUE (execucao_id, dia, refeicao, prato),
        FOREIGN KEY (execucao_id) REFERENCES execucao(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS porcao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cardapio_id INTEGER NOT NULL,
        membro TEXT NOT NULL,
        quantidade REAL NOT NULL CHECK (quantidade >= 0),
        FOREIGN KEY (cardapio_id) REFERENCES cardapio(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS compra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        execucao_id INTEGER NOT NULL,
        ingrediente TEXT NOT NULL,
        quantidade REAL NOT NULL CHECK (quantidade >= 0),
        unidade TEXT NOT NULL,
        custo REAL,
        FOREIGN KEY (execucao_id) REFERENCES execucao(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS descarte (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        execucao_id INTEGER NOT NULL,
        ingrediente TEXT NOT NULL,
        lote TEXT NOT NULL,
        quantidade REAL NOT NULL CHECK (quantidade >= 0),
        motivo TEXT,
        FOREIGN KEY (execucao_id) REFERENCES execucao(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS aderencia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        execucao_id INTEGER NOT NULL,
        dia INTEGER NOT NULL,
        membro TEXT NOT NULL,
        regra TEXT NOT NULL,
        valor REAL NOT NULL,
        minimo REAL,
        maximo REAL,
        alvo REAL,
        desvio REAL,
        folga REAL NOT NULL,
        FOREIGN KEY (execucao_id) REFERENCES execucao(id) ON DELETE CASCADE
    )
    """,
]

SQL_CRIAR_INDICES = [
    (
        "CREATE INDEX IF NOT EXISTS ix_execucao_estrategia_cenario "
        "ON execucao (estrategia, cenario_id)"
    ),
    "CREATE INDEX IF NOT EXISTS ix_aderencia_folga ON aderencia (folga)",
    "CREATE INDEX IF NOT EXISTS ix_descarte_ingrediente ON descarte (ingrediente)",
]
