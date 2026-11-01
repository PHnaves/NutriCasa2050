# Resultados do Sprint 3

Registros que os cards do Sprint 3 pedem explicitamente para documentar
(S3-02, S3-04, S3-08). Todos os numeros vem de rodadas reais do solver
nesta maquina (CBC via PuLP), com `NUTRICASA2050_SOLVER_TIMEOUT` no
padrao (30s) — ver `src/nutricasa2050/config.py`.

## S3-02 — Ligar as quatro pessoas da familia

Catalogo real (`data/`), horizonte de 7 dias, 3 refeicoes/dia, 2 pratos
por refeicao (padrao do projeto), orcamento de R$ 500.

| Cenario | Status | Tempo de solucao |
|---|---|---|
| 1 pessoa (`adulto_ativo`) | Optimal | ~9,4 s |
| 4 pessoas (familia completa) | Optimal | ~36,8 s |

**O modelo cresce rapido:** as variaveis de porcao (`y`) multiplicam por
membro, e as de folga/desvio (`R5`/`R7`, S3-06) multiplicam por
membro x nutriente x dia. Com os 4 membros reais, 36,8 s passa dos 30 s
que o card pede como teto (`test_tempo_de_solucao_abaixo_de_trinta_segundos`,
em `tests/unidade/test_familia.py`, marcado `@pytest.mark.lento` e
`@pytest.mark.xfail(strict=False)` — fica vermelho de proposito, sem
quebrar o pipeline, para continuar sendo medido a cada rodada).

**Isso e exatamente o sinal que o proprio card previu:** "SE ESTE FALHAR,
e o sinal de que o card S4-05 (performance) vai ser necessario." Sprint 4
vai precisar atacar isso — candidatos obvios sao reduzir o `timeLimit` do
CBC aceitando um gap de otimalidade, ou cortar o numero de variaveis de
folga/desvio para so os nutrientes realmente tracked por cada membro (hoje
`variaveis.py` cria uma para TODO nutriente do catalogo x TODO membro,
mesmo quando aquele membro nao tem faixa definida para aquele nutriente).

**Achado paralelo (nao e so o tempo):** mesmo com orcamento alto
(testado at R$ 5.000) e mais pratos por refeicao (testado com 4), a
familia completa ainda precisa de folga (R5/S3-06) para fechar as 6
faixas nutricionais dos 4 membros simultaneamente. Nao e falta de
dinheiro — e que 2 (ou mesmo 4) pratos compartilhados por refeicao nao
bastam para atender 4 perfis nutricionais bem diferentes (crianca,
idoso hipertenso, 2 adultos) ao mesmo tempo com as 24 receitas atuais.
A folga faz exatamente o que deveria: em vez de Infeasible, o modelo
entrega a melhor resposta possivel e marca onde precisou ceder.

A crianca (`fator_porcao = 0.6`) consome, no mesmo prato, exatamente 60%
do que o adulto (`fator_porcao = 1.0`) consome — verificado em
`test_crianca_consome_sessenta_por_cento_do_adulto`.

## S3-04 — Regra da variedade (R4)

Catalogo real, 1 pessoa (`adulto_ativo`), horizonte de 7 dias, 3
refeicoes/dia (21 pratos no total), orcamento de R$ 300.

**Sem R4** — so 7 receitas distintas usadas nos 21 pratos da semana; o
solver repete a mais barata/mais perto do alvo nutricional o quanto
quiser:

| Receita | Vezes na semana |
|---|---|
| Macarrão com Atum e Ervilha | 11 |
| Arroz, Feijão e Ovo | 9 |
| Arroz Rápido com Ovo | 7 |
| Macarrão com Frango e Molho de Tomate | 5 |
| Omelete de Legumes | 4 |
| Frango ao Molho de Tomate | 3 |
| Iogurte com Aveia e Maçã | 1 |

**Com R4** — 15 receitas distintas, nenhuma repetida mais de 2 vezes:

| Receita | Vezes na semana |
|---|---|
| Arroz Rápido com Ovo, Macarrão com Frango e Molho de Tomate, Feijão/Arroz/Couve, Omelete de Legumes, Frango ao Molho de Tomate, Panqueca de Banana e Aveia, Iogurte com Aveia e Maçã, Macarrão com Atum e Ervilha, Frango Grelhado com Batata, Feijão com Calabresa, Bolo de Banana com Aveia, Arroz/Feijão/Ovo | 2 cada |
| Sanduíche Quente de Queijo e Tomate, Torta de Legumes, Escondidinho de Batata com Carne | 1 cada |

**O preço da variedade, decomposto termo a termo (`descrever_objetivo`,
S3-07):**

| Termo | Sem R4 | Com R4 |
|---|---|---|
| Custo (compra) | R$ 111,70 | R$ 279,40 |
| Desperdício | R$ 50,12 | R$ 83,22 |
| Preparo (tempo) | R$ 85,70 | R$ 73,80 |
| Desvio do alvo | R$ 246,27 | R$ 4.075,05 |
| Folga (S3-06) | R$ 0,00 | R$ 239.916,87 |
| Preferência | − R$ 29,39 | − R$ 19,06 |
| **Total** | **R$ 464,40** | **R$ 244.409,28** |

A compra sobe ~2,5x (repetir a receita mais barata e literalmente mais
barato que variar). Mas o salto grande esta na **folga**: sem variedade,
o solver acha uma combinacao de repeticoes que fecha as 6 faixas
nutricionais quase exatamente (folga zero); com o teto de 2 repeticoes
por receita, as 24 receitas do catalogo nao bastam para fechar a faixa
com precisao todos os dias, e o modelo precisa ceder — exatamente o
"nao existe cardapio perfeito, mas aqui esta o melhor possivel, e e
assim que ele cede" que a folga (S3-06) foi desenhada para mostrar.
Achado honesto: variedade e nutricao entram em tensao real quando o
catalogo de receitas e pequeno — o numero tambem sinaliza que o Sprint
4/5 (mais receitas, ou ajustar os pesos) tem material concreto para
investigar.

## S3-08 — MARCO: o coracao anti-desperdicio

Cenario: 1 lote de tomate (3 kg) vencendo no dia 3, 3 receitas que usam
tomate (salada, molho, tomate assado) e 2 receitas sem tomate (arroz,
feijao), horizonte de 5 dias, 1 prato por refeicao — exatamente o que o
card pede ("pelo menos 3 receitas que usam tomate").

**Antes (card so cumprido parcialmente, sem R10/termo_desperdicio
—simulado desligando as duas coisas):** sem a penalidade de desperdicio
no objetivo, qualquer ordem de pratos e igualmente "otima" — nada
empurra o tomate para o inicio da semana.

**Depois (com R10 + termo_desperdicio, o codigo real deste sprint):**

| Dia | Prato escolhido pelo solver |
|---|---|
| 1 | Salada de tomate |
| 2 | Molho de tomate |
| 3 | Salada de tomate |
| 4 | Arroz simples |
| 5 | Feijao simples |

Descarte final: **zero**. Custo do objetivo: R$ 8,50 (so o preco do
tomate que ja estava em estoque, nenhuma compra adicional).

**NINGUEM programou "use o tomate antes do dia 3".** O solver chegou
nesse cardapio sozinho: comer o tomate nos 3 primeiros dias nao custa
nada extra (ja estava comprado), enquanto deixar ele vencer custaria o
preco unitario do tomate inteiro no termo de desperdicio. Minimizar
custo, nessas condicoes, É minimizar desperdicio — e isso te faz usar
primeiro o que vence primeiro. Comportamento emergente, nao
programacao explicita.

Teste de regressao: `tests/integracao/test_coracao.py::test_coracao_antidesperdicio`
— **nunca deve ser marcado como skip.**
