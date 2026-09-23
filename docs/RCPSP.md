# RCPSP Turnaround Scheduler

## Papel no 3Way

O 3Way continua respondendo três perguntas de decisão:

1. **WHICH** — FUCOM + PROMETHEE;
2. **WHEN** — Bruss X·RUL;
3. **WHAT** — RBD + Selective Maintenance.

O RCPSP entra depois, como camada operacional:

4. **HOW** — como executar o escopo selecionado dentro da janela da parada.

Ele não muda o nome nem a lógica decisória do 3Way.

## Formulação do MVP

Para cada atividade `j`:

- `s_j`: início;
- `d_j`: duração;
- `e_j = s_j + d_j`: fim.

### Precedências

Para cada arco `i -> j`:

```text
s_j >= e_i
```

### Recursos renováveis

Para cada recurso `r` e instante `t`:

```text
sum(q_jr para atividades ativas em t) <= Q_r
```

No CP-SAT isso é modelado por `Cumulative`.

### Recursos exclusivos

Guindastes, bancadas, equipamentos ou frentes indivisíveis usam `NoOverlap`.

### Indisponibilidades

Bloqueios de recurso são representados como intervalos fixos que consomem uma
parte ou toda a capacidade durante a janela configurada.

### Janela

Todas as atividades devem terminar dentro de `T0`.

### Objetivo

O MVP minimiza:

```text
Cmax = max(e_j)
```

ou seja, o makespan da parada.

## Discretização

O domínio público usa horas decimais, mas o CP-SAT opera com inteiros. O motor
usa `time_unit_minutes` (15 min por padrão).

A conversão é conservadora:

- duração: arredondada para cima;
- earliest start: arredondado para cima;
- latest finish e T0: arredondados para baixo;
- bloqueios: início para baixo e fim para cima.

Isso evita produzir um cronograma artificialmente otimista.

## Dados suportados

### Recurso

```json
{
  "id": "MEC",
  "nome": "Mecânicos",
  "capacidade": 4,
  "exclusivo": false
}
```

### Atividade

```json
{
  "id": "P101_ALIGN",
  "nome": "P-101 · Alinhamento",
  "work_package_id": "WP-P101",
  "duracao_h": 2.0,
  "predecessores": ["P101_INSTALL"],
  "recursos": [
    {"recurso_id": "MEC", "quantidade": 2}
  ],
  "earliest_start_h": 0.0,
  "latest_finish_h": 24.0
}
```

### Bloqueio de recurso

```json
{
  "recurso_id": "G150",
  "inicio_h": 4.0,
  "fim_h": 6.0,
  "reducao_capacidade": 1,
  "motivo": "Guindaste reservado para outra frente"
}
```

## Uso em Python

```python
from app.core.rcpsp import RCPSPScheduler
from app.rcpsp_models import InstanciaRCPSP

instancia = InstanciaRCPSP.model_validate(dados)
resultado = RCPSPScheduler(instancia).solve()

print(resultado.status)
print(resultado.makespan_h)
```

## Ponte com Selective Maintenance

`app.core.rcpsp_adapter.rascunho_rcpsp_do_selective()` transforma cada ação
selecionada pelo Selective em uma atividade inicial.

Essa saída é propositalmente um **rascunho**. Um work package real precisa ser
decomposto em WBS: isolamento, desmontagem, inspeção, içamento, reparo, montagem,
teste, liberação etc.

O RCPSP só deve ser tratado como cronograma operacional depois dessa decomposição.

## Diagnóstico de inviabilidade

Quando o CP-SAT prova inviabilidade, o motor tenta identificar condições
necessárias simples:

- caminho crítico por precedências maior que `T0`;
- carga agregada de recurso maior que sua capacidade disponível.

Se nenhuma dessas condições explicar o problema, o resultado informa que a
inviabilidade decorre da combinação de janelas, precedências e competição por
recursos.

## Fora do MVP

- multi-mode RCPSP;
- multi-skill workforce scheduling;
- recursos não renováveis;
- custos e horas extras no objetivo;
- SIMOPS explícito;
- incerteza nas durações dentro do scheduler;
- trabalho emergente;
- geração automática de cuts para devolver inviabilidade ao Selective;
- integração Primavera P6.

Esses itens podem ser adicionados sem substituir o contrato atual.
