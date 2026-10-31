# Formulação Matemática — NutriCasa 2050

> Entrega mais importante do projeto. Qualquer um dos três integrantes da
> equipe pode ser chamado para explicar qualquer restrição deste documento na
> avaliação individual de novembro — por isso cada restrição vem acompanhada
> do que aconteceria se ela fosse removida, não só do que ela faz.

Este documento formaliza o problema de programação linear (com variáveis
binárias e inteiras, portanto um PLIM — Problema Linear Inteiro Mista) que o
NutriCasa 2050 resolve a cada cenário simulado: decidir o cardápio da semana
de uma família, as porções de cada membro, a lista de compras e o descarte de
estoque, minimizando custo, desperdício, tempo de preparo e desvio
nutricional, sem violar as restrições de dieta, orçamento e tempo.

A implementação usa [PuLP](https://coin-or.github.io/pulp/) com o solver CBC
(ver `notebooks/00_stigler.ipynb` para o protótipo mais simples que já roda no
projeto, e `.github/workflows/ci.yml` para a prova de que o CBC funciona
dentro do container).

---

## 1. Conjuntos

| Conjunto | Significado | Tamanho atual nos dados |
|---|---|---|
| `I` | Ingredientes do catálogo (`data/ingredientes.csv`) | 50 |
| `R` | Receitas cadastradas (`data/receitas.csv`) | 24 |
| `D` | Dias do horizonte de planejamento (ex.: 1 semana) | 7 (configurável) |
| `M` | Refeições do dia (café da manhã, almoço, jantar) | 3 |
| `P` | Membros da família (`data/perfis/familia_demo.json`) | 4 |
| `N` | Nutrientes acompanhados (`data/nutrientes.csv`) | 6 (`kcal`, `proteina_g`, `carboidrato_g`, `gordura_g`, `sodio_mg`, `fibra_g`) |
| `L` | Lotes em estoque, cada um com ingrediente e validade próprios (`data/estoque_inicial.csv`) | 15 (crescem a cada compra simulada) |
| `C` | Dias de compra permitidos, `C ⊆ D` | 1 na implementação atual (compra única no início do horizonte — é por isso que a tabela `compra` do banco, card S1-14, não tem coluna `dia`) |
| `T` | Tags de dieta fixas (`vegetariano`, `sem_gluten`, `sem_lactose`, `alto_sodio`) | 4 |

Índices usados abaixo: `i ∈ I`, `r ∈ R`, `d ∈ D`, `m ∈ M`, `p ∈ P`, `n ∈ N`,
`l ∈ L`, `t ∈ T`.

---

## 2. Parâmetros

Todos vêm dos CSVs de dados ou do JSON de perfis — nada é "chutado" dentro do
modelo.

| Parâmetro | Origem | Significado |
|---|---|---|
| `a[r,i]` | `matriz_a.csv` (`quantidade_por_porcao`) | quantidade do ingrediente `i` exigida por **uma porção** da receita `r` |
| `v[r,n]` | `nutrientes.csv` (`valor`) | quantidade do nutriente `n` entregue por **uma porção** da receita `r` (já calculado a partir da TACO, card S1-07) |
| `preco[i]` | `ingredientes.csv` (`preco_embalagem`) | preço de **uma embalagem** do ingrediente `i` |
| `tam[i]` | `ingredientes.csv` (`tamanho_embalagem`) | quantidade que vem em uma embalagem de `i`, na mesma unidade de `a[r,i]` |
| `fp[p]` | perfil (`fator_porcao`) | fator de porção do membro `p` (1,0 adulto padrão; 0,6 criança) |
| `bloq[p,t] ∈ {0,1}` | perfil (`tags_bloqueadas`) | 1 se o membro `p` não pode consumir receitas com a tag `t` |
| `tag[r,t] ∈ {0,1}` | receitas (`tags_dieta`) | 1 se a receita `r` carrega a tag `t` |
| `min[p,n]`, `max[p,n]`, `alvo[p,n]` | perfil (`faixas`) | faixa mínima, máxima e alvo diário do nutriente `n` para o membro `p` |
| `tempo[r]` | receitas (`tempo_min`) | minutos de preparo da receita `r` |
| `pref[r]` | receitas (`preferencia`) | nota de 0 a 1 do quanto a família gosta da receita `r` |
| `estoque0[l]`, `ing[l]`, `venc[l]` | `estoque_inicial.csv` | quantidade inicial, ingrediente e dia de vencimento (relativo ao início do horizonte) do lote `l` |
| `B` | orçamento combinado para o horizonte | teto de gasto em R$ |
| `Tmax` | tempo disponível da família por refeição | minutos |
| `K` | limite de pratos distintos por refeição (regra da família: **2**) | — |
| `Vmin` | número mínimo de receitas distintas no horizonte | — |
| `w_custo, w_desc, w_prep, w_desv, w_pref, w_sobra` | pesos/fatores de conversão da função objetivo | ver Seção 4 |

---

## 3. Variáveis de decisão

Seis famílias de variáveis, cada uma alimentando diretamente uma das tabelas
de resultado do banco criado no card S1-14 (`cardapio`, `compra`, `porcao`,
`descarte`, `aderencia`):

| Variável | Tipo | Índices | O que representa |
|---|---|---|---|
| `x[r,d,m]` | **binária** | `r∈R, d∈D, m∈M` | 1 se a receita `r` é preparada no dia `d`, refeição `m` → tabela `cardapio` |
| `n[i]` | **inteira**, `≥0` | `i∈I` | número de embalagens do ingrediente `i` compradas no horizonte |
| `q[i]` | **contínua**, `≥0` | `i∈I` | quantidade comprada do ingrediente `i` (ligada a `n[i]`, ver R12) → tabela `compra` |
| `y[p,r,d,m]` | **contínua**, `≥0` | `p∈P, r∈R, d∈D, m∈M` | porção da receita `r` que o membro `p` consome no dia `d`, refeição `m` → tabela `porcao` |
| `w[l,d]` | **contínua**, `≥0` | `l∈L, d∈D` | quantidade do lote `l` descartada no dia `d` (venceu ou sobrou) → tabela `descarte` |
| `s⁺[p,n,d]`, `s⁻[p,n,d]` | **contínua**, `≥0` | `p∈P, n∈N, d∈D` | desvio positivo/negativo do nutriente `n` do membro `p` em relação ao alvo no dia `d` → tabela `aderencia` (coluna `desvio`, e a `folga` de R5 vem da mesma família) |

> Duas variáveis auxiliares que **não** entram nessa lista de seis porque são
> derivadas das variáveis acima só para linearizar restrições — explicadas na
> Seção 6: `u[r]` (binária, usada em R4) e a decomposição `s⁺/s⁻` em si
> (usada em R5 e R7).

---

## 4. Função objetivo

```
min   w_custo · Σ_i preco[i]·n[i]
    + w_desc  · Σ_{l,d} (preco[ing[l]]/tam[ing[l]]) · w[l,d]
    + w_prep  · Σ_{r,d,m} tempo[r] · x[r,d,m]
    + w_desv  · Σ_{p,n,d} (s⁺[p,n,d] + s⁻[p,n,d])
    - w_pref  · Σ_{r,d,m} pref[r] · x[r,d,m]
    + w_sobra · Σ_i (preco[i]/tam[i]) · (n[i]·tam[i] − q[i])
```

Os seis termos, em ordem: **custo de compra**, **custo do desperdício**
(cada unidade descartada valorizada ao preço por unidade de compra do seu
ingrediente), **custo do tempo de preparo**, **penalidade do desvio
nutricional**, **bônus de preferência** (subtraído, pois é minimização: mais
preferência reduz o objetivo) e **custo da sobra de embalagem** (o que foi
comprado em pacote fechado mas não chegou a ser usado no horizonte — dinheiro
parado na despensa).

**Por que todos precisam estar em reais antes de somar:** cada termo nasce
numa unidade diferente — R$, quilos/litros descartados, minutos, gramas ou
miligramas de desvio nutricional, uma nota subjetiva de 0 a 1. Somar minutos
com miligramas de sódio direto não tem significado matemático nem prático.
Os pesos `w_*` não são só "importância relativa": alguns literalmente
convertem unidade (ex.: `w_prep` tem unidade R$/minuto, um custo-hora
assumido para o tempo da família) para que a soma inteira vire uma única
grandeza — reais — comparável e minimizável.

---

## 5. As doze restrições

### Bloco A — estrutura do cardápio

**R1 — Cobertura.** `Σ_r x[r,d,m] ≥ 1` para todo `d, m`.
Garante que toda refeição do horizonte tem pelo menos um prato servido.
*Se fosse removida:* o solver poderia deixar refeições vazias sempre que
qualquer prato custasse mais do que zero — a solução "mais barata" seria a
família não comer, o que é absurdo para uma simulação de alimentação real e
tornaria toda a função objetivo inútil como medida de custo de vida.

**R2 — Vínculo.** `y[p,r,d,m] ≤ fp[p] · x[r,d,m]` para todo `p, r, d, m`
(o fator de porção do membro limita superiormente o quanto ele pode consumir
daquele prato).
Impede que um membro "consuma" uma receita que não está no cardápio daquele
dia e refeição. *Se fosse removida:* o modelo poderia alimentar alguém com um
prato que nunca foi cozinhado — quebraria a ligação causal entre `x` (o que
foi cozinhado) e `y` (o que foi comido), e o custo/nutrição calculados
deixariam de corresponder a qualquer cardápio real.

**R3 — Limite de pratos.** `Σ_r x[r,d,m] ≤ K` para todo `d, m`, com `K = 2`.
No máximo dois pratos diferentes por refeição — o teto que a família de
demonstração foi desenhada para apertar (perfis com faixas conflitantes, ver
`docs/premissas.md`). *Se fosse removida:* o solver preparia um prato
individual e perfeito para cada um dos quatro membros em cada refeição, o que
é impraticável numa cozinha doméstica e elimina exatamente o problema de
portfólio que torna o projeto interessante — virariam quatro problemas de
dieta independentes, não um problema de família.

**R4 — Variedade.** Com a binária auxiliar `u[r]` (Seção 6):
`u[r] ≥ x[r,d,m]` para todo `d, m`, e `Σ_r u[r] ≥ Vmin`.
Obriga o cardápio da semana a usar pelo menos `Vmin` receitas distintas.
*Se fosse removida:* o solver repetiria a receita de menor custo/maior
eficiência nutricional em todas as refeições do horizonte — tecnicamente
viável, mas descaracteriza a ideia de "semana de cardápio variado" e esconde
a real capacidade do catálogo de 24 receitas.

### Bloco B — nutrição

**R5 — Faixas com folga.** Para todo `p, n, d`:
`min[p,n] − s⁻[p,n,d] ≤ Σ_{r,m} v[r,n]·y[p,r,d,m] ≤ max[p,n] + s⁺[p,n,d]`.
O consumo diário de cada nutriente deve ficar dentro da faixa prescrita do
membro, mas com uma folga elástica (`s⁺`, `s⁻`) em vez de um limite rígido.
*Se fosse removida* (ou aplicada sem a folga): qualquer dia em que não exista
combinação de receitas que caiba exatamente dentro da faixa tornaria o
problema inteiro **inviável** (`Infeasible`) — o solver pararia sem devolver
solução nenhuma, nem para os outros dias. A folga é exatamente a coluna mais
importante do banco de resultados (card S1-14): sem ela, não há como medir
depois qual regra da nutricionista a realidade mais atropela.

**R6 — Restrição individual.** `y[p,r,d,m] = 0` sempre que exista uma tag
`t` com `bloq[p,t] = 1` e `tag[r,t] = 1`.
Impede que um membro receba uma receita com uma tag que lhe é proibida (o
idoso hipertenso do perfil de demonstração não pode receber pratos
`alto_sodio`). *Se fosse removida:* a prescrição médica que justifica a
existência dos perfis desapareceria do modelo — o idoso hipertenso poderia
"comer" um prato alto em sódio no papel, o que invalida a simulação como
representação de uma dieta clinicamente orientada.

**R7 — Desvio do alvo.** `Σ_{r,m} v[r,n]·y[p,r,d,m] − alvo[p,n] = s⁺[p,n,d] − s⁻[p,n,d]`
para todo `p, n, d`, com `s⁺, s⁻ ≥ 0` penalizadas no objetivo (Seção 4).
Mede o quanto cada membro ficou do alvo nutricional, não apenas se ficou
dentro do min/max. *Se fosse removida:* o modelo se daria por satisfeito em
qualquer ponto dentro da faixa — inclusive nos extremos — sem nenhum
incentivo a se aproximar do valor que a nutricionista definiu como ideal; um
cardápio "tecnicamente válido" mas nutricionalmente ruim (sempre raspando o
mínimo ou o máximo) passaria sem ser penalizado.

### Bloco C — estoque e desperdício

**R8 — Consumo derivado.** Para todo `i, d`:
`cons[i,d] = Σ_{r,m,p} a[r,i] · y[p,r,d,m]`.
Define quanto do ingrediente `i` é efetivamente consumido no dia `d`, como
função do cardápio e das porções — não é uma variável nova, é a ponte entre
o lado da demanda (`x`, `y`) e o lado da oferta (estoque, lotes, compras).
*Se fosse removida:* não haveria elo matemático entre o que a família "pede"
para comer e o que precisa existir na despensa — o cardápio poderia usar
ingredientes que nunca foram comprados, e a tabela `compra` do banco nunca
teria como ser validada contra a tabela `cardapio`.

**R9 — Balanço por lote.** Para todo `l, d` (com `d₀` = dia anterior a `d`
no horizonte, ou o início, para `d=1`):
`estoque[l,d] = estoque[l,d₀] − consumo_atribuído[l,d] − w[l,d]`,
com `estoque[l,0] = estoque0[l]` (mais a fração da compra do dia `C`
alocada ao lote recém-criado) e `Σ_l consumo_atribuído[l,d] = cons[ing[l],d]`
para cada ingrediente. Controla, lote a lote, o saldo entre o que havia, o
que foi consumido e o que foi descartado. *Se fosse removida:* o modelo
consumiria ingredientes "no ar", sem respeitar lotes individuais — a coluna
`puxado_por_validade` da tabela `cardapio` (card S1-14) nunca teria como ser
preenchida, porque não existiria o conceito de "este prato foi escolhido para
salvar aquele lote específico".

**R10 — Validade (FEFO).** O `consumo_atribuído[l,d]` de R9 é distribuído
entre os lotes de um mesmo ingrediente priorizando sempre o menor `venc[l]`
disponível primeiro (*first-expire, first-out*): só se consome de um lote com
vencimento mais distante depois que todo lote com vencimento mais próximo do
mesmo ingrediente estiver esgotado ou vencido. **Esta é a regra mais
importante do projeto** — é ela que torna R5/R7 um incentivo real a escolher
receitas que usem o que está vencendo (os lotes propositalmente cadastrados
vencendo em 2–3 dias no card S1-08 existem só para forçar essa escolha).
*Se fosse removida:* o solver poderia deixar o lote que vence em 2 dias
intacto e consumir primeiro um lote do mesmo ingrediente comprado depois e
com validade longa — produzindo exatamente o desperdício que o projeto existe
para evitar e demonstrar como comportamento emergente (card S3-08).

### Bloco D — operacional

**R11 — Tempo de preparo.** `Σ_r tempo[r]·x[r,d,m] ≤ Tmax` para todo
`d, m`.
O tempo total de preparo dos pratos escolhidos numa refeição não pode
exceder o tempo disponível da família. *Se fosse removida:* o modelo poderia
empilhar dois pratos de 60 minutos de preparo cada na mesma refeição de um
dia de semana comum, o que nenhuma família realmente sustentaria — o
cardápio ficaria matematicamente ótimo e logisticamente impossível.

**R12 — Orçamento.** `Σ_i preco[i]·n[i] ≤ B`, com `q[i] ≤ n[i]·tam[i]` para
todo `i` (só se compra em embalagens inteiras, e `q[i]` é o quanto
efetivamente se usa dessa compra).
O gasto total com compras não pode superar o orçamento disponível para o
horizonte. *Se fosse removida:* o modelo minimizaria desperdício e desvio
nutricional sem nenhum freio de gasto — esvaziaria a "manchete em reais" que
o projeto promete entregar na apresentação (preços reais coletados no card
S1-03) e deixaria de representar um problema real de economia doméstica.

---

## 6. Notas técnicas

**Linearização do valor absoluto (R7).** Programação linear não resolve
`|valor − alvo|` diretamente. A técnica padrão é decompor a diferença em duas
variáveis não negativas, `s⁺` (quanto passou do alvo) e `s⁻` (quanto faltou),
de modo que `valor − alvo = s⁺ − s⁻` e `|valor − alvo| = s⁺ + s⁻`. Não é
preciso impor por restrição que uma das duas seja zero: como ambas entram
somadas e penalizadas no objetivo (minimização), qualquer solução com
`s⁺ > 0` e `s⁻ > 0` simultaneamente poderia reduzir as duas pelo mesmo valor
sem mudar `s⁺ − s⁻`, diminuindo o objetivo — o solver nunca escolhe essa
solução dominada. O mesmo par `s⁺/s⁻` cobre a folga elástica de R5 e o desvio
penalizado de R7; a coluna `folga` da tabela `aderencia` é `max − s⁺` (ou
`min + s⁻`, o que for mais apertado) — a distância que ainda restava até
estourar o limite.

**Variável auxiliar de variedade (R4).** `u[r] ∈ {0,1}` indica se a receita
`r` foi usada ao menos uma vez no horizonte. Ela não entra na lista de "seis
variáveis de decisão" da Seção 3 porque é inteiramente derivada de `x` — existe
só para que R4 (uma contagem de receitas *distintas* usadas) seja expressável
como restrição linear, já que `Σ_{r,d,m} x[r,d,m] ≥ Vmin` não impediria usar a
mesma receita repetidas vezes.

**Tamanho estimado do modelo.** Com os dados atuais (`|R|=24`, `|I|=50`,
`|D|=7`, `|M|=3`, `|P|=4`, `|N|=6`, `|L|≈15` por cenário):

| Família | Fórmula | Ordem de grandeza |
|---|---|---|
| `x[r,d,m]` (binária) | `R·D·M` | ~500 |
| `u[r]` (binária, auxiliar) | `R` | 24 |
| `n[i]` (inteira) | `I` | 50 |
| `q[i]` (contínua) | `I` | 50 |
| `y[p,r,d,m]` (contínua) | `P·R·D·M` | ~2.000 |
| `w[l,d]` (contínua) | `L·D` | ~100 |
| `s⁺,s⁻[p,n,d]` (contínuas) | `2·P·N·D` | ~340 |

Isso dá algumas centenas de variáveis binárias e algo em torno de 2.500 a
3.000 variáveis no total por cenário — um PLIM de porte pequeno/médio, bem
dentro do que o CBC resolve em segundos (confirmado pelo smoke test do card
S1-13 dentro do container). Isso importa porque o card S1-14 já prevê gravar
os resultados de **500 cenários** de Monte Carlo: 500 resoluções de um
problema desse tamanho são factíveis em minutos, não em horas — o que não
seria verdade se o modelo crescesse para a casa das dezenas de milhares de
variáveis.
