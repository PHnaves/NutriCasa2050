import argparse
import os

from nutricasa2050.persistencia.banco import (
    ConfiguracaoBanco,
    ErroDeBanco,
    apagar_schema,
    criar_engine,
    criar_schema,
)


def _carregar_cfg() -> ConfiguracaoBanco:
    return ConfiguracaoBanco(
        ambiente=os.environ.get("NUTRICASA2050_ENVIRONMENT", "development"),
        url_banco_principal=os.environ.get(
            "NUTRICASA2050_DB_URL", "sqlite:///var/nutricasa2050.db"
        ),
        url_banco_teste=os.environ.get(
            "NUTRICASA2050_TEST_DB_URL", "sqlite:///var-test/nutricasa2050_test.db"
        ),
    )


def _url_ativa(cfg: ConfiguracaoBanco) -> str:
    if cfg.ambiente == "test":
        return cfg.url_banco_teste
    return cfg.url_banco_principal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operacoes de persistencia")
    parser.add_argument("acao", choices=["criar", "resetar", "info"])
    parser.add_argument(
        "--url",
        default=None,
        help="URL opcional para sobrepor o banco ativo da configuracao",
    )
    args = parser.parse_args(argv)

    cfg = _carregar_cfg()
    url = args.url or _url_ativa(cfg)

    try:
        if args.acao == "info":
            print(f"Ambiente: {cfg.ambiente}")
            print(f"Banco ativo: {url}")
            return 0

        if args.acao == "resetar" and cfg.ambiente == "production":
            raise ErroDeBanco("Acao resetar recusada em producao.")

        engine = criar_engine(cfg, url)

        if args.acao == "criar":
            criar_schema(engine)
            print(f"Schema criado em {url}")
            return 0

        if args.acao == "resetar":
            apagar_schema(engine)
            criar_schema(engine)
            print(f"Schema resetado em {url}")
            return 0

        return 1
    except ErroDeBanco as erro:
        print(f"Erro: {erro}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
