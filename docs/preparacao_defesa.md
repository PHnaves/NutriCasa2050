# Preparação para a sabatina (cards S6-04 e S6-05)

Respostas curtas para as **dez perguntas** e as **três perguntas-armadilha**
do card S6-04, cada uma apontando **onde está a prova** (código, teste ou
medição). Isto não é para decorar. Leia, abra o arquivo indicado e explique
com as suas palavras. O formato que resolve quase tudo:

> "Essa restrição existe porque *[motivo do mundo real]*. Se ela saísse,
> aconteceria *[consequência concreta]*."

## As dez perguntas

**1. Por que a regra da validade (R10) existe e o que acontece se ela sair?**
Comida vencida não pode ser servida. R10 obriga que todo lote vencido saia
do estoque **como descarte**, e descarte custa dinheiro no objetivo. Sem
ela, o modelo "comeria" tomate podre no papel e o desperdício ficaria
sempre zero, o que é falso. Mostre `r10_validade_por_lote` em
`otimizacao/restricoes.py` e `tests/integracao/test_coracao.py`.

**2. O que acontece se tirar a regra da variedade (R4)?**
O modelo repetiria o prato mais barato e nutritivo a semana toda (arroz,
feijão e ovo no café, no almoço e no jantar). É matematicamente ótimo e
humanamente inaceitável. R4 limita cada receita a 2 vezes por semana e
proíbe dias seguintes. A medição está em `docs/resultados.md`, seção S3-04.

**3. Por que otimização e não testar todas as combinações?**
Só a decisão "cozinhar ou não" já tem 504 variáveis binárias (24 receitas ×
5 dias × 3 refeições + …), ou seja, 2⁵⁰⁴ combinações, mais do que átomos no
universo, antes ainda de porções e compras. O branch-and-bound do CBC
descarta regiões inteiras sem visitá-las, usando a relaxação linear como
limite.

**4. O que é preço-sombra e o que o de vocês diz?**
É quanto o objetivo melhora se uma restrição afrouxar 1 unidade (uma
derivada). Num MIP, o `.pi` do solver não é confiável: ele devolveu 0 até
para restrição apertada. Por isso calculamos por **diferença finita**:
resolvemos de novo com o limite +1 e subtraímos (`analise/sensibilidade.py`).
O botão "Afrouxar sódio" mostra isso ao vivo.

**5. Por que os termos do objetivo precisam estar todos em reais?**
Somar reais com minutos e com gramas faz o peso depender da unidade, não da
importância. Em reais (minuto = R$ 0,10, folga = R$ 1000 por unidade), o
objetivo lê-se como "quanto a semana custa, contando tudo", e cada peso
vira uma decisão explícita.

**6. Por que a porção é um número fracionário e não sim/não?**
Porque comer **metade** do prato é real, e a criança come 60% da porção do
adulto. Deixar y contínuo também deixa o problema bem mais fácil. Só "o
prato foi cozinhado" (x) e "quantas embalagens comprar" (b) precisam ser
inteiros.

**7. O que significa a folga ser maior que zero?**
Que naquele dia, para aquela pessoa, não foi possível ficar dentro da faixa
do nutriente. O modelo **cedeu** e diz quanto. Sem a folga, o problema ficaria
inviável ("não existe cardápio") com facilidade. O resultado: a regra mais
atropelada é a **fibra do idoso hipertenso** (1173 ocorrências em 100
cenários).

**8. Por que fecharam a lista de ingredientes ANTES das receitas?**
Para não sobrar ingrediente "órfão", usado por uma receita só. Ele vira
lixo quase com certeza, porque a embalagem é maior que a porção. A análise de
grafos (`analise/grafos.py`) confirma: o catálogo final tem 0 órfãos.

**9. Por que dois pratos por refeição e não quatro?**
Realismo (uma casa comum faz um prato principal e, às vezes, um
acompanhamento) e tamanho do problema: cada prato a mais por refeição
multiplica as combinações que o solver precisa considerar. É a R3.

**10. Onde está a linearização do valor absoluto e por que ela é necessária?**
Na R7 (`r7_desvio_do_alvo`). |consumo − alvo| não é linear, e o solver só
aceita expressões lineares. Criamos s⁺ e s⁻ ≥ 0 com consumo − alvo = s⁺ − s⁻
e minimizamos s⁺ + s⁻. No ótimo, só uma delas é positiva e a soma é o
valor absoluto.

## As três perguntas-armadilha

**"Se eu dobrar o orçamento, o desperdício aumenta ou diminui?"**
*Depende de o orçamento estar apertando ou não*, e nós medimos. Com 4
pessoas e 5 dias, R$ 500 e R$ 800 deram **exatamente a mesma solução**: o
modelo gasta cerca de R$ 365 porque não precisa de mais, e dinheiro sobrando
não compra nada a mais, já que comprar e jogar fora custa. Já com o
orçamento **abaixo** do necessário (R$ 300), não existe cardápio inteiro
viável no tempo limite. Moral: a R12 só influencia quando está ativa, e o
preço-sombra dela é zero quando ela folga.

**"E se tirassem o termo de desperdício do objetivo, mas mantivessem R10?"**
R10 continua obrigando o vencido a sair como descarte, mas jogar fora passa a
ser "de graça". O modelo deixa de preferir o que vence primeiro. Testado em
`test_sem_custo_de_desperdicio_o_tomate_vence`: com o peso do desperdício
zerado, o tomate passa a vencer (descarte > 0,5 kg). Com o peso normal, o
descarte é 0. R10 garante a **contabilidade**; o termo de custo dá a
**motivação**.

**"Vocês poderiam ter usado um algoritmo guloso. Por que não usaram?"**
Nós implementamos um guloso, para comparar (`simulacao/baselines.py`). E
somos honestos: ele desperdiça **menos** que o modelo (R$ 92 contra R$ 578 por
semana). Só que ele faz isso **ignorando a dieta**: cozinha o que vence, sem
olhar se o idoso passou do sódio ou se a criança comeu o suficiente. Um
guloso decide uma refeição de cada vez e não consegue trocar um pouco de
sobra hoje por cumprir a nutrição da semana. O modelo equilibra os seis
objetivos ao mesmo tempo e garante as restrições duras (R1 a R4, R6, R10 a
R12). Contra a família normal, o modelo reduz o desperdício em 77%.

## Perguntas prováveis sobre o Sprint 6

- **"Esses números são os mesmos de antes?"** Não. No Sprint 6 descobrimos
  que, quando o tempo limite acabava antes de qualquer solução inteira, o
  código aceitava a relaxação linear (pratos fracionados). Corrigimos
  (`solucao_e_inteira`), refizemos a simulação, e a redução caiu de 91% para
  77,1%. Mostrar o erro e a correção é melhor do que defender um número
  errado.
- **"A solução é ótima?"** É a melhor **encontrada** dentro do tempo limite.
  Com 10 s e com 60 s, o mesmo cenário teve objetivo 36× diferente
  (`docs/resultados.md`).
- **"Por que 100 cenários e não 500?"** Cada cenário com solução inteira de
  verdade leva cerca de 30 s. 500 cenários levariam cerca de 4,5 h. O
  intervalo de confiança da economia está publicado junto com o número.
- **"Me mostre no código onde está o R10."** Em `restricoes.py`, procure
  `def r10`. A docstring tem "(a) o que faz" e "(b) se sair".
