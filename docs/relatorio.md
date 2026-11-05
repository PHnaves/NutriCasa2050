# NutriCasa 2050 — Relatório final

> O trecho marcado **[A PREENCHER]** depende de uma fonte que o grupo
> ainda precisa citar.
> Nenhum número abaixo foi inventado: o que não está validado está dito.

## 1. O problema

Uma família decide toda semana o que cozinhar, o que comprar e o que usar
antes de vencer — sem enxergar o conjunto. O resultado típico é compra em
excesso, comida jogada fora e dieta que não respeita as necessidades de cada
pessoa (um idoso hipertenso, uma criança, etc.).

Dado o estoque, o orçamento, o tempo de cozinha e a prescrição de cada
membro, o NutriCasa 2050 escolhe cardápio, porções e lista de compras de
menor custo e menor desperdício.

**[A PREENCHER]** Dado estatístico de desperdício de alimentos em domicílios
brasileiros, com fonte citável.

## 2. Base acadêmica

O ponto de partida é o problema da dieta de Stigler (1945): entre 77
alimentos, achar a combinação de menor custo que atende 9 nutrientes — a
origem histórica da programação linear. O protótipo está em
`notebooks/00_stigler.ipynb`. O NutriCasa acrescenta três dimensões que o
problema original não tinha:

1. **Tempo:** restrição e custo de preparo (R11).
2. **Perecibilidade:** lotes com validade e descarte (R9, R10).
3. **Heterogeneidade:** cada pessoa com faixas, porções e restrições
   próprias (R5–R7).

## 3. O modelo

Programação linear inteira mista (PuLP + CBC). Formulação completa, com as
12 restrições, em [formulacao.md](formulacao.md). Em resumo:

- **Decisões:** quais pratos cozinhar (binária), quanto cada pessoa come
  (fração), quantas embalagens comprar (inteira), e variáveis auxiliares de
  estoque por lote, folga e desvio.
- **Objetivo:** seis termos, todos em reais — compra, desperdício, tempo de
  cozinha, repetição, folga nutricional (peso 1000) e desvio do alvo.
- **Restrições:** cardápio (R1–R4), nutrição (R5–R7), estoque e validade
  (R8–R10), operacional (R11–R12). R10 é o coração anti-desperdício.
- **Tamanho** (catálogo real, horizonte 5, 4 pessoas): 504 binárias de
  cozimento, 2016 frações, 50 inteiras de compra, 4360 restrições.

## 4. Implementação

Python 3.11; `src/nutricasa2050/` com domínio, dados, otimização,
simulação, análise e persistência (SQLite); interface Streamlit (`app.py`);
CI com ruff, pytest e container Docker; imagem publicada no ghcr.io.
Mapa de arquivos no [README](../README.md).

## 5. Resultados

### 5.1 O que está validado

- **Anti-desperdício funciona e é causal.** Em um cenário controlado
  (`tests/integracao/test_coracao.py`), com o ingrediente vencendo, o
  modelo cozinha o prato que o consome e descarta 0 kg de tomate; com o peso
  do desperdício zerado (e a regra de validade mantida), descarta
  mais de 0,5 kg. O teste foi desenhado para separar o efeito do peso de
  outros fatores (preço e tempo iguais entre as receitas).
- **Preço-sombra** por diferença finita, porque o dual do CBC não é
  confiável em MIP (ver `analise/sensibilidade.py`).

### 5.2 Desempenho e uma correção importante

Cada solução real leva de 10 a 60 s no catálogo completo. Quando o tempo
limite estoura, o CBC pode devolver apenas a **relaxação linear** (pratos
fracionados), que parece uma resposta válida. Isso foi tratado errado nos
Sprints 3–4 e corrigido no 6: `resolver` agora verifica a integralidade e
descarta o resultado se ela falhar. Detalhes e medições em
[resultados.md](resultados.md). Também: "Optimal" com tempo limite estourado
é a melhor solução *encontrada*, não provada ótima.

### 5.3 Monte Carlo (os números da apresentação)

Rodada de 100 cenários (horizonte 5, orçamento 500, tempo limite 30 s, 0
falhas):

| Número | Valor |
|---|---|
| Redução de desperdício vs. família normal | 77,1% |
| Economia projetada por mês (IC 95%) | R$ 9.136 [4.649 ; 13.623] |
| Preço da prescrição (ordem de grandeza) | +R$ 174/semana, +294 min de cozinha |
| Folga mais frequente | fibra do idoso hipertenso; carboidrato da criança |

Ressalva: o baseline guloso desperdiça menos (R$ 92 contra R$ 578 do
otimizado por semana), porque o otimizado aceita desperdício para cumprir a
nutrição; a vantagem do modelo é contra a família normal e na aderência.
Com tempo limite de 30 s a solução está longe do ótimo provado.

Os valores publicados antes (91,0%, R$ 12.635/mês) foram invalidados.

## 6. Limitações

- Horizonte de 5 dias; semana de 7 dias não resolve no tempo razoável com o
  CBC (testado também com HiGHS, pior).
- Qualidade da solução depende do tempo limite; não há prova de otimalidade.
- Dados de preço e composição vêm de tabelas estáticas, sem atualização.
- Baselines (humano e guloso) são simplificações; o "humano" é uma regra
  fixa, não observação de famílias reais.
- Publicação online do app pendente (S5-08).

## 7. Conclusão e próximos passos

O modelo reproduz, com tempo e perecibilidade, o espírito do problema de
Stigler e comprova com teste que o desperdício cai *por causa* do termo de
custo e da regra de validade. Os percentuais acima vêm de 100 cenários, não 500. Próximos passos: solver mais forte ou decomposição
para horizonte de 7 dias, dados reais de preço e publicação do app.
