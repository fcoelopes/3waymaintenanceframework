# Framework de Apoio à Decisão em Manutenção

Aplicação Streamlit para integrar três perguntas que normalmente ficam separadas:

1. **Quais ativos?** — FUCOM + PROMETHEE II
2. **Quando intervir?** — Bruss X·RULUL com sobrevivência Weibull condicional à idade e mantenabilidade
3. **O que fazer?** — RBD + Selective Maintenance com tempos de intervenção estocásticos

## Arquitetura decisória

```text
Critérios + carteira
        ↓
FUCOM + PROMETHEE II
        ↓
ativos priorizados
        ↓
Agenda + idade atual + Weibull + MTTR/σT
        ↓
Bruss X·R
        ↓
ativo × parada
        ↓
RBD + ações + MTTR/σT por ação
        ↓
Selective Maintenance
        ↓
ativo × parada × ação
```

Os motores permanecem desacoplados. O score PROMETHEE **não** é somado à função objetivo do Selective Maintenance: a primeira camada representa preferência/prioridade; a última representa consequência física/sistêmica da combinação de intervenções.

## Camada 1 — FUCOM + PROMETHEE II

O usuário configura critérios, direção, limiares `q/p` e razões FUCOM. O PROMETHEE II produz `phi+`, `phi-`, fluxo líquido e ranking dos ativos.

## Camada 2 — Bruss X·RUL

Para cada ativo priorizado e cada parada `i`:

```text
p_i = M(d_i) * S_RUL(t_i | idade_atual)
```

- `M(d_i)` = probabilidade de concluir a intervenção dentro da duração da parada;
- `S_RUL(t_i | idade_atual)` = probabilidade de sobreviver da idade atual até a oportunidade;
- as odds `p/(1-p)` alimentam a regra de Bruss.

A mantenabilidade pode ser lognormal (MTTR + σT) ou exponencial para comparação com a formulação de referência já prevista no projeto.

## Camada 3 — Selective Maintenance estocástica

A saída do Bruss fornece a parada e sua duração `T0`. Os ativos que apontam para a mesma parada entram como candidatos ao plano operacional. O Selective recebe o RBD completo do sistema: componentes não candidatos ficam fixados em `none`, mas continuam afetando `R_sys`.

Cada combinação `ativo × ação` possui:

- efeito sobre a confiabilidade do componente;
- posição no RBD;
- MTTR da ação;
- σT da ação.

O problema inicial é:

```text
max R_sys(S)
sujeito a P(T_portfólio <= T0) >= alpha
```

A probabilidade de conclusão é estimada por Monte Carlo com amostras comuns por ação, tornando a avaliação reproduzível para uma seed fixa. O modo determinístico permanece disponível para benchmarking.

Ações do MVP:

- nenhuma intervenção;
- reparo mínimo;
- substituição.

Solvers disponíveis:

- heurística construtiva;
- Tabu Search;
- branch-and-bound para instâncias pequenas.

## Integração / fallback

Se o Bruss indicar uma parada para um ativo, mas o Selective Maintenance não selecionar nenhuma ação nesse ativo porque a janela está congestionada, a interface mostra a **próxima oportunidade ranqueada pelo Bruss**.

## RBD

O motor já suporta estruturas série/paralelo e exige que a topologia contenha todos os componentes declarados para o sistema. No MVP a topologia é entrada em JSON. Um canvas visual poderá substituir essa entrada sem alterar o núcleo matemático.

## Executar

```bash
pip install -r requirements.txt
streamlit run app/Inicio.py
```

ou com `uv`:

```bash
uv sync
uv run streamlit run app/Inicio.py
```

## Testes

```bash
pytest -q
```

A suíte cobre FUCOM, PROMETHEE, confiabilidade/mantenabilidade, Bruss e Selective Maintenance. O caso elementar de Lust, Roux & Riane permanece como teste de regressão **no modo determinístico**, reproduzindo `R_sys ≈ 0.874198` para `L=40` e `T0=6 h`.

## Estrutura principal

```text
app/
├── Inicio.py
├── models.py
├── core/
│   ├── fucom.py
│   ├── promethee.py
│   ├── reliability.py
│   ├── bruss_xr.py
│   ├── framework.py
│   ├── rbd.py
│   └── selective_maintenance.py
└── pages/
    ├── 1_Criterios_FUCOM.py
    ├── 2_Ativos.py
    ├── 3_PROMETHEE_II.py
    ├── 5_Paradas_e_Parametros.py
    ├── 6_Bruss_XR.py
    ├── 8_Decisao_Integrada.py
    └── 9_Selective_Maintenance.py
```

## Referências-base do projeto

- Brans & Vincke — PROMETHEE.
- Pamučar, Stević & Sremac — FUCOM.
- Bruss — odds theorem.
- Thomas, Levrat & Iung — seleção temporal de oportunidades por mantenabilidade × confiabilidade.
- Lust, Roux & Riane — selective maintenance com maximização de confiabilidade sob janela limitada.


## Formulação matemática

A formulação, os contratos entre camadas e as hipóteses do MVP estão detalhados em
`docs/MATHEMATICAL_MODEL.md`.
