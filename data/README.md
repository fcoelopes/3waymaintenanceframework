# Data folder

## Conteúdo esperado

### `exemplo_carteira.xlsx`
Template da carteira para PROMETHEE/FUCOM (camada estratégica).

Estrutura (aba `Ativos`):

| ID    | Nome                  | Criticidade | Custo de falha | Impacto | Recursos | Complexidade |
|-------|----------------------|-------------|----------------|---------|----------|--------------|
| A001  | Bomba BC-101         | 9           | 250000         | 9       | 4        | 7            |
| ...   | ...                  | ...         | ...            | ...     | ...      | ...          |

Pode ser reaproveitado o template do workbook `framework_gestao_ativos.xlsx`
gerado anteriormente, exportando apenas a aba 'Alternativas'.

### `exemplo_thomas2008.json`
Caso de validação do artigo Thomas, Levrat & Iung (2008) para a camada tática.

Estrutura:
```json
{
  "horizonte_T": 800,
  "paradas": [
    {"id": 1,  "inicio": 30,  "duracao": 3.8},
    {"id": 2,  "inicio": 60,  "duracao": 3.0},
    ...
    {"id": 20, "inicio": 600, "duracao": 3.0}
  ],
  "parametros_referencia": {
    "weibull_beta": 1.5,
    "weibull_eta": 600,
    "weibull_gamma": 0,
    "mttr": 5
  },
  "threshold_referencia": 0.35
}
```

As durações exatas de cada parada estão na **Tabela 1 do artigo** (coluna 'duration').
Os instantes são regulares de 30 em 30h conforme afirmado em §3.1 do artigo.


### `turnaround_project_model.xml`
Modelo de cronograma em **Microsoft Project XML (MSPDI)** para testes do motor de turnaround/RCPSP/MRCPSP.

O exemplo inclui:
- EDT/WBS e tarefas-resumo;
- atividades executáveis e milestone final;
- relações Finish-to-Start (FS) e Start-to-Start (SS) com lag;
- calendário de turnaround 24x7;
- pools de recursos: Operação, Mecânica, Elétrica, Instrumentação, Inspeção, Guindaste e Andaime;
- assignments com unidades de recurso;
- duas frentes concorrentes que disputam recursos.

Use o arquivo como referência para exportar cronogramas reais do Microsoft Project. Os modos alternativos do MRCPSP continuam sendo definidos na aplicação; o XML representa o planejamento-base.


### \`turnaround_conditional_model.xml\` + \`turnaround_conditional_scope.json\`

Cenário demonstrativo de **scope discovery** em uma parada de bomba P-101.

O XML contém o escopo potencial completo. O JSON define quais tarefas são condicionais e quais eventos da inspeção as disparam:

- \`bearing_damage\` → troca de rolamentos;
- \`seal_damage\` → troca de selo;
- \`shaft_damage\` → reparo de eixo + END pós-reparo;
- \`impeller_damage\` → decisão XOR entre recuperar ou substituir o impelidor.

O JSON também demonstra múltiplos modos MRCPSP para reparos, permitindo alterar as capacidades na interface e observar mudança de modo e makespan.

As tarefas potenciais podem permanecer no Project como parte da rede de planejamento; quando o sidecar as marca como inativas, suas relações de precedência não restringem o cronograma executável.
