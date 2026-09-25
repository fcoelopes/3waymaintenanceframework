from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.core.turnaround import (
    ExecutionState,
    TaskExecution,
    apply_scope_config,
    load_project_xml,
    resolve_activation,
    reschedule_from_state,
    solve_mrcpsp,
)

ROOT = Path(__file__).resolve().parents[2]
DEMO_XML = ROOT / "data" / "turnaround_conditional_model.xml"
DEMO_SCOPE = ROOT / "data" / "turnaround_conditional_scope.json"

st.set_page_config(page_title="Turnaround MRCPSP", page_icon="🛠️", layout="wide")
st.title("Turnaround · MRCPSP + escopo condicional")
st.caption(
    "Planejamento-base do Microsoft Project + scope discovery + cenários explícitos de recursos "
    "+ seleção de modos + rescheduling."
)


def load_inputs():
    c1, c2 = st.columns(2)
    with c1:
        xml_upload = st.file_uploader("Microsoft Project XML", type=["xml"])
    with c2:
        scope_upload = st.file_uploader("Escopo potencial / regras (JSON)", type=["json"])

    use_demo = st.checkbox("Usar cenário demonstrativo 'Kinder Ovo'", value=xml_upload is None)
    if xml_upload is not None:
        project = load_project_xml(io.BytesIO(xml_upload.getvalue()))
    elif use_demo:
        project = load_project_xml(DEMO_XML)
    else:
        st.info("Envie um XML do Project ou habilite o cenário demonstrativo.")
        st.stop()

    if scope_upload is not None:
        project = apply_scope_config(project, io.BytesIO(scope_upload.getvalue()))
    elif use_demo:
        project = apply_scope_config(project, DEMO_SCOPE)
    return project, use_demo


base_project, use_demo = load_inputs()
base_capacities = dict(base_project.capacities)

empty_state = ExecutionState(current_time=0)
baseline_activation = resolve_activation(base_project, empty_state)
baseline_tasks = [t for t in base_project.tasks if t.id in baseline_activation.active_ids]
try:
    planned_baseline = solve_mrcpsp(
        baseline_tasks,
        base_project.capacities,
        deadline=base_project.deadline,
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

st.subheader("1. Planejamento original")
b1, b2, b3, b4 = st.columns(4)
b1.metric("Makespan planejado", f"{planned_baseline.makespan:.1f} h")
b2.metric("Deadline", "—" if base_project.deadline is None else f"{base_project.deadline:.1f} h")
b3.metric("Tarefas inicialmente ativas", len(planned_baseline.tasks))
b4.metric("Escopo potencial", len(base_project.tasks) - len(planned_baseline.tasks))

with st.expander("Capacidades originais importadas", expanded=False):
    st.dataframe(
        pd.DataFrame(
            [{"Recurso": r, "Capacidade base": c} for r, c in sorted(base_capacities.items())]
        ),
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.subheader("2. Estado da parada e scope discovery")
current_time = st.number_input(
    "Hora corrente desde o início da parada",
    min_value=0.0,
    value=min(7.0, float(planned_baseline.makespan)),
    step=0.5,
)

executions: dict[str, TaskExecution] = {}
for item in planned_baseline.tasks:
    if item.finish <= current_time + 1e-9:
        executions[item.task_id] = TaskExecution(
            status="completed", start=item.start, finish=item.finish, mode_name=item.mode_name
        )
    elif item.start < current_time < item.finish:
        executions[item.task_id] = TaskExecution(
            status="in_progress", start=item.start, finish=item.finish, mode_name=item.mode_name
        )

event_catalog: dict[str, set[str]] = {}
for task in base_project.tasks:
    for condition in task.activation.conditions:
        event_catalog.setdefault(condition.source_task_id, set()).update(condition.events)
for group in base_project.logical_groups:
    if group.when:
        event_catalog.setdefault(group.when.source_task_id, set()).update(group.when.events)

name_by_id = {t.id: t.name for t in base_project.tasks}
events: dict[str, list[str]] = {}
if event_catalog:
    st.markdown("**Resultados observados nas atividades gatilho**")
    for source_id, options in sorted(event_catalog.items()):
        execution = executions.get(source_id)
        completed = execution is not None and execution.status == "completed"
        label = (
            f"{name_by_id.get(source_id, source_id)} · "
            f"{'concluída' if completed else 'ainda não concluída'}"
        )
        default_events = []
        if use_demo and completed and source_id == "4":
            default_events = ["bearing_damage"]
        selected = st.multiselect(
            label,
            options=sorted(options),
            default=default_events,
            disabled=not completed,
            key=f"events_{source_id}",
        )
        if selected:
            events[source_id] = selected

group_members = {tid for g in base_project.logical_groups for tid in g.member_task_ids}
independent_optional = [
    t for t in base_project.tasks if t.activation.kind == "optional" and t.id not in group_members
]
selected_optional_ids: list[str] = []
if independent_optional:
    labels = {t.id: f"{t.id} · {t.name}" for t in independent_optional}
    selected_optional_ids = st.multiselect(
        "Atividades opcionais selecionadas",
        options=list(labels),
        format_func=lambda tid: labels[tid],
    )

group_selections: dict[str, list[str]] = {}
for group in base_project.logical_groups:
    labels = {tid: f"{tid} · {name_by_id.get(tid, tid)}" for tid in group.member_task_ids}
    if group.operator == "xor":
        chosen = st.selectbox(
            f"Grupo XOR · {group.id}",
            options=[None] + group.member_task_ids,
            format_func=lambda tid: "— selecionar —" if tid is None else labels[tid],
        )
        if chosen:
            group_selections[group.id] = [chosen]
    elif group.operator == "or":
        chosen = st.multiselect(
            f"Grupo OR · {group.id}",
            options=group.member_task_ids,
            format_func=lambda tid: labels[tid],
        )
        if chosen:
            group_selections[group.id] = chosen

state = ExecutionState(
    current_time=current_time,
    events=events,
    selected_optional_ids=selected_optional_ids,
    group_selections=group_selections,
    executions=executions,
)

activation = resolve_activation(base_project, state)
pending_groups = [gid for gid, status in activation.group_states.items() if status == "pending_selection"]
if pending_groups:
    st.warning(
        "Há decisão lógica pendente nos grupos: " + ", ".join(pending_groups) + ". "
        "Os ramos ainda não escolhidos ficam fora das comparações."
    )

try:
    discovered_base = reschedule_from_state(base_project, state)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

active_now = discovered_base.activation.active_ids
new_scope = active_now - baseline_activation.active_ids
d1, d2, d3, d4 = st.columns(4)
d1.metric(
    "Makespan após discovery",
    f"{discovered_base.schedule.makespan:.1f} h",
    delta=f"{discovered_base.schedule.makespan - planned_baseline.makespan:+.1f} h vs plano",
)
d2.metric("Novas tarefas ativas", len(new_scope))
d3.metric("Atraso com recursos originais", f"{discovered_base.schedule.tardiness:.1f} h")
d4.metric("Custo dos modos", f"{discovered_base.schedule.total_cost:,.0f}")

st.divider()
st.subheader("3. Cenário MRCPSP de recursos")
st.markdown(
    "Mude as capacidades abaixo. O cenário é comparado **contra o mesmo escopo descoberto**, "
    "mantendo os achados e o passado congelado. Assim aparece apenas o efeito dos recursos."
)

scenario_name = st.text_input("Nome do cenário", value="Cenário de recursos A")
if use_demo:
    st.info(
        "Teste guiado: com o achado bearing_damage ativo, mova Mecânica de 4 para 5. "
        "O modo de 'Trocar rolamentos P-101' deve mudar de normal (5 h) para reforço (3 h), "
        "e o makespan do escopo descoberto deve cair de 17 h para 15 h."
    )
cols = st.columns(min(4, max(1, len(base_capacities))))
scenario_capacities: dict[str, float] = {}
for i, (resource, capacity) in enumerate(sorted(base_capacities.items())):
    upper = max(2.0, capacity * 2.5)
    step = 1.0 if float(capacity).is_integer() else 0.5
    demo_default = float(capacity)
    with cols[i % len(cols)]:
        scenario_capacities[resource] = st.slider(
            resource,
            min_value=0.0,
            max_value=float(upper),
            value=demo_default,
            step=step,
            key=f"scenario_capacity_{resource}",
            help=f"Base importada: {capacity:g}",
        )

resource_rows = []
for resource in sorted(base_capacities):
    base = float(base_capacities[resource])
    scenario = float(scenario_capacities[resource])
    resource_rows.append(
        {
            "Recurso": resource,
            "Base": base,
            "Cenário": scenario,
            "Δ": scenario - base,
            "Alterado": "sim" if abs(scenario - base) > 1e-9 else "não",
        }
    )
st.dataframe(pd.DataFrame(resource_rows), use_container_width=True, hide_index=True)

scenario_project = base_project.model_copy(update={"capacities": scenario_capacities})
try:
    scenario_result = reschedule_from_state(scenario_project, state)
except ValueError as exc:
    st.error(f"Cenário inviável: {exc}")
    st.stop()

s1, s2, s3, s4 = st.columns(4)
s1.metric(
    "Makespan do cenário",
    f"{scenario_result.schedule.makespan:.1f} h",
    delta=f"{scenario_result.schedule.makespan - discovered_base.schedule.makespan:+.1f} h vs recursos base",
)
s2.metric(
    "Horas recuperadas",
    f"{max(0.0, discovered_base.schedule.makespan - scenario_result.schedule.makespan):.1f} h",
)
s3.metric(
    "Atraso",
    f"{scenario_result.schedule.tardiness:.1f} h",
    delta=f"{scenario_result.schedule.tardiness - discovered_base.schedule.tardiness:+.1f} h",
)
s4.metric(
    "Custo dos modos",
    f"{scenario_result.schedule.total_cost:,.0f}",
    delta=f"{scenario_result.schedule.total_cost - discovered_base.schedule.total_cost:+,.0f}",
)

base_future = {x.task_id: x for x in discovered_base.schedule.tasks}
scenario_future = {x.task_id: x for x in scenario_result.schedule.tasks}
comparison_rows = []
for tid in sorted(set(base_future) | set(scenario_future)):
    before = base_future.get(tid)
    after = scenario_future.get(tid)
    if before is None or after is None:
        continue
    comparison_rows.append(
        {
            "ID": tid,
            "Atividade": after.task_name,
            "Modo · recursos base": before.mode_name,
            "Modo · cenário": after.mode_name,
            "Mudou modo?": "SIM" if before.mode_name != after.mode_name else "não",
            "Duração base": before.duration,
            "Duração cenário": after.duration,
            "Início base": before.start,
            "Início cenário": after.start,
            "Fim base": before.finish,
            "Fim cenário": after.finish,
            "Δ fim": after.finish - before.finish,
        }
    )
comparison_df = pd.DataFrame(comparison_rows)
changed_modes = (
    comparison_df[comparison_df["Mudou modo?"] == "SIM"]
    if not comparison_df.empty
    else comparison_df
)

if not changed_modes.empty:
    st.success(f"O MRCPSP trocou o modo de {len(changed_modes)} atividade(s) neste cenário.")
    st.dataframe(changed_modes, use_container_width=True, hide_index=True)
else:
    st.info(
        "Nenhuma atividade trocou de modo neste cenário. Ainda assim, o makespan pode mudar por "
        "permitir mais paralelismo. Veja a tabela completa abaixo."
    )

with st.expander("Comparação completa das atividades futuras", expanded=True):
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

mode_rows = []
for task in base_project.tasks:
    if task.id not in active_now or len(task.modes) <= 1:
        continue
    for mode in task.modes:
        feasible_base = all(
            req <= base_capacities.get(resource, 0.0) + 1e-9
            for resource, req in mode.resources.items()
        )
        feasible_scenario = all(
            req <= scenario_capacities.get(resource, 0.0) + 1e-9
            for resource, req in mode.resources.items()
        )
        mode_rows.append(
            {
                "ID": task.id,
                "Atividade": task.name,
                "Modo": mode.name,
                "Duração": mode.duration,
                "Demandas": ", ".join(f"{k}:{v:g}" for k, v in mode.resources.items()),
                "Factível na base?": "sim" if feasible_base else "NÃO",
                "Factível no cenário?": "sim" if feasible_scenario else "NÃO",
                "Novo modo liberado?": "SIM" if (not feasible_base and feasible_scenario) else "não",
            }
        )
if mode_rows:
    with st.expander("Por que o solver pode mudar de modo?", expanded=True):
        st.dataframe(pd.DataFrame(mode_rows), use_container_width=True, hide_index=True)

st.session_state.setdefault("turnaround_scenarios", [])
save_col, clear_col = st.columns([1, 1])
with save_col:
    if st.button("Salvar cenário na comparação", type="primary"):
        st.session_state.turnaround_scenarios.append(
            {
                "Cenário": scenario_name,
                "Makespan": scenario_result.schedule.makespan,
                "Atraso": scenario_result.schedule.tardiness,
                "Custo modos": scenario_result.schedule.total_cost,
                "Horas recuperadas": discovered_base.schedule.makespan
                - scenario_result.schedule.makespan,
                "Recursos": "; ".join(
                    f"{r}={scenario_capacities[r]:g}" for r in sorted(scenario_capacities)
                ),
                "Modos alterados": int(
                    sum(
                        1
                        for row in comparison_rows
                        if row["Mudou modo?"] == "SIM"
                    )
                ),
            }
        )
        st.success(f"{scenario_name} salvo para comparação.")
with clear_col:
    if st.button("Limpar cenários salvos"):
        st.session_state.turnaround_scenarios = []

if st.session_state.turnaround_scenarios:
    st.markdown("**Cenários salvos nesta sessão**")
    st.dataframe(
        pd.DataFrame(st.session_state.turnaround_scenarios),
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.subheader("4. Cronograma do cenário selecionado")
activation_df = pd.DataFrame([
    {
        "ID": t.id,
        "Atividade": t.name,
        "Tipo": t.activation.kind,
        "Estado": scenario_result.activation.states[t.id].value,
        "Motivo": scenario_result.activation.reasons[t.id],
    }
    for t in base_project.tasks
])
with st.expander("Mapa de ativação", expanded=False):
    st.dataframe(activation_df, use_container_width=True, hide_index=True)

all_items = scenario_result.frozen_tasks + scenario_result.schedule.tasks
schedule_df = pd.DataFrame([
    {
        "ID": x.task_id,
        "Atividade": x.task_name,
        "Modo": x.mode_name,
        "Início (h)": x.start,
        "Fim (h)": x.finish,
        "Duração (h)": x.duration,
        "Congelada": x.fixed,
        "Recursos": ", ".join(f"{k}:{v:g}" for k, v in x.resources.items()),
    }
    for x in sorted(all_items, key=lambda item: (item.start, item.finish))
])
st.dataframe(schedule_df, use_container_width=True, hide_index=True)

if all_items:
    fig = go.Figure()
    ordered = sorted(all_items, key=lambda x: (x.start, x.finish), reverse=True)
    fig.add_trace(go.Bar(
        y=[f"{x.task_id} · {x.task_name}" for x in ordered],
        x=[x.duration for x in ordered],
        base=[x.start for x in ordered],
        orientation="h",
        text=[x.mode_name + (" · congelada" if x.fixed else "") for x in ordered],
        hovertemplate="%{y}<br>Início=%{base:.1f}h<br>Duração=%{x:.1f}h<extra></extra>",
    ))
    fig.add_vline(x=current_time, line_dash="dash", annotation_text="agora")
    if scenario_project.deadline is not None:
        fig.add_vline(x=scenario_project.deadline, line_dash="dot", annotation_text="deadline")
    fig.update_layout(
        title=f"Cronograma reprogramado · {scenario_name}",
        xaxis_title="Horas desde o início da parada",
        yaxis_title="",
        barmode="overlay",
        height=max(450, 32 * len(ordered)),
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Solver: {scenario_result.schedule.strategy} · "
    f"combinações de modos={scenario_result.schedule.mode_combinations} · "
    f"avaliações SSGS={scenario_result.schedule.evaluated_combinations}. "
    "A comparação de recursos usa exatamente o mesmo escopo descoberto e o mesmo estado da parada."
)
