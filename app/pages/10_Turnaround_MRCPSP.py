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
    "Planejamento-base do Microsoft Project + modos de execução + atividades opcionais/condicionais "
    "+ rescheduling após achados de inspeção."
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
    return project


project = load_inputs()

st.subheader("Capacidade de recursos")
cols = st.columns(min(4, max(1, len(project.capacities))))
new_caps: dict[str, float] = {}
for i, (resource, capacity) in enumerate(sorted(project.capacities.items())):
    upper = max(2.0, capacity * 2.5)
    step = 1.0 if float(capacity).is_integer() else 0.5
    with cols[i % len(cols)]:
        new_caps[resource] = st.slider(
            resource,
            min_value=0.0,
            max_value=float(upper),
            value=float(capacity),
            step=step,
        )
project = project.model_copy(update={"capacities": new_caps})

empty_state = ExecutionState(current_time=0)
baseline_activation = resolve_activation(project, empty_state)
baseline_tasks = [t for t in project.tasks if t.id in baseline_activation.active_ids]
try:
    baseline = solve_mrcpsp(
        baseline_tasks,
        project.capacities,
        deadline=project.deadline,
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Makespan base", f"{baseline.makespan:.1f} h")
m2.metric("Deadline", "—" if project.deadline is None else f"{project.deadline:.1f} h")
m3.metric("Tarefas base", len(baseline.tasks))
m4.metric("Escopo potencial", len(project.tasks) - len(baseline.tasks))

st.divider()
st.subheader("Estado da parada e achados")
current_time = st.number_input(
    "Hora corrente desde o início da parada",
    min_value=0.0,
    value=min(7.0, float(baseline.makespan)),
    step=0.5,
)

executions: dict[str, TaskExecution] = {}
for item in baseline.tasks:
    if item.finish <= current_time + 1e-9:
        executions[item.task_id] = TaskExecution(
            status="completed", start=item.start, finish=item.finish, mode_name=item.mode_name
        )
    elif item.start < current_time < item.finish:
        executions[item.task_id] = TaskExecution(
            status="in_progress", start=item.start, finish=item.finish, mode_name=item.mode_name
        )

event_catalog: dict[str, set[str]] = {}
for task in project.tasks:
    for condition in task.activation.conditions:
        event_catalog.setdefault(condition.source_task_id, set()).update(condition.events)
for group in project.logical_groups:
    if group.when:
        event_catalog.setdefault(group.when.source_task_id, set()).update(group.when.events)

name_by_id = {t.id: t.name for t in project.tasks}
events: dict[str, list[str]] = {}
if event_catalog:
    st.markdown("**Resultados observados nas atividades gatilho**")
    for source_id, options in sorted(event_catalog.items()):
        execution = executions.get(source_id)
        completed = execution is not None and execution.status == "completed"
        label = f"{name_by_id.get(source_id, source_id)} · {'concluída' if completed else 'ainda não concluída'}"
        selected = st.multiselect(
            label,
            options=sorted(options),
            default=[],
            disabled=not completed,
            key=f"events_{source_id}",
        )
        if selected:
            events[source_id] = selected

group_members = {tid for g in project.logical_groups for tid in g.member_task_ids}
independent_optional = [
    t for t in project.tasks if t.activation.kind == "optional" and t.id not in group_members
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
for group in project.logical_groups:
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

activation = resolve_activation(project, state)
pending_groups = [gid for gid, status in activation.group_states.items() if status == "pending_selection"]
if pending_groups:
    st.warning(
        "Há decisão lógica pendente nos grupos: " + ", ".join(pending_groups) + ". "
        "O cronograma abaixo não inclui os ramos ainda não escolhidos."
    )

try:
    result = reschedule_from_state(project, state)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

st.divider()
st.subheader("Impacto do escopo descoberto")
active_now = result.activation.active_ids
new_scope = active_now - baseline_activation.active_ids
r1, r2, r3, r4 = st.columns(4)
r1.metric(
    "Novo makespan",
    f"{result.schedule.makespan:.1f} h",
    delta=f"{result.schedule.makespan - baseline.makespan:+.1f} h",
)
r2.metric("Atraso", f"{result.schedule.tardiness:.1f} h")
r3.metric("Novas tarefas ativas", len(new_scope))
r4.metric("Custo de modos", f"{result.schedule.total_cost:,.0f}")

activation_df = pd.DataFrame([
    {
        "ID": t.id,
        "Atividade": t.name,
        "Tipo": t.activation.kind,
        "Estado": result.activation.states[t.id].value,
        "Motivo": result.activation.reasons[t.id],
    }
    for t in project.tasks
])
with st.expander("Mapa de ativação", expanded=bool(new_scope)):
    st.dataframe(activation_df, use_container_width=True, hide_index=True)

all_items = result.frozen_tasks + result.schedule.tasks
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
    if project.deadline is not None:
        fig.add_vline(x=project.deadline, line_dash="dot", annotation_text="deadline")
    fig.update_layout(
        title="Cronograma reprogramado",
        xaxis_title="Horas desde o início da parada",
        yaxis_title="",
        barmode="overlay",
        height=max(450, 32 * len(ordered)),
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Solver: {result.schedule.strategy} · combinações de modos={result.schedule.mode_combinations} · "
    f"avaliações SSGS={result.schedule.evaluated_combinations}. "
    "Atividades já iniciadas/concluídas são congeladas; somente o trabalho futuro é reprogramado."
)
