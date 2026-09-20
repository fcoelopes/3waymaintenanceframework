# Integração das três camadas

## Contratos

### 1. PROMETHEE/FUCOM — QUais ativos

Saída: `ResultadoPROMETHEE` com `rank` e `phi_net` por ativo.

O ranking é usado para selecionar o top-N que segue para a camada temporal. O fluxo PROMETHEE não é somado à função objetivo operacional para evitar dupla contagem de criticidade/preferência.

### 2. Bruss X·R — QUando

Entrada: top-N + agenda de paradas + Weibull + MTTR/σT.

Para cada ativo/parada:

`p_i = M(d_i) * R(a_i)`

Saída: `ResultadoBrussAtivo`, contendo oportunidades ranqueadas e `parada_otima_id`.

A duração da parada escolhida fornece diretamente `T0` ao Selective Maintenance.

### 3. RBD + Selective Maintenance — O quê

Entrada: candidatos que apontaram para a mesma parada + RBD + parâmetros das ações.

Cada ação usa MTTR + σT. A viabilidade estocástica é:

`P(T_portfolio <= T0) >= alpha`

Objetivo inicial: maximizar a confiabilidade da próxima missão `R_sys`.

## Fallback temporal

Se um ativo candidato não recebe ação (`none`) na parada porque o portfólio ótimo usa a janela em outras intervenções, `framework.proxima_oportunidade()` aponta a próxima oportunidade ranqueada no resultado Bruss.

## Escopo do MVP

- RBD série/paralelo;
- ações: none, minimal_repair, replace;
- execução serial/equivalente das intervenções;
- independência das durações das ações;
- lognormal por MTTR + σT;
- Monte Carlo com seed fixa;
- heurística, Tabu Search e solver exato para instâncias pequenas.

Fora do MVP: múltiplas equipes/recursos, precedências, common cause, k-out-of-n, custos e otimização multiobjetivo.
