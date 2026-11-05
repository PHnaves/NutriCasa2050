# Hospedagem do NutriCasa 2050

Este guia mostra três jeitos de colocar o app no ar, do mais simples ao mais
controlado. O app é **um processo Streamlit só**: não tem API separada nem
banco servidor. Ele lê os CSV de `data/` e, na aba "Resultados da simulação",
o arquivo SQLite `var/results.db`, que vai versionado no repositório.

## O que já está pronto no repositório

| Item | Onde | Para quê |
|---|---|---|
| Dependências com versão fixa | `requirements.txt` | o servidor instala exatamente o que foi testado |
| `import nutricasa2050` sem `pip install -e .` | topo do `app.py` (põe `src/` no `sys.path`) | o Streamlit Cloud só roda `pip install -r requirements.txt` |
| Tema com as cores da logo | `.streamlit/config.toml` | é lido automaticamente |
| Resultados da Monte Carlo | `var/results.db` (exceção no `.gitignore`) | a aba de resultados funciona sem rodar a simulação no servidor |
| Imagem Docker | `Dockerfile` (+ `publicar.yml` publica no ghcr.io a cada tag) | hospedagem em qualquer lugar que rode container |
| Solver | CBC embutido no PuLP 3.3.2 | não precisa instalar nada no sistema |

Antes de publicar, confira localmente:

```bash
pip install -r requirements.txt
streamlit run app.py      # http://localhost:8501, as duas abas devem abrir
```

## Opção 1 — Streamlit Community Cloud (gratuito, recomendado)

1. Faça o merge na `main` e garanta que `var/results.db` está commitado.
2. Entre em <https://share.streamlit.io> com a conta do GitHub dona do
   repositório e autorize o acesso.
3. **Create app**, depois **Deploy a public app from GitHub**:
   - Repository: `PHnaves/NutriCasa2050`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: escolha, por exemplo, `nutricasa2050`
4. Em **Advanced settings**:
   - **Python version: 3.11.** É a versão do CI e do Docker. O padrão do
     Streamlit Cloud é a mais nova, e não é ela que foi testada.
   - **Secrets** (opcional): `NUTRICASA2050_SOLVER_TIMEOUT = "20"`. Segredos
     no nível raiz viram variáveis de ambiente, e o `config.py` as lê. O
     padrão é 10 s. Os servidores gratuitos são mais lentos que um notebook,
     e 20 s reduz a chance de o tempo acabar antes de existir um cardápio.
5. **Deploy**. O primeiro build leva alguns minutos.
6. Cole o link no README, no lugar do aviso "ainda não há link público", e
   no card S5-08.

### Repositório privado

O Streamlit Cloud aceita repositório privado: o app nasce privado e só abre
para quem for convidado pelo e-mail (botão **Share**). O plano gratuito
permite **um app privado por vez**. Para uma banca ou feira com visitantes
sem login, o app precisa ser público. Em **Settings, Sharing** dá para
tornar o app público e manter o código privado no GitHub.

### Limites que importam aqui

- **CPU compartilhada.** Cada clique leva de 10 a 20 s para resolver. O app
  guarda as respostas em cache (`st.cache_data`), então voltar a uma
  configuração já vista é instantâneo. Na apresentação, clique uma vez em
  cada botão antes, para "aquecer" o cache.
- **O app dorme** depois de alguns dias sem acesso. Abra o link na véspera.
- **Disco temporário.** O que o app grava some quando ele reinicia. Não há
  problema: o app hospedado só lê dados.

## Opção 2 — Imagem Docker publicada (qualquer servidor)

Cada tag `vX.Y` enviada ao GitHub gera
`ghcr.io/phnaves/nutricasa2050:<tag>` e `:latest`, pelo workflow
`publicar.yml`. Em qualquer máquina com Docker:

```bash
docker run -d -p 8501:8501 --restart unless-stopped \
  -e NUTRICASA2050_SOLVER_TIMEOUT=20 \
  ghcr.io/phnaves/nutricasa2050:latest
```

Funciona em VPS, Render, Railway, Fly.io, Google Cloud Run e Hugging Face
Spaces (SDK "Docker", porta 8501). Se o repositório for privado, o pacote
no ghcr.io também nasce privado: torne-o público em **GitHub, Packages,
nutricasa2050, Package settings**, ou faça `docker login ghcr.io` no
servidor.

## Opção 3 — Rede local, no dia da feira (plano B sem internet)

```bash
make dev        # ou: docker compose up
```

O terminal mostra a "Network URL" (`http://<ip-da-máquina>:8501`). Qualquer
celular na mesma rede Wi-Fi abre o app por ela.

## Atualizar os números publicados

```bash
make resultados             # 100 cenários, timeout 30 s (cerca de 55 min) no banco principal
make publicar-resultados    # copia var/nutricasa2050.db para var/results.db
git add var/results.db && git commit -m "chore: atualiza resultados publicados"
```

Depois atualize as tabelas de `docs/resultados.md` e `docs/relatorio.md`.

## Checklist antes do congelamento (card S6-07)

- [ ] CI verde na `main`
- [ ] `var/results.db` commitado
- [ ] App no ar (opção 1 ou 2) e link no README e no card S5-08
- [ ] `git tag v1.0 && git push --tags` (publica a imagem no ghcr.io)
- [ ] `docker run ghcr.io/phnaves/nutricasa2050:v1.0` testado numa máquina limpa
- [ ] Backup do repositório (zip ou clone em outro lugar)
