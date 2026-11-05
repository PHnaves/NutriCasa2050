# Formulação Matemática — NutriCasa 2050

> Entrega mais importante do projeto. Qualquer um dos três integrantes da
> equipe pode ser chamado para explicar qualquer restrição deste documento na
> avaliação individual de novembro — por isso cada restrição vem acompanhada
> do que aconteceria se ela fosse removida, não só do que ela faz.

**Versão implementada.** Este documento foi escrito no Sprint 1 como plano e
reescrito no Sprint 6 para descrever **o modelo que de fato roda** em
`src/nutricasa2050/otimizacao/`. Onde a implementação divergiu do plano
original, a Seção 7 lista a diferença e o motivo. Cada função de restrição tem
o número no nome (`r10_validade_por_lote`, etc.) e uma docstring com os
mesmos dois itens que aparecem aqui: **(a) o que faz** e **(b) o que acontece
se sair**.

Este documento formaliza o problema de programação linear inteira mista
(PLIM — variáveis binárias, inteiras e contínuas) que o NutriCasa 2050
resolve a cada cenário: decidir o cardápio da semana de uma família, a porção
de cada membro, a lista de compras e o descarte de estoque, minimizando custo,
desperdício, tempo de preparo e desvio nutricional, sem violar as restrições
de dieta, orçamento e tempo.

A implementação usa [PuLP](https://coin-or.github.io/pulp/) com o solver CBC.

---

## 1. Conjuntos

| Conjunto | Significado | Tamanho atual nos dados |
|---|---|---|
| `I` | Ingredientes (`data/ingredientes.csv`) | 50 |
| `R` | Receitas (`data/receitas.csv`) | 24 |
| `D` | Dias do horizonte | 7 (configurável; a Monte Carlo usa 5) |
| `M` | Refeições do dia (café da manhã, almoço, jantar) | 3 |
| `P` | Membros da família (`data/perfis/familia_demo.json`) | 4 |
| `N` | Nutrientes acompanhados (`data/nutrientes.csv`) | 6 (`kcal`, `proteina_g`, `carboidrato_g`, `gordura_g`, `sodio_mg`, `fibra_g`) |
| `L` | Lotes: os do estoque inicial **mais um lote de compra por ingrediente e dia de compra** (S3-01) | 50 iniciais (15 reais + 35 vazios, um por ingrediente sem estoque) + 50 de compra = 100 |
| `C` | Dias de compra, `C ⊆ D` | 1 (uma compra semanal, no dia 1) |
| `T` | Tags de dieta fixas (`vegetariano`, `sem_gluten`, `sem_lactose`, `alto_sodio`) | 4 |

Índices: `i ∈ I`, `r ∈ R`, `d ∈ D`, `m ∈ M`, `p ∈ P`, `n ∈ N`, `l ∈ L`, `c ∈ C`.

---

## 2. Parâmetros

Todos vêm dos CSVs de dados, do JSON de perfis ou do objeto `Parametros` —
nada é "chutado" dentro do modelo.

| Parâmetro | Origem | Significado |
|---|---|---|
| `a[r,i]` | `matriz_a.csv` | quantidade do ingrediente `i` em **uma porção** da receita `r` |
| `v[r,n]` | `nutrientes.csv` | quantidade do nutriente `n` em **uma porção** da receita `r` (da tabela TACO, card S1-07) |
| `preco[i]`, `tam[i]` | `ingredientes.csv` | preço e tamanho de **uma embalagem** de `i`; `pu[i] = preco[i]/tam[i]` é o preço por unidade |
| `val[i]` | `ingredientes.csv` (`validade_dias`) | validade típica de `i` (dias) |
| `fp[p]` | perfil (`fator_porcao`) | fator de porção do membro `p` (1,0 adulto; 0,6 criança; 0,8 idoso) |
| `perm[p,r] ∈ {0,1}` | perfil × receita | 1 se nenhuma `tag_dieta` de `r` está em `tags_bloqueadas` de `p` **e** todas as `tags_exigidas` de `p` estão em `r` (`Membro.pode_comer`) |
| `min[p,n]`, `max[p,n]`, `alvo[p,n]` | perfil (`faixas`) | faixa e alvo diários do nutriente `n` para o membro `p` |
| `tempo[r]`, `pref[r]` | receitas | minutos de preparo e nota de preferência (0 a 1) |
| `q0[l]`, `ing[l]`, `venc[l]`, `chega[l]` | estoque / lotes de compra | quantidade inicial, ingrediente, dia de vencimento e (só lotes de compra) dia de chegada |
| `B` | `Parametros.orcamento` | teto de gasto com compras no horizonte (R$) |
| `Tmax` | `Parametros.tempo_por_dia` | minutos de cozinha por dia (∞ = sem limite) |
| `K` | `Parametros.pratos_por_refeicao` | limite de pratos por refeição (**2**) |
| `pulada[d,m]` | `Catalogo.refeicoes_puladas` | refeições que não acontecem (cenários, botão "ninguém jantou") |
| `w_*`, `cpm`, `vpp` | `Pesos` | pesos do objetivo, custo por minuto e valor por ponto de preferência (Seção 4) |

---

## 3. Variáveis de decisão

| Variável | Tipo | Índices | O que representa |
|---|---|---|---|
| `x[r,d,m]` | **binária** | `r,d,m` | 1 se a receita `r` é cozinhada no dia `d`, refeição `m` → tabela `cardapio` |
| `y[p,r,d,m]` | **contínua** em `[0,1]` | `p,r,d,m` | **fração** da porção de `r` que o membro `p` come → tabela `porcao` |
| `b[i,c]` | **inteira**, `≥0` | `i∈I, c∈C` | embalagens do ingrediente `i` compradas no dia `c` → tabela `compra` |
| `s[l,d]` | contínua, `≥0` | `l,d` | estoque do lote `l` ao fim do dia `d` |
| `u[l,d]` | contínua, `≥0` | `l,d` | quantidade do lote `l` consumida no dia `d` |
| `w[l,d]` | contínua, `≥0` | `l,d` | quantidade do lote `l` descartada no dia `d` → tabela `descarte` |
| `f⁻[n,p,d]`, `f⁺[n,p,d]` | contínuas, `≥0` | `n,p,d` | **folga** abaixo do mínimo / acima do máximo → tabela `aderencia` |
| `s⁺[n,p,d]`, `s⁻[n,p,d]` | contínuas, `≥0` | `n,p,d` | desvio acima / abaixo do alvo (no código: `desvio_acima`, `desvio_abaixo`) |

**Por que `y` é fração e não sim/não?** Se a porção fosse binária, cada pessoa
comeria "o prato inteiro ou nada" e o modelo seria muito mais pesado (milhares
de binárias a mais) sem ganho real. Com `x` binário (o prato foi cozinhado ou
não) e `y` contínuo, só `x` e `b` carregam a combinatória do problema.

---

## 4. Função objetivo

```
min   w_custo · Σ_{i,c} preco[i]·b[i,c]                         (1) compra
    + w_desc  · Σ_{l,d} pu[ing[l]]·w[l,d]                       (2) desperdício
    + w_prep  · cpm · Σ_{r,d,m} tempo[r]·x[r,d,m]               (3) tempo
    + w_desv  · Σ_{n,p,d} (s⁺[n,p,d] + s⁻[n,p,d])               (4) desvio do alvo
    + w_folga · Σ_{n,p,d} (f⁺[n,p,d] + f⁻[n,p,d])               (5) folga
    − w_pref  · vpp · Σ_{r,d,m} pref[r]·x[r,d,m]                (6) preferência
```

Pesos padrão (`Pesos`): `w_custo = w_desc = w_prep = w_desv = w_pref = 1`,
`w_folga = 1000`, `cpm = R$ 0,10/min`, `vpp = R$ 1,00/ponto`.

Os seis termos: **custo de compra**, **valor do que foi jogado fora**,
**tempo de cozinha**, **distância do alvo nutricional**, **folga usada** e
**bônus de preferência** (subtraído, porque é minimização: gostar mais reduz
o objetivo).

**Por que tudo precisa estar em reais antes de somar.** Cada termo nasce numa
unidade diferente — R$, quilos descartados, minutos, miligramas, uma nota de
0 a 1. Somar minutos com miligramas de sódio não tem significado. `cpm`
(R$/minuto) e `vpp` (R$/ponto) são **fatores de conversão**: com eles, "o peso
do tempo é 0,5" vira a frase defensável "cada minuto de cozinha vale R$ 0,50
para nós". Os pesos `w_*` ficam como o verdadeiro botão de importância
relativa.

**Por que a folga pesa 1000.** A folga existe para o modelo *nunca recusar*
uma faixa nutricional impossível, não para ser usada de graça: com peso baixo
ela viraria o jeito mais barato de ignorar a nutricionista.

---

## 5. As doze restrições

### Bloco A — estrutura do cardápio

**R1 — Cobertura** (`r1_cobertura`). `Σ_r y[p,r,d,m] = 1` para todo `p,d,m`
(exceto refeições puladas, onde `y = 0`).
*(a)* Cada pessoa come exatamente uma porção por refeição, somando os pratos.
*(b) Se sair:* a soma poderia ficar em zero sempre que um prato custasse mais
que zero, e a solução "mais barata" seria a família não comer.

**R2 — Vínculo** (`r2_vinculo`). `y[p,r,d,m] ≤ x[r,d,m]`.
*(a)* Ninguém come de um prato que não foi cozinhado.
*(b) Se sair:* o modelo alimentaria alguém com um prato que nunca entrou no
cardápio — `x` (o que foi cozinhado) e `y` (o que foi comido) perderiam a
ligação causal e custo/nutrição deixariam de corresponder a qualquer cardápio
real.

**R3 — Limite de pratos** (`r3_limite_de_pratos`). `Σ_r x[r,d,m] ≤ K`, `K = 2`.
*(a)* No máximo dois pratos por refeição — o teto que obriga o solver a achar
pratos que sirvam várias pessoas ao mesmo tempo.
*(b) Se sair:* o solver cozinharia um prato sob medida para cada pessoa em
cada refeição; viraria quatro problemas de dieta independentes, não um
problema de família.

**R4 — Variedade** (`r4_variedade`). (i) `Σ_{d,m} x[r,d,m] ≤ 2` para todo `r`;
(ii) `x[r,d,m] + x[r,d+1,m] ≤ 1` para todo `r,d,m`.
*(a)* Nenhuma receita aparece mais de duas vezes na semana, nem em dois dias
seguidos na mesma refeição.
*(b) Se sair:* o solver serve a receita mais barata os sete dias — matematicamente
ótimo, humanamente inviável (medido: sem R4, uma receita aparece 11 vezes em
21 refeições; ver `docs/resultados.md`). Exemplo de que bom senso humano
também é modelagem.

### Bloco B — nutrição

**R5 — Faixas com folga** (`r5_faixas_nutricionais`). Para todo `n,p,d`, com
`tot[n,p,d] = Σ_{r,m} v[r,n]·fp[p]·y[p,r,d,m]`:
`min[p,n] − f⁻[n,p,d] ≤ tot[n,p,d] ≤ max[p,n] + f⁺[n,p,d]`.
*(a)* O consumo diário de cada nutriente fica dentro da faixa do membro, com
uma válvula de escape elástica em vez de um limite rígido.
*(b) Se sair* (ou sem a folga): qualquer dia sem combinação de receitas que
caiba na faixa tornaria o problema inteiro `Infeasible` — nenhuma resposta,
nem para os outros dias. Com a folga, o modelo entrega a melhor resposta
possível **e mostra onde e quanto precisou ceder**.

**R6 — Restrição individual** (`r6_restricao_alimentar_individual`).
`y[p,r,d,m] = 0` se `perm[p,r] = 0`.
As tags dos dados são de dois tipos, e `perm` trata os dois: **bloqueadas**
(a receita *tem* algo, como `alto_sodio`, que o idoso bloqueia) e
**exigidas** (a receita *não tem* algo, como `sem_gluten`; um celíaco só come
receitas com essa tag, via `Membro.tags_exigidas`). Até o Sprint 6 só
existiam as bloqueadas, e o botão "Filho celíaco" bloqueava `sem_gluten`:
proibia justamente os pratos seguros e deixava o modelo inviável.
*(a)* Um membro não recebe prato com tag que lhe é proibida — mas o prato
continua podendo ser cozinhado para os outros (é isso que permite "o filho é
celíaco" sem obrigar a casa toda a comer sem glúten).
*(b) Se sair:* a prescrição médica que justifica os perfis some do modelo — o
idoso hipertenso "comeria" prato alto em sódio no papel.

**R7 — Desvio do alvo** (`r7_desvio_do_alvo`). `tot[n,p,d] − alvo[p,n] = s⁺[n,p,d] − s⁻[n,p,d]`.
*(a)* Mede a distância do valor *prescrito*, não só se está dentro da faixa.
*(b) Se sair:* qualquer ponto dentro da faixa — inclusive os extremos —
pareceria igualmente bom; um cardápio "válido mas ruim" passaria sem
penalização.

### Bloco C — estoque e desperdício

**R8 — Consumo derivado** (`r8_consumo_derivado`). Para todo `i,d`:
`Σ_{l: ing[l]=i} u[l,d] = Σ_{r,m,p} a[r,i]·fp[p]·y[p,r,d,m]`.
*(a)* A ponte entre o cardápio/porções (demanda) e o estoque/lotes (oferta).
*(b) Se sair:* o cardápio poderia usar ingredientes que nunca foram comprados.

**R9 — Balanço por lote** (`r9_balanco_de_estoque`). Para todo `l,d`:
`s[l,d] = s[l,d−1] + chegada[l,d] − u[l,d] − w[l,d]`, com `s[l,0] = q0[l]` e
`chegada[l,d] = tam[ing[l]]·b[ing[l],d]` **só** se `chega[l] = d` (zero nos
demais casos — `chegada_do_lote`).
*(a)* O que resta hoje = o que restava ontem + o que chegou − o que foi
consumido − o que foi descartado; amarra os dias num sistema só.
*(b) Se sair:* o solver consumiria ingredientes "no ar", sem respeitar lotes
nem o que havia na despensa (teste `test_r9_conserva_massa`: entrada total =
consumo + descarte + estoque final).

**R10 — Validade** (`r10_validade_por_lote`). Para todo `l,d`:
`d > venc[l] ⇒ u[l,d] = 0` e `d ≥ venc[l] ⇒ s[l,d] = 0`.
*(a)* Não se come o que já venceu, e não pode sobrar estoque de lote vencido
— o que não foi comido a tempo é **obrigado** a sair por `w` (descarte).
*(b) Se sair:* o consumo poderia ser empurrado para depois do vencimento sem
consequência; não haveria pressão para usar primeiro o que vence primeiro.
**É o coração do projeto**: junto com o custo do descarte no objetivo, o
solver passa a preferir as receitas que gastam o que está vencendo —
*ninguém programou isso* (ver Seção 8, teste `test_coracao_antidesperdicio`).

### Bloco D — operacional

**R11 — Tempo de preparo** (`r11_tempo_de_preparo`). `Σ_{r,m} tempo[r]·x[r,d,m] ≤ Tmax` para todo `d`.
*(a)* O tempo de cozinha do dia cabe no tempo disponível (não é adicionada
quando `Tmax = ∞`).
*(b) Se sair:* uma receita de duas horas poderia cair numa terça corrida — o
cardápio seria ótimo no papel e impossível na cozinha.

**R12 — Orçamento** (`r12_orcamento`). `Σ_{i,c} preco[i]·b[i,c] ≤ B`.
*(a)* O gasto com compras não passa do orçamento.
*(b) Se sair:* o modelo minimizaria desperdício e desvio sem nenhum freio de
gasto e deixaria de ser um problema de economia doméstica.

---

## 6. Notas técnicas

**Linearização do valor absoluto (R7).** Programação linear não minimiza
`|tot − alvo|` diretamente (módulo não é linear). A técnica padrão: duas
variáveis não negativas, `s⁺` (quanto passou) e `s⁻` (quanto faltou), com
`tot − alvo = s⁺ − s⁻` e `|tot − alvo| = s⁺ + s⁻`. Não é preciso exigir por
restrição que uma delas seja zero: como ambas entram somadas no objetivo
(minimização), uma solução com `s⁺ > 0` e `s⁻ > 0` ao mesmo tempo sempre pode
ser melhorada reduzindo as duas pelo mesmo valor sem alterar `s⁺ − s⁻` — o
solver nunca a escolhe. Testado em `test_apenas_um_lado_do_desvio_fica_positivo`.

**Lotes de compra (R9/R10).** Para a validade valer também para o que foi
*comprado* (e não só para o estoque inicial), `criar_lotes_de_compra` cria um
lote por ingrediente e dia de compra, vencendo em `dia + val[i]`
(`preparar_catalogo` junta esses lotes aos iniciais). Sem isso, comprar no
dia 2 um item que dura 5 dias não teria como vencer no dia 7.

**Preço-sombra em MIP.** O modelo tem variáveis binárias e inteiras, então o
valor dual do solver (`LpConstraint.pi`) **não é confiável** (confirmado: até
o orçamento, genuinamente apertado, volta `0.0`). O preço-sombra do projeto
é calculado resolvendo duas vezes com o limite perturbado em uma unidade —
diferença finita, a definição literal de derivada (`analise/sensibilidade.py`).

**Tamanho do modelo** (catálogo real, 4 membros, 7 dias, 3 refeições):

| Família | Quantidade |
|---|---|
| `x` (binária) | 504 |
| `y` (contínua) | 2.016 |
| `b` (inteira) | 50 |
| `s`, `u`, `w` (contínuas) | 2.100 (700 cada = 100 lotes × 7 dias) |
| `f⁻`, `f⁺`, `s⁻`, `s⁺` (contínuas) | 672 (168 cada = 6 nutrientes × 4 membros × 7 dias) |
| **Restrições** | 4.360 |

Resolve em ~15 s (Optimal) com `NUTRICASA2050_SOLVER_TIMEOUT=10`; a Monte Carlo
usa horizonte 5 e timeout 2 s (ver `docs/resultados.md`, S4-05).

---

## 7. O que mudou do plano original (Sprint 1) para o modelo implementado

| Plano (S1-10) | Implementado | Motivo |
|---|---|---|
| R1: `Σ_r x ≥ 1` (ao menos um prato) | `Σ_r y = 1` por pessoa | com `y` fracionário, "comer" é por pessoa, não por prato |
| R2: `y ≤ fp·x` | `y ≤ x` | o fator de porção `fp` já multiplica nos lugares onde importa (R5, R7, R8) |
| R4: `Σ_r u[r] ≥ Vmin` (mínimo de receitas distintas) | teto de 2 aparições + proibição de dias seguidos | a regra do plano não impedia repetir uma receita 10 vezes; a nova impede de verdade |
| `n[i]`, `q[i]`, termo "sobra de embalagem" | `b[i,c]`; termo de **folga** no lugar | a sobra de embalagem já aparece como estoque/descarte nos lotes; a folga virou o sexto termo |
| R10: FEFO por ordenação de lotes | `u = 0` após o vencimento e `s = 0` a partir dele | basta obrigar o descarte e cobrá-lo — o solver descobre a ordem sozinho (comportamento emergente) |
| R11: tempo **por refeição** | tempo **por dia** | alinhado ao parâmetro `tempo_por_dia` |
| lotes só do estoque inicial | + lotes de compra por dia de compra | validade vale também para o que se compra |

---

## 8. Onde está cada coisa no código e nos testes

| Peça | Função | Arquivo | Teste principal |
|---|---|---|---|
| R1–R3 | `r1_cobertura`, `r2_vinculo`, `r3_limite_de_pratos` | `restricoes.py` | `test_restricoes_cardapio.py` |
| R4 | `r4_variedade` | `restricoes.py` | `test_restricoes_variedade.py` |
| R5, R7 | `r5_faixas_nutricionais`, `r7_desvio_do_alvo` | `restricoes.py` | `test_folga_e_desvio.py` |
| R6 | `r6_restricao_alimentar_individual` | `restricoes.py` | `test_restricoes_dieta.py` |
| R8, R9 | `r8_consumo_derivado`, `r9_balanco_de_estoque` | `restricoes.py` | `test_restricoes_estoque.py` |
| R10 | `r10_validade_por_lote` | `restricoes.py` | `test_restricoes_validade.py`, `tests/integracao/test_coracao.py` |
| R11 | `r11_tempo_de_preparo` | `restricoes.py` | `test_restricoes_tempo.py` |
| R12 | `r12_orcamento` | `restricoes.py` | `test_restricoes_nutricao.py` |
| Objetivo | `montar_objetivo`, `termo_*`, `descrever_objetivo` | `objetivo.py` | `test_objetivo_completo.py` |
