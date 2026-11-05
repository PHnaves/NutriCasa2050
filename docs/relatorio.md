# NutriCasa 2050: relatório final

> Os números deste relatório vêm de rodadas reais do solver, registradas em
> [resultados.md](resultados.md). Onde um número tem ressalva, ela está
> escrita ao lado dele.

## 1. Problema e motivação

Cada brasileiro desperdiça em média **41,6 kg de alimentos por ano dentro
de casa**; uma família de até três pessoas, cerca de 128 kg (Embrapa e FGV,
pesquisa "Intercâmbio Brasil–União Europeia sobre desperdício de
alimentos", Porpino et al., 2018). Arroz, carne, feijão e frango lideram a
lista. A maior parte desse desperdício nasce no planejamento: compra-se por
hábito, sem saber o que vai ser cozinhado, e o que vence primeiro não é
usado primeiro. O UNEP Food Waste Index Report 2024 estima, para o Brasil,
94 kg por pessoa por ano, mas essa medida inclui partes não comestíveis e
não é comparável com a anterior.

**Por que isso é otimização e não recomendação.** Um app que sugere
receitas responde "o que eu poderia cozinhar?". A família precisa decidir,
**ao mesmo tempo**, o cardápio da semana, quanto cada pessoa come e o que
comprar, sob um orçamento, um tempo de cozinha diário, a validade de cada
lote na despensa e a dieta de cada pessoa. Essas decisões dependem umas das
outras. Escolher um prato muda o estoque, que muda a compra, que muda o
custo. Sugerir uma receita de cada vez (uma heurística) não enxerga essa
interação. Um modelo de programação matemática enxerga, e devolve a melhor
combinação que encontrou, com a garantia de que todas as regras foram
respeitadas ou de que a violação foi medida e penalizada.

## 2. Formulação

A formulação completa (conjuntos, parâmetros, variáveis, objetivo e as
doze restrições, cada uma com "o que faz" e "o que acontece se sair") está
em [formulacao.md](formulacao.md). Este é o resumo.

### 2.1 Base acadêmica

O ponto de partida é o **problema da dieta de Stigler (1945)**: entre 77
alimentos, achar a combinação de menor custo que atende 9 nutrientes. É uma
das origens históricas da programação linear, resolvida depois com o
simplex. O protótipo está em `notebooks/00_stigler.ipynb`. O NutriCasa
acrescenta **três dimensões** que o problema original não tinha:

1. **Tempo:** cada receita tem tempo de preparo, há um limite diário (R11)
   e o tempo entra no objetivo.
2. **Perecibilidade:** o estoque é controlado **por lote**, cada lote com sua
   data de vencimento (R9), e o que vence sai como descarte (R10).
3. **Heterogeneidade:** quatro pessoas, cada uma com faixas nutricionais,
   tamanho de porção e restrições alimentares próprias (R5 a R7).

### 2.2 Variáveis

| Símbolo | Tipo | Significado |
|---|---|---|
| x | binária | a receita r é cozinhada no dia d, na refeição m |
| y | contínua [0,1] | fração do prato que cada pessoa come |
| b | inteira | embalagens compradas de cada ingrediente, em cada dia de compra |
| s, u, w | contínuas | estoque, consumo e descarte por lote e dia |
| f⁻, f⁺ | contínuas | folga: quanto faltou ou sobrou da faixa nutricional |
| s⁺, s⁻ | contínuas | desvio acima e abaixo do alvo prescrito |

Tamanho com o catálogo real (horizonte de 5 dias, 4 pessoas): 504 binárias,
2016 frações, 50 inteiras e 4360 restrições.

### 2.3 Objetivo

Minimizar a soma de seis termos, **todos em reais**: custo de compra, valor
desperdiçado, tempo de preparo (R$ 0,10 por minuto), desvio do alvo,
folga nutricional (peso 1000) e perda de preferência.

### 2.4 As doze restrições

| Bloco | Restrições |
|---|---|
| A, Cardápio | R1 cobertura · R2 vínculo prato/porção · R3 até 2 pratos por refeição · R4 variedade |
| B, Nutrição | R5 faixas com folga · R6 restrição individual (ex.: sem glúten só para a criança) · R7 desvio do alvo |
| C, Estoque | R8 consumo derivado · R9 balanço por lote · **R10 validade** (o coração do projeto) |
| D, Operacional | R11 tempo de preparo · R12 orçamento |

## 3. Implementação e decisões técnicas

**Arquitetura em camadas.** `dominio.py` (dataclasses) ← `dados/` (leitura
e validação dos CSV/JSON) ← `otimizacao/` (variáveis, restrições,
objetivo, solver) ← `simulacao/` e `analise/` ← `app.py`. A tela não faz
conta nenhuma: só liga widgets a funções de `src/`. `serializacao.py`
converte qualquer solução, do solver ou de um baseline, no **mesmo
dicionário**, usado pela tela, pelo banco e pelos gráficos.

**Por que SQLite e não Postgres.** O app é um processo só, roda no
notebook de quem apresenta e na nuvem gratuita, e os dados são de
escrita única (a simulação grava, as consultas leem). SQLite é um arquivo,
não precisa de servidor e pode ser versionado (`var/results.db` vai junto
com o app hospedado). Postgres traria servidor, credenciais e rede, sem
nenhum ganho para esse volume de dados. Testes e simulação usam **bancos
separados** por variável de ambiente, para que um teste nunca toque nos
resultados reais.

**Por que todos os termos do objetivo estão em reais.** Somar "reais" com
"minutos" com "gramas de proteína" faz o peso relativo depender da unidade
escolhida, não da importância. Convertendo tudo para reais (minuto vale
R$ 0,10, folga nutricional vale R$ 1000 por unidade), o objetivo pode ser
lido como "quanto essa semana custa, contando tudo", e os pesos viram
decisões explícitas e discutíveis.

**Linearização do valor absoluto (R7).** O desvio do alvo é |consumo −
alvo|, que não é linear. Introduzem-se s⁺ ≥ 0 e s⁻ ≥ 0 com consumo − alvo
= s⁺ − s⁻ e minimiza-se s⁺ + s⁻. No ótimo, no máximo uma das duas é
positiva e a soma é exatamente o valor absoluto.

**Folga em vez de inviabilidade (R5).** Uma faixa nutricional dura deixa o
modelo inviável com facilidade (basta um ingrediente faltar). Com folga
penalizada, o modelo sempre devolve um cardápio e **mede** quanto cada regra
foi violada. Essa medida virou um resultado (seção 5).

**Desempenho e uma correção.** O CBC raramente prova otimalidade no
catálogo completo, então o solver roda com tempo limite (padrão de 10 s no
app, 30 s na simulação). No Sprint 6 descobrimos que, quando o tempo acaba
**antes** de existir uma solução inteira, o PuLP devolve os valores da
**relaxação linear** (pratos "0,3 cozinhados"), que parecem válidos.
`resolver()` agora verifica a integralidade (`solucao_e_inteira`) e
descarta essas respostas. Os números de simulação antigos foram refeitos.

**Qualidade.** 184 testes automatizados (incluindo um que abre o app inteiro com o Streamlit AppTest) (pytest), lint (ruff), CI no GitHub
Actions com um job que prova que o solver funciona **dentro** do container
Docker, e imagem publicada no ghcr.io a cada versão.

## 4. Simulação e metodologia

**Cenários.** Cada cenário é uma semana levemente diferente da padrão,
sorteada a partir de uma semente (reprodutível): cada preço varia até ±15%,
pode chegar uma visita (1 em 4), até 2 refeições não acontecem, até 3
ingredientes são esquecidos na compra e até 2 lotes estragam antes do
previsto. As três estratégias rodam sobre **os mesmos dados perturbados**,
e há um teste que garante isso.

**Por que dois baselines.** Com um baseline só, não dá para separar o que
vem da otimização do que vem de uma regra óbvia.

- **Família normal (humano):** escolhe pelo gosto, compra a lista habitual
  (sem olhar o cardápio) e não confere o que vence primeiro. É a referência
  da manchete.
- **Guloso:** a mesma compra habitual, mas cozinha primeiro o que vence
  primeiro. Ele responde à pergunta: "uma regra simples já não resolveria?"

**Rodada oficial.** 100 cenários × 3 estratégias, horizonte de 5 dias,
3 refeições por dia, orçamento de R$ 900, preços do Atacadão (05/11/2026),
tempo limite de 30 s, 0 falhas, cerca de 55 minutos de execução. O card pedia 500 cenários: com soluções inteiras de
verdade, cada cenário leva cerca de 30 s, e 500 levariam cerca de 4,5 h.

## 5. Resultados

### 5.1 O comportamento emergente (S3-08)

Ninguém programou "use primeiro o que vence antes". Num cenário controlado
(`tests/integracao/test_coracao.py`), com tomate perto de vencer e receitas
com preço e tempo equivalentes, o modelo cozinha os pratos com tomate e
**descarta 0 kg**. Zerando apenas o peso do desperdício, com a regra de
validade mantida, ele passa a descartar mais de 0,5 kg. O comportamento vem
do termo de custo do desperdício, não de uma regra escrita à mão.

### 5.2 Os quatro números

| Número | Valor | Leitura |
|---|---|---|
| Redução de desperdício vs. família normal | **63,7%** | R$ 122,88 contra R$ 338,00 por semana, em média |
| Economia projetada por mês (IC 95%) | R$ 2.158 [2.097 ; 2.219] | compras + desperdício; ver ressalva abaixo |
| Preço da prescrição | **+R$ 333 por semana e +301 min de cozinha** | seguir as faixas da nutricionista, contra não segui-las |
| Regra mais atropelada | **fibra do idoso hipertenso** (1181 ocorrências), depois carboidrato da criança e proteína dos adultos | consulta `GROUP BY` sobre a folga |

**Ressalvas.**

1. **O guloso empata em desperdício** (R$ 119,55 contra R$ 122,88 por
   semana), mas cozinha o que vence sem olhar a dieta. O NutriCasa chega ao
   mesmo desperdício **cumprindo as faixas nutricionais** e comprando
   menos (R$ 520 contra R$ 809 por semana, porque o guloso usa a compra
   habitual da família normal). A vantagem não é desperdício absoluto: é
   desperdiçar tão pouco quanto a melhor regra simples sem abrir mão da
   dieta.
2. **A economia em reais** vem principalmente da compra: a família normal
   compra uma lista habitual com 30% de margem sobre a média do catálogo.
   A porcentagem de desperdício compara cenários idênticos e é o número
   que defendemos.
3. **Correção no Sprint 6.** Um item "esquecido na compra" era simulado com
   preço ×1000, e esse preço também valorava o descarte do estoque inicial
   do item: 88% do desperdício medido era esse artefato. Corrigido (o item
   agora só é bloqueado na compra) e a simulação foi refeita. Por isso a
   redução mudou de 77,1% para 63,7%.
4. **O preço da prescrição** vem de duas soluções com tempo limite. Deve ser
   lido como ordem de grandeza.

### 5.3 Gráficos

Em `notebooks/01_analise.ipynb`: a fronteira de Pareto custo × desperdício
("não existe almoço grátis"), a fronteira custo × aderência, a distribuição
das três estratégias nos cenários, a região viável em 2D com curvas de nível
(o ótimo cai num vértice) e o grafo bipartido receita–ingrediente, com os
ingredientes órfãos. O app hospedado mostra os números da simulação na página
"Resultados".

## 6. Limitações e premissas declaradas

- **Preços de um único mercado, numa única data**: Atacadão (loja online,
  sem CEP), em 05/11/2026. 42 dos 50 preços foram coletados; 8 itens sem
  oferta no dia ficaram como estimativa (`data/precos_coletados.csv`). A
  simulação varia ±15%, mas não modela promoções nem sazonalidade.
- **Todos comem porções da mesma receita** numa refeição (no máximo 2
  pratos). Não há "um prato para cada um".
- **Sem reaproveitamento de sobras** entre refeições: o que não se come do
  prato não volta ao estoque.
- **Horizonte de 5 dias** na simulação. Sete dias resolvem no app, mas
  demoram mais e com qualidade pior. O HiGHS foi testado e foi mais lento.
- **Sem prova de otimalidade:** as respostas são as melhores encontradas
  dentro do tempo limite. Com 10 s e com 60 s, o objetivo chegou a variar
  36×.
- **Baselines são regras fixas**, não observação de famílias reais.
- **100 cenários, não 500**, pelo tempo de execução (seção 4).
- **Visitante fica a semana toda**, sem presença parcial.

## 7. Trabalhos futuros

- **Designação de nutricionistas a famílias.** Dado um conjunto de
  nutricionistas (com especialidade, agenda e região) e de famílias (com
  perfis clínicos), atribuir cada família a um profissional minimizando
  deslocamento e incompatibilidade. É um problema de designação clássico de
  Pesquisa Operacional e ficou fora do escopo de propósito.
- Solver mais forte (comercial, ou decomposição por dia) para a semana de 7
  dias com prova de otimalidade.
- Preços reais via API de supermercado e validade lida da nota fiscal.
- Reaproveitamento de sobras como novo tipo de lote.
- Validar o baseline humano com o diário de compras de famílias reais.
