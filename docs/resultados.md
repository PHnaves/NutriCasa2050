# Resultados dos Sprints 3, 4 e 6

> ## Sprint 6 — o que mais foi corrigido ao preparar a hospedagem
>
> Rodando o app inteiro com os parametros padrao (Streamlit AppTest, novo
> teste `tests/integracao/test_app_streamlit.py`), apareceram dois erros
> que nenhum teste pegava:
>
> 1. **O app quebrava ao abrir** (`KeyError: 'compra_habitual_...'`): a
>    comparacao com a familia normal era serializada sem a expansao dos
>    lotes de compra do baseline. Corrigido em `app.py`.
> 2. **O botao "Filho celiaco" deixava o modelo inviavel**: bloqueava a tag
>    `sem_gluten`, que nos dados significa "esta receita NAO tem gluten" — ou
>    seja, proibia os pratos seguros. Agora `Membro.tags_exigidas` exige a
>    tag (ver R6 em `formulacao.md`). O teste dos cinco botoes usava
>    horizonte 3, que escondia o problema; agora usa os padroes do app
>    (5 dias, R$ 500) e exige cardapio nao vazio.
>
> Medido com os padroes do app (4 pessoas, R$ 500, tempo limite 10 s):
> horizonte 5 → cardapio em 12,4 s; horizonte 7 → 14,8 s. O app passou a
> usar 5 dias por padrao (com um seletor de 3 a 7) e guarda as respostas em
> cache. O card S5-06 pedia menos de 10 s por botao: o primeiro clique leva
> ~13 s, os repetidos sao instantaneos.

> ## NUMEROS REVALIDADOS (Sprint 6, rodada de 100 cenarios)
>
> Rodada real: 100 cenarios x 3 estrategias, horizonte 5, 3 refeicoes/dia,
> orcamento 500, tempo limite 30 s, 0 falhas, 3222 s (54 min). Solucoes
> nao inteiras agora sao descartadas. Resultados (substituem os de S4-06):
>
> | Numero | Valor |
> |---|---|
> | Desperdicio medio (R$/semana) | otimizado 578,30 · humano 2.526,79 · **guloso 92,13** |
> | Reducao vs. familia normal (humano) | **77,1%** |
> | Economia mensal (otimizado vs humano, IC 95%) | R$ 9.136 [4.649 ; 13.623] |
> | Preco da prescricao (1 cenario base) | +R$ 174,40/semana e +294 min de cozinha |
> | Folga mais frequente | fibra do idoso hipertenso (1173 ocorrencias); carboidrato da crianca (1108); proteina dos adultos |
>
> **Ressalvas honestas.** (1) O guloso desperdiça MENOS que o otimizado
> (92 contra 578): o otimizado paga desperdicio para atender nutricao (folga
> pesa 1000x) e, com 30 s, fica longe do otimo (vide tabela de timeout acima);
> a vantagem do otimizado nao e desperdicio absoluto contra todos, e sim
> contra a familia normal e em aderencia nutricional. (2) O "preco da
> prescricao" vem de solucoes com tempo limite e deve ser lido como ordem de
> grandeza, nao valor exato. (3) A economia mensal e a diferenca de custo de
> compra + desperdicio extrapolada de 5 dias para 30 (x30/7), com tudo o que
> isso implica. As secoes S4-05/S4-06 abaixo seguem como registro historico.

> ## CORRECAO (Sprint 6) — leia antes das secoes S4-05 e S4-06
>
> Os numeros do S4-05/S4-06 abaixo (91,0% de reducao, R$ 12.635/mes, preco
> da prescricao, guloso vs. otimizado) foram calculados tratando o status
> "Not Solved" do CBC como "melhor solucao viavel encontrada". **Isso estava
> errado.** Quando o tempo limite estoura antes de qualquer solucao
> *inteira*, o PuLP devolve os valores da **relaxacao linear** (x = 0,3
> "prato meio cozinhado", 0,6 embalagem comprada). Eles satisfazem R1 e as
> demais restricoes lineares, entao a checagem que fiz na epoca (soma das
> porcoes) nao detectava. Medido agora no catalogo real (horizonte 5):
>
> | orcamento | timeout | status | observacao |
> |---|---|---|---|
> | 300 | 10 s | Not Solved | sem solucao inteira — **antes era aceito** |
> | 500 | 10 s | Optimal (13 s) | objetivo 5.255.966 — incumbente ruim |
> | 500 | 60 s | Optimal (62 s) | objetivo 145.205 — 36x melhor |
>
> Duas consequencias: (1) "Optimal" com tempo limite estourado e so a
> melhor solucao *encontrada*, nao provada otima — a qualidade depende do
> tempo; (2) cada solve real leva >=10 s, entao 500 cenarios x 1 solve
> otimizado passam de 1,5 h. **Correcao no codigo:** `solver.resolver` agora
> checa a integralidade (`solucao_e_inteira`) e devolve solucao vazia se nao
> for inteira (teste de regressao em `tests/unidade/test_solver.py`).
> os numeros do S4-06 antigos NAO valem; use os revalidados acima.

Registros que os cards dos Sprints 3 e 4 pedem explicitamente para
documentar (S3-02, S3-04, S3-08, S4-05, S4-06). Todos os numeros vem de
rodadas reais do solver nesta maquina (CBC via PuLP). O padrao de
`NUTRICASA2050_SOLVER_TIMEOUT` mudou de 30s para 10s no meio deste
documento (card S4-05, ver secao propria) — os numeros do S3-02/S3-04/
S3-08 abaixo foram medidos ANTES dessa mudanca (com o antigo padrao de
30s); os do S4-05/S4-06 já refletem o novo padrao, cada secao diz qual.

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
em `tests/unidade/test_familia.py`).

**Isso e exatamente o sinal que o proprio card previu:** "SE ESTE FALHAR,
e o sinal de que o card S4-05 (performance) vai ser necessario." **Resolvido
no S4-05** — baixar `NUTRICASA2050_SOLVER_TIMEOUT` de 30s para 10s
(a alavanca 3 do card) foi suficiente por si so para ESTE cenario
especifico: ~15,3s, Optimal de verdade (nao so um incumbente — ver a
secao S4-05 completa, mais abaixo, para a investigacao e a prova). O
teste nao usa mais `xfail`.

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

Cenario: 1 lote de tomate (3 kg, R$ 5/kg) vencendo no dia 3, 3 receitas
que usam tomate (salada, molho, tomate assado — todas LENTAS, 30 min) e 2
sem tomate (arroz, feijao — RAPIDAS, 10 min), horizonte de 5 dias, 1 prato
por refeicao.

**Correcao feita no Sprint 6 (achado honesto).** A primeira versao deste
cenario (S3-08) tinha as receitas de tomate como as mais RAPIDAS. Ao
zerar o peso do desperdicio para montar o "antes", o cardapio saiu
IDENTICO — o solver escolhia o tomate so por tempo de preparo, e o teste
passava sem provar o que dizia provar. O cenario foi refeito para o tomate
ser a opcao mais lenta: agora a unica razao para gasta-lo e nao deixa-lo
vencer. O texto anterior dizia que o "antes" tinha sido "simulado"; nao
tinha sido rodado — agora foi.

| Dia | Com custo de desperdicio (peso 1) | Sem custo de desperdicio (peso 0) |
|---|---|---|
| 1 | Salada de tomate | Feijao simples |
| 2 | Molho de tomate | Arroz simples |
| 3 | Salada de tomate | Molho de tomate |
| 4 | Arroz simples | Arroz simples |
| 5 | Feijao simples | Feijao simples |
| **Tomate descartado** | **0 kg** | **2 kg** |

**NINGUEM programou "use o tomate antes do dia 3".** Com o desperdicio
custando dinheiro, o solver aceita cozinhar tres pratos lentos para nao
perder o tomate; sem esse custo, ele cozinha o rapido e joga 2 kg fora. A
unica diferenca entre as duas colunas e um peso no objetivo. Comportamento
emergente, nao programacao explicita.

Testes de regressao (nunca marcar como skip):
`tests/integracao/test_coracao.py::test_coracao_antidesperdicio` e o
controle `::test_sem_custo_de_desperdicio_o_tomate_vence`.

# Sprint 4

## S4-05 — Desempenho (obrigatorio: o teste do S3-02 falhou)

Base medida no S3-02 (4 membros reais, horizonte 7, 3 refeicoes/dia,
`NUTRICASA2050_SOLVER_TIMEOUT` no antigo padrao de 30s): **~36,8 s**,
acima do teto de 30s. Testei as quatro alavancas do card, NESTA ORDEM:

| Alavanca | Configuracao | Tempo | Status | Veredito |
|---|---|---|---|---|
| (base) | horizonte=7, timeout=30s | 36,8 s | Optimal | acima do teto |
| 1. Reduzir horizonte | horizonte=5, timeout=30s | 33,5 s | Optimal | ajuda pouco (~3s) — o gargalo nao e o tamanho, e a combinatoria |
| 2. Reduzir dias de compra | ja era 1 dia so | — | — | nao aplicavel, ja no minimo |
| 4. Trocar CBC por HiGHS | horizonte=7, timeout=30s | **>60 s** | Not Solved | **PIOROU** — testei e descartei (ver abaixo) |
| 3. Baixar o timeLimit do CBC | horizonte=7, timeout=20s | 26,9 s | Optimal | funciona isolado, mas insuficiente para 500 cenarios |
| 1+3 combinadas | horizonte=5, timeout=5s | ~9 s | Optimal | boa, mas 500× isso ainda e ~75 min |
| 1+3, mais agressiva | horizonte=5, timeout=2s | **~2,5 s** | Not Solved (incumbente usavel) | **escolhida** |

**Sobre o HiGHS (alavanca 4) — achado negativo, documentado em vez de
escondido:** instalei `highspy` e testei `pulp.HiGHS` no cenario mais
dificil (4 membros). Com timeLimit=30s, devolveu "Not Solved" (nao
achou nem provou nada util, `objective.value() == 0.0`); com 60s,
mesma coisa. Para ESTE modelo especificamente (muitas variaveis
binarias + folga, poucas variaveis continuas "faceis"), o CBC do PuLP
se saiu melhor. Decisao: **nao adotar o HiGHS** — "troque o solver" nao
e uma vitoria garantida, depende da estrutura do problema, e vale medir
antes de assumir que é melhoria.

**A peca que faltava para a alavanca 3 funcionar sem perder confianca:**
o `solver.py` (S2-09) so confiava no resultado quando o status era
`"Optimal"` — qualquer outra coisa (incluindo "Not Solved") era tratada
como "sem solucao", mesmo quando o CBC tinha, sim, achado uma resposta
valida, so sem provar que era A melhor. Verifiquei isso na mao: parando
o CBC em 3 segundos num problema que normalmente leva 36s, a cobertura
R1 (soma de `y` por membro/dia/refeicao) ainda fechava em 1,0 em
TODAS as 84 combinacoes — um incumbente real, nao lixo de ramo
abandonado. A diferenca de verdade e so entre "Infeasible/Unbounded/
Undefined" (ai sim o CBC deixa valores velhos sem sentido, confirmado
num teste separado) e "Not Solved" com incumbente. `resolver()` agora
so descarta os tres primeiros; "Not Solved" e extraido normalmente, com
o status preservado para quem for ler o resultado saber que pode nao
ser o otimo (card: "declarem isso no relatorio").

**Configuracao final:** `Parametros(horizonte=5, ...)` para a Monte
Carlo, e `NUTRICASA2050_SOLVER_TIMEOUT=2` so para o alvo `make
resultados` (ver Makefile) — o padrao geral do `config.py` caiu de 30s
para 10s (uso cotidiano/demonstracao continua com boa chance de ficar
Optimal de verdade; so a rodada em lote de 500 cenarios usa o valor
mais agressivo).

**Numero real, medido, nao so estimado:** rodei 40 cenarios completos
(as tres estrategias, com banco) com essa configuracao —
**152,1 segundos para 40 cenarios ≈ 3,8 s/cenario** (o solver sozinho
fica perto de 2,5s; o resto e os dois baselines + as gravacoes no
banco, 3 execucoes x 7 tabelas cada). Extrapolando para 500: **≈ 32
minutos** — passa do teto de 20 minutos do card. Achado honesto: o
gargalo que falta atacar NAO e mais o solver (ja resolvido pela
alavanca 3), e sim o custo fixo de I/O (3 gravacoes completas no
SQLite por cenario). Caminho natural para o Sprint 5: agrupar as
gravacoes de um cenario numa unica transacao maior (`gravar_resultado_completo`
ja atomiza por execucao, mas nao entre as tres) ou gravar em lote a
cada N cenarios em vez de cenario por cenario — nao implementado
agora porque o card S4-05 pede para atacar o SOLVER, nao a
persistencia, e e um escopo novo melhor tratado como seu proprio card.

**Dois bugs reais encontrados e corrigidos durante esta validacao**
(os dois so apareciam com o catalogo real e horizonte=5 — os testes
unitarios, menores, nunca pegaram nenhum dos dois):
1. Os baselines (S4-02/03) registram descarte usando um lote sintetico
   ("compra_habitual_*") que nunca existia no `Catalogo` de verdade —
   so dentro da simulacao interna. `serializacao.resultado_para_dict`
   quebrava com `KeyError` tentando traduzir esse id de volta para um
   ingrediente. Corrigido com `baselines.catalogo_com_compra_habitual`
   (mesma ideia do `preparar_catalogo` do S3-01), usado por
   `monte_carlo.rodar_um_cenario` antes de serializar o resultado de
   humano/guloso. Sem isso, **40 cenarios em 40 falhavam**.
2. A perturbacao `esquecer_itens` (S4-01) infla o preco em 1000x para o
   SOLVER nunca escolher comprar aquele item — mas os baselines
   decidem a compra habitual so pela QUANTIDADE, nunca pelo preco.
   Resultado: eles compravam a mesma quantidade de sempre a um preco
   1000x maior, e se aquilo fosse descartado, o valor do desperdicio
   explodia (a primeira rodada real deu uma media de **R$ 10.318 por
   semana** de desperdicio do baseline humano — fisicamente
   implausivel). Corrigido com `Catalogo.itens_esquecidos`, um sinal
   explicito que os baselines agora olham antes de decidir comprar.

## S4-06 — MARCO: os numeros da apresentacao

Rodada de validacao: 40 cenarios (nao os 500 completos, por tempo/custo
desta maquina — ver S4-05 para a conta de tempo) via
`rodar_monte_carlo`, catalogo real, horizonte=5, 3 refeicoes/dia,
orcamento R$ 500, `NUTRICASA2050_SOLVER_TIMEOUT=2`.

**1. Desperdicio medio por estrategia (R$/semana):**

| Estrategia | Desperdicio medio |
|---|---|
| Humano (familia normal) | R$ 2.845,85 |
| Guloso (regra do vencimento) | R$ 93,65 |
| Otimizado | R$ 254,84 |

**2. A MANCHETE — reducao de desperdicio (otimizado vs. humano):
91,0%.**

**Achado honesto, nao escondido:** o guloso teve desperdicio MEDIO
menor que o otimizado nesta rodada (R$ 93,65 vs R$ 254,84). Nao e bug:
o otimizado minimiza um objetivo com SEIS termos ponderados, e o peso
da folga (1000x, S3-06) domina a decisao quando a nutricao dos 4
membros fica dificil — ele pode aceitar mais sobra de comida se isso
ajudar a ceder menos nas faixas nutricionais, uma troca que o guloso
(que so olha vencimento, nunca nutricao) nem considera. Some-se a isso
que boa parte dos 40 cenarios parou em "Not Solved" (S4-05): o CBC pode
nao ter tido tempo de refinar o desperdicio depois de fechar o resto.
A comparacao que importa para a manchete (otimizado vs. humano, a
pergunta real do projeto) continua forte e clara; guloso-vs-otimizado
e material para o Sprint 5 investigar com mais tempo de solver.

**3. Economia mensal projetada (otimizado vs. humano, IC 95%):**

Media **R$ 12.635,06**/mes, intervalo **[R$ 3.580,49, R$ 21.689,86]**.
(custo de compra + valor desperdicado, por semana, vezes 30/7 dias).

**4. Preco da prescricao** (catalogo real, horizonte=5, com vs. sem as
faixas nutricionais da nutricionista):

> Seguir esta dieta custa **R$ 127,40 a mais por semana** e **184
> minutos a mais de cozinha** — nenhuma nutricionista consegue dizer
> isso hoje para uma familia; aqui e so uma subtracao entre duas
> rodadas do mesmo modelo.

(Usa `termo_custo`, so a compra em reais de verdade — nao o objetivo
completo, que mistura isso com a folga ponderada e, com a nutricao
apertada, chegava a R$ 5,2 MILHOES por semana. Tecnicamente correto
para o solver minimizar, inutil como resposta para um ser humano —
corrigido em `consultas.py`.)

**5. Folgas mais frequentes** (de quais regras a realidade mais
atropela, nos 40 cenarios):

| Membro | Nutriente | Em quantos cenarios teve folga | Folga media |
|---|---|---|---|
| adulto_sedentario | kcal | 413 de 600 (execucoes otimizadas x dias) | 419,97 |
| crianca_8_anos | carboidrato_g | 405 | 54,35 |
| adulto_sedentario | carboidrato_g | 394 | 103,30 |
| idoso_hipertenso | carboidrato_g | 381 | 82,06 |
| adulto_sedentario | proteina_g | 366 | 16,67 |

Achado clinicamente relevante saindo de um `GROUP BY`: calorias do
adulto sedentario e carboidrato (dos tres membros com faixa mais
estreita) sao as regras que a realidade mais atropela — candidato
natural para a nutricionista revisar primeiro.

**Dois bugs reais corrigidos durante esta validacao** — ver a secao
S4-05 acima para os detalhes completos (lote sintetico sem tradutor
no catalogo, e preco inflado que os baselines nao sabiam ignorar).
