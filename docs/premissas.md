### 1. Perfil da Família e Justificativa de Contraste
Optou-se por configurar uma família com restrições conflitantes para testar a restrição de cobertura do modelo, que permite no máximo dois pratos por refeição[cite: 2].
* **Adulto Ativo:** ~2400 kcal, traciona a necessidade de volume e alta ingestão proteica[cite: 2].
* **Adulto Sedentário:** ~1900 kcal, cria conflito direto ao exigir um teto calórico rigoroso[cite: 2].
* **Criança (8 anos):** ~1500 kcal, fator de porção de 0,6, exige o fracionamento correto do consumo[cite: 2].
* **Idoso Hipertenso:** Impõe teto de sódio e bloqueia pratos processados e temperados de baixo custo[cite: 2].

---

### 2. Coleta de Preços
* **Local da Coleta:** Atacadão, loja online (atacadao.com.br), do Grupo Carrefour Brasil, a maior rede supermercadista do país no Ranking ABRAS 2025. Usamos a loja online padrão, sem CEP informado. O Carrefour Mercado bloqueia consulta automatizada; o catálogo do Atacadão é público.
* **Data da Coleta:** 05/11/2026.
* **Regra de escolha (igual para todos os itens):** entre os produtos disponíveis que correspondem ao ingrediente, o de menor preço por kg, litro ou unidade, em embalagem de varejo (até cerca de 1,2 kg) ou vendido por peso. Embalagem maior só quando é a única oferta (farinha de trigo, 5 kg). O tamanho da embalagem passou a ser o do produto real (ex.: pimenta-do-reino em 15 g, molho de tomate em 300 g).
* **Resultado:** 42 dos 50 preços coletados. Alface, cheiro-verde, abobrinha, berinjela, couve, brócolis, sal refinado e óleo de soja não tinham oferta disponível no dia e mantêm o preço anterior, marcado como **estimativa**.
* **Procedência item a item** (produto, preço, tamanho e link): `data/precos_coletados.csv`. A página "Ingredientes e preços" do app mostra essa tabela.

---

### 3. Padrão de Cadastro de Receitas
Todas as receitas cadastradas devem seguir o formato estrito abaixo[cite: 2]:
* **id:** minúsculo, sem espaço, com underline (ex: arroz_ovo)[cite: 2].
* **tempo_min:** minutos de preparo, realista[cite: 2].
* **tags_dieta:** separadas por ponto e vírgula[cite: 2].
* **preferencia:** nota decimal de 0 a 1[cite: 2].
* **quantidade_por_porcao:** na unidade do ingrediente, calculada por pessoa[cite: 2].

---

### 4. Lista Fixa de Tags de Dieta
Para evitar falhas de execução no solver (Restrição R6), não é permitido inventar novas tags[cite: 2]. Apenas as seguintes devem ser utilizadas:
* `vegetariano`[cite: 2]
* `sem_gluten`[cite: 2]
* `sem_lactose`[cite: 2]
* `alto_sodio`[cite: 2]
