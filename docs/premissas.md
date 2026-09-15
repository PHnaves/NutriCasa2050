### 1. Perfil da Família e Justificativa de Contraste
Optou-se por configurar uma família com restrições conflitantes para testar a restrição de cobertura do modelo, que permite no máximo dois pratos por refeição[cite: 2].
* **Adulto Ativo:** ~2400 kcal, traciona a necessidade de volume e alta ingestão proteica[cite: 2].
* **Adulto Sedentário:** ~1900 kcal, cria conflito direto ao exigir um teto calórico rigoroso[cite: 2].
* **Criança (8 anos):** ~1500 kcal, fator de porção de 0,6, exige o fracionamento correto do consumo[cite: 2].
* **Idoso Hipertenso:** Impõe teto de sódio e bloqueia pratos processados e temperados de baixo custo[cite: 2].

---

### 2. Coleta de Preços
* **Local da Coleta:** [PREENCHER_NOME_DO_SUPERMERCADO][cite: 2]
* **Data da Coleta:** [PREENCHER_DATA_DA_COLETA][cite: 2]

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