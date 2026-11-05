# Roteiro do vídeo pitch: NutriCasa 2050

**Formato:** vídeo de cerca de 3 minutos, com **duas pessoas**: **A**
(apresenta o problema e a ideia) e **B** (mostra o app e os números). As
falas são sugestões. Falem do jeito de vocês, mas mantenham os números
**exatamente** como estão aqui: todos têm fonte em `docs/resultados.md` ou em
`docs/relatorio.md`.

**Preparação:** app aberto em 1920×1080, com zoom de 125% no navegador.
Aqueça o cache antes de gravar: na página **Planejar a semana**, rode uma vez
cada imprevisto que vai aparecer (Semana normal, Filho celíaco, Orçamento −30%),
para nenhum cálculo de 15 s aparecer no vídeo. Use o mesmo fundo para as duas
pessoas e microfone de lapela ou fone. Grave cada cena separada e edite depois.

---

## Cena 1: o gancho (0:00–0:20) · A, em câmera

> **A:** Cada brasileiro joga fora, em média, **41 quilos de comida por ano**
> dentro de casa. Não é no mercado, nem na lavoura: é na nossa geladeira.
> E quase sempre pelo mesmo motivo: a gente comprou sem planejar e a comida
> venceu antes de ser usada.

*Na tela:* "41,6 kg por pessoa por ano · Embrapa/FGV". Corte para uma
geladeira com um tomate passado.

## Cena 2: por que não é só "uma receita" (0:20–0:45) · A

> **A:** A ideia óbvia seria um app que sugere receitas. Só que sugerir é
> palpite. A pergunta real é maior: **o que cozinhar, quanto cada pessoa
> come e o que comprar**, tudo ao mesmo tempo, sem estourar o orçamento,
> sem passar do tempo que a família tem para cozinhar, respeitando a dieta
> de cada um e usando primeiro o que vence primeiro.
>
> Isso não é recomendação. É um **problema de otimização**.

*Na tela:* os quatro blocos aparecem um a um: Cardápio, Nutrição, Estoque,
Tempo e orçamento.

## Cena 3: a base (0:45–1:05) · B, em câmera

> **B:** Em 1945, o economista George Stigler perguntou qual era a dieta
> mais barata que atendia às necessidades de nutrientes de uma pessoa. Essa
> pergunta ajudou a nascer a programação linear. O NutriCasa parte dela e
> acrescenta três coisas que a vida real tem: **tempo de cozinha**, **comida
> que vence** e **uma família de verdade**, com um idoso hipertenso, uma
> criança e dois adultos, cada um com a sua dieta.

*Na tela:* "Stigler, 1945, 77 alimentos e 9 nutrientes" e, abaixo, "+ tempo
+ validade + cada pessoa".

## Cena 4: a demonstração (1:05–2:05) · B, tela do app

*Ação:* no menu do topo, **Planejar a semana**. Mostre rapidamente o
formulário: quem está em casa, orçamento, tempo de cozinha, dias.

> **B:** Esta é a semana da família. O modelo escolheu o cardápio, a porção
> de cada um e a lista de compras. Os pratos com **borda laranja** usam algo
> da despensa que vence em até dois dias. Ninguém programou "use o que vence
> antes". O modelo faz isso sozinho, porque jogar comida fora custa dinheiro.

*Ação:* passe o mouse pela grade do cardápio e pelos pratos de borda laranja.
Embaixo de cada prato aparece quem come dele.

> **B:** Agora a vida acontece. **O filho é celíaco.**

*Ação:* em "Aconteceu algum imprevisto?", escolha **Filho celíaco** e clique
em **Planejar a semana**. O cardápio se refaz.

> **B:** O modelo achou pratos sem glúten **para a criança**, e o resto da
> casa não precisa mudar tudo. Repare no nome do Leo embaixo dos pratos. E
> se o dinheiro apertar?

*Ação:* escolha **Orçamento −30%** e clique em **Planejar a semana**.

> **B:** Ele replaneja tudo dentro do novo orçamento e mostra quais regras da
> nutricionista ficaram mais difíceis de cumprir. Ele não esconde isso.

*Ação:* aba **Nutrição**: as bolinhas laranja são os nutrientes que saíram
da faixa.

## Cena 5: os números (2:05–2:35) · A e B, alternando

*Ação:* no menu do topo, **Resultados**.

> **A:** Para não depender de um caso de sorte, rodamos **100 semanas
> simuladas**, com preços, validades e visitas sorteados.
>
> **B:** Contra uma família que compra sempre a mesma lista, o NutriCasa
> desperdiçou **64% menos**.
>
> **A:** E uma regra simples, "cozinhe o que vence primeiro", desperdiça
> mais ou menos o mesmo que o NutriCasa. Só que ela **ignora a dieta** e
> gasta mais no mercado. O NutriCasa chega ao mesmo desperdício **com cada
> pessoa da casa comendo o que precisa**. Esse é o equilíbrio que um
> palpite não consegue fazer.

*Na tela:* "−64% de desperdício vs. família típica (100 semanas simuladas)".

## Cena 6: o fechamento (2:35–3:00) · A e B juntos em câmera

> **B:** O NutriCasa 2050 é código aberto, testado automaticamente e roda no
> navegador.
>
> **A:** Porque planejar a semana não deveria significar jogar comida fora.
>
> **A e B:** NutriCasa 2050.

*Na tela:* logo, link do app e do GitHub, e os nomes do grupo.

---

## O que NÃO dizer (e por quê)

- **"Economia de R$ 9 mil por mês."** O número sai da simulação
  (`docs/resultados.md`), mas a família de comparação compra quantidades
  fixas grandes de propósito. Em reais absolutos, ele não representa uma
  família real. No vídeo use a **porcentagem**, que compara dois cenários
  com os mesmos dados.
- **"O cardápio ótimo."** Com tempo limite, o solver devolve a melhor
  resposta **encontrada**, não uma resposta provada ótima. Diga "o melhor
  cardápio que o modelo encontrou" ou só "o cardápio".
- **"Seguir a dieta custa exatamente R$ 333 a mais."** É uma ordem de
  grandeza, calculada com tempo limite. Se perguntarem, diga "na casa das
  centenas de reais por semana, no nosso cenário".
- **"91%" ou "77%".** São números antigos, invalidados no Sprint 6 (ver
  `docs/resultados.md`).
- **"Preços do Carrefour."** Os preços são do **Atacadão** (do Grupo
  Carrefour), coletados em 05/11/2026, e 8 dos 50 são estimativas.

## Ficha técnica para a legenda ou a descrição do vídeo

Python · programação linear inteira mista (PuLP + CBC) · 12 restrições ·
Streamlit · SQLite · Docker · simulação Monte Carlo com 100 cenários.
Fonte do dado de desperdício: Embrapa e FGV, pesquisa "Intercâmbio
Brasil–União Europeia sobre desperdício de alimentos" (Porpino et al.),
divulgada em 2018/2019.
