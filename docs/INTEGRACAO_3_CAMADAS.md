# Integração das três camadas

## Contratos

### 1. FUCOM + PROMETHEE II — QUAIS ativos

O FUCOM recebe os critérios já ordenados por importância e as razões comparativas
entre critérios consecutivos. Os pesos são obtidos resolvendo explicitamente o
problema de minimização da **deviation from full consistency (DFC)**:

```text
min chi
```

sujeito às relações `w_k / w_(k+1) ≈ phi_k,k+1`, à transitividade
`w_k / w_(k+2) ≈ phi_k,k+1 * phi_k+1,k+2`, à normalização e à não
negatividade dos pesos.

Saída do PROMETHEE: `ResultadoPROMETHEE` com `rank` e `phi_net` por ativo.

O ranking seleciona o top-N que segue para a camada temporal. O fluxo PROMETHEE
**não** é somado à função objetivo operacional para evitar dupla contagem de
preferência/criticidade.

### 2. Bruss X·RUL — QUANDO

Entrada: top-N + agenda de paradas + idade atual + Weibull + MTTR/σT.

A agenda usa `inicio` como **tempo a partir de agora**. Para um ativo com idade
atual `a`, a sobrevivência até uma oportunidade em `t_i` é calculada como
sobrevivência residual condicional:

```text
S_RUL(t_i | a) = R(a + t_i) / R(a)
```

Para cada ativo/parada:

```text
p_i = M(d_i) * S_RUL(t_i | a)
```

Assim, uma parada daqui a 200 h não é tratada como se o componente tivesse apenas
200 h de idade.

Saída: `ResultadoBrussAtivo`, contendo oportunidades ranqueadas e
`parada_otima_id`.

A duração da parada escolhida fornece diretamente `T0` ao Selective Maintenance.

### 3. RBD completo + Selective Maintenance — O QUÊ

Entrada:

- todos os componentes pertencentes ao sistema/RBD;
- candidatos que apontaram para a mesma parada;
- topologia RBD completa;
- parâmetros Weibull e duração das ações.

A idade de um componente no início da janela é:

```text
idade_na_parada = idade_atual + inicio_da_parada
```

Apenas os candidatos podem receber ações diferentes de `none`. Componentes não
candidatos continuam presentes na topologia e afetam `R_sys`, mas ficam fixados
em `none`.

A viabilidade estocástica é:

```text
P(T_portfolio <= T0) >= alpha
```

e o objetivo inicial é:

```text
max R_sys
```

O motor rejeita um RBD que omita algum componente declarado como pertencente ao
sistema.

## Fallback temporal

Se um ativo candidato não recebe ação (`none`) porque o portfólio ótimo usa a
janela em outras intervenções, `framework.proxima_oportunidade()` aponta a
próxima oportunidade ranqueada no resultado Bruss.

## Escopo do MVP

- FUCOM resolvido por otimização;
- PROMETHEE II;
- sobrevivência residual Weibull condicional à idade atual;
- RBD série/paralelo completo;
- ações: none, minimal_repair, replace;
- execução serial/equivalente das intervenções;
- independência das durações das ações;
- lognormal por MTTR + σT;
- Monte Carlo com seed fixa;
- heurística, Tabu Search e solver exato para instâncias pequenas.

## Hipóteses que ainda limitam o modelo

- a idade futura é projetada sem intervenção antes da parada selecionada;
- a Weibull permanece estável no horizonte analisado;
- a aplicação da regra de Bruss herda a hipótese operacional adotada para as
  oportunidades sucessivas; não se reivindica optimalidade universal fora dessas
  hipóteses;
- RBD limitado a estruturas decomponíveis série/paralelo;
- sem common cause, múltiplas equipes, precedências, custos ou otimização
  multiobjetivo no MVP.
