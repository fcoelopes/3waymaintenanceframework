# Modelo matemático do 3Way Maintenance Framework

## 1. Objetivo

O framework separa três decisões distintas:

1. **prioridade** — quais ativos merecem atenção;
2. **oportunidade** — quando existe uma janela temporal adequada;
3. **ação** — qual combinação de intervenções produz a melhor consequência
   sistêmica dentro da janela.

A separação evita misturar preferência multicritério com consequência física.

---

## 2. Camada 1 — FUCOM + PROMETHEE II

Considere critérios ordenados por importância e razões comparativas
`phi_(k/(k+1))`.

O FUCOM resolve:

```text
min chi
```

sujeito a:

```text
|w_k / w_(k+1) - phi_(k/(k+1))| <= chi
|w_k / w_(k+2) - phi_(k/(k+1))*phi_((k+1)/(k+2))| <= chi
sum(w_k) = 1
w_k >= 0
```

Os pesos alimentam o PROMETHEE II. O fluxo líquido `phi_net` produz o ranking
estratégico, mas **não entra** na função objetivo da camada operacional.

---

## 3. Camada 2 — Bruss X·RUL

Para um ativo com idade atual `a`, Weibull `(beta, eta, gamma)` e uma
oportunidade que ocorrerá daqui a `t_i`, define-se a sobrevivência residual:

```text
S_RUL(t_i | a) = P(T > a+t_i | T > a)
               = R(a+t_i) / R(a)
```

A implementação usa a forma algébrica equivalente em expoentes para evitar
underflow numérico.

Para uma janela de duração `d_i`:

```text
M(d_i) = P(T_reparo <= d_i)
p_i    = M(d_i) * S_RUL(t_i | a)
odd_i  = p_i / (1-p_i)
```

As odds alimentam a regra de Bruss usada para ranquear oportunidades.

**Interpretação importante:** `t_i` é tempo até a oportunidade; não é idade do
componente.

---

## 4. Camada 3 — RBD completo + Selective Maintenance

A parada selecionada fornece a janela `T0`.

Se o componente `j` tem idade atual `a_j`, sua idade projetada no início da
parada é:

```text
a_j^stop = a_j + t_stop
```

O sistema é representado por um RBD completo. Seja `C` o conjunto de todos os
componentes do sistema e `K subset C` o conjunto de candidatos Bruss.

Para `j not in K`:

```text
acao_j = none
```

Esses componentes continuam presentes em `R_sys`.

Para os candidatos, o solver escolhe entre as ações permitidas. No modo
estocástico:

```text
max R_sys(S)

sujeito a:
P(T_portfolio(S) <= T0) >= alpha
```

As durações são amostradas por ação a partir de distribuições lognormais
parametrizadas por média (MTTR da ação) e desvio-padrão.

---

## 5. Contrato entre as camadas

```text
FUCOM/PROMETHEE
      |
      | top-N / prioridade
      v
Bruss X RUL condicional
      |
      | parada + T0
      v
RBD completo + Selective Maintenance
      |
      | ativo x parada x ação
      v
estratégia de manutenção
```

Se um candidato recebe `none`, ele retorna à camada temporal para consulta da
próxima oportunidade ranqueada.

---

## 6. Hipóteses do MVP

- Weibull estável no horizonte analisado;
- sem atualização dinâmica de condição entre agora e a oportunidade;
- duração das ações independente;
- execução serial/equivalente das ações;
- RBD decomponível em série/paralelo;
- sem common cause;
- sem custo e sem múltiplos recursos/equipes;
- a adaptação de Bruss é tratada como regra de seleção temporal sob as hipóteses
  do modelo, não como prova de optimalidade universal.

Essas hipóteses devem ser explicitadas em qualquer artigo ou experimento.
