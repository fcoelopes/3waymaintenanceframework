import io

import pytest

from app.core.turnaround import (
    ActivationRule,
    ExecutionMode,
    ExecutionState,
    LogicalGroup,
    Precedence,
    TaskExecution,
    TriggerCondition,
    TurnaroundProject,
    TurnaroundTask,
    apply_scope_config,
    load_project_xml,
    resolve_activation,
    reschedule_from_state,
    solve_mrcpsp,
)


def task(tid, name, duration, resources=None, predecessors=None, activation=None, modes=None):
    return TurnaroundTask(
        id=tid,
        name=name,
        modes=modes or [ExecutionMode(name="base", duration=duration, resources=resources or {})],
        precedences=[Precedence(predecessor_id=p) for p in (predecessors or [])],
        activation=activation or ActivationRule(kind="mandatory"),
    )


def test_mandatory_project_remains_backward_compatible():
    project = TurnaroundProject(
        tasks=[task("A", "A", 2, {"Mec": 1}), task("B", "B", 3, {"Mec": 1}, ["A"])],
        capacities={"Mec": 1},
    )
    activation = resolve_activation(project, ExecutionState())
    assert activation.active_ids == {"A", "B"}
    result = solve_mrcpsp(project.tasks, project.capacities)
    assert result.makespan == pytest.approx(5)


def test_kinder_ovo_can_activate_multiple_findings():
    inspect = task("I", "Inspecionar", 2, {"Insp": 1})
    bearing = task(
        "B",
        "Trocar rolamento",
        4,
        {"Mec": 2},
        ["I"],
        ActivationRule(
            kind="conditional",
            conditions=[TriggerCondition(source_task_id="I", events=["bearing_damage"])],
        ),
    )
    seal = task(
        "S",
        "Trocar selo",
        3,
        {"Mec": 1},
        ["I"],
        ActivationRule(
            kind="conditional",
            conditions=[TriggerCondition(source_task_id="I", events=["seal_damage"])],
        ),
    )
    shaft = task(
        "X",
        "Reparar eixo",
        6,
        {"Mec": 2},
        ["I"],
        ActivationRule(
            kind="conditional",
            conditions=[TriggerCondition(source_task_id="I", events=["shaft_damage"])],
        ),
    )
    project = TurnaroundProject(tasks=[inspect, bearing, seal, shaft], capacities={"Insp": 1, "Mec": 3})
    state = ExecutionState(
        current_time=2,
        events={"I": ["bearing_damage", "seal_damage"]},
        executions={"I": TaskExecution(status="completed", start=0, finish=2, mode_name="base")},
    )
    activation = resolve_activation(project, state)
    assert activation.active_ids == {"I", "B", "S"}
    assert "X" in activation.inactive_ids


def test_xor_group_waits_for_choice_and_enforces_single_path():
    inspection = task("I", "Inspecionar", 1)
    minor = task("M", "Reparo leve", 2, activation=ActivationRule(kind="optional"))
    major = task("G", "Reparo pesado", 5, activation=ActivationRule(kind="optional"))
    group = LogicalGroup(
        id="severity",
        operator="xor",
        member_task_ids=["M", "G"],
        when=TriggerCondition(source_task_id="I", events=["defect_found"]),
    )
    project = TurnaroundProject(tasks=[inspection, minor, major], capacities={}, logical_groups=[group])
    base_state = ExecutionState(
        events={"I": ["defect_found"]},
        executions={"I": TaskExecution(status="completed", start=0, finish=1)},
    )
    unresolved = resolve_activation(project, base_state)
    assert unresolved.group_states["severity"] == "pending_selection"
    assert {"M", "G"}.issubset(unresolved.pending_ids)

    chosen = base_state.model_copy(update={"group_selections": {"severity": ["G"]}})
    resolved = resolve_activation(project, chosen)
    assert "G" in resolved.active_ids
    assert "M" in resolved.inactive_ids

    invalid = base_state.model_copy(update={"group_selections": {"severity": ["M", "G"]}})
    with pytest.raises(ValueError, match="exatamente uma"):
        resolve_activation(project, invalid)


def test_rescheduling_freezes_past_and_activates_discovered_scope():
    inspection = task("I", "Inspecionar", 2, {"Insp": 1})
    repair = TurnaroundTask(
        id="R",
        name="Reparo",
        modes=[
            ExecutionMode(name="normal", duration=6, resources={"Mec": 2}),
            ExecutionMode(name="reforco", duration=3, resources={"Mec": 4}),
        ],
        precedences=[Precedence(predecessor_id="I")],
        activation=ActivationRule(
            kind="conditional",
            conditions=[TriggerCondition(source_task_id="I", events=["crack"])],
        ),
    )
    test = task(
        "T",
        "END pós-reparo",
        2,
        {"Insp": 1},
        ["R"],
        ActivationRule(
            kind="conditional",
            conditions=[TriggerCondition(source_task_id="I", events=["crack"])],
        ),
    )
    project = TurnaroundProject(
        tasks=[inspection, repair, test],
        capacities={"Insp": 1, "Mec": 4},
        deadline=8,
    )
    state = ExecutionState(
        current_time=2,
        events={"I": ["crack"]},
        executions={"I": TaskExecution(status="completed", start=0, finish=2, mode_name="base")},
    )
    result = reschedule_from_state(project, state)
    assert result.frozen_tasks[0].task_id == "I"
    repair_item = next(x for x in result.schedule.tasks if x.task_id == "R")
    assert repair_item.start >= 2
    assert repair_item.mode_name == "reforco"
    assert result.schedule.makespan == pytest.approx(7)


def test_optional_predecessor_is_ignored_when_not_selected():
    opt = task("O", "Opcional", 5, activation=ActivationRule(kind="optional"))
    mandatory = task("M", "Obrigatória", 2, predecessors=["O"])
    project = TurnaroundProject(tasks=[opt, mandatory], capacities={})
    state = ExecutionState()
    activation = resolve_activation(project, state)
    active = [t for t in project.tasks if t.id in activation.active_ids]
    result = solve_mrcpsp(active, project.capacities)
    assert [x.task_id for x in result.tasks] == ["M"]
    assert result.makespan == pytest.approx(2)


def test_project_xml_imports_fs_ss_lag_and_resources():
    xml = b'''<?xml version="1.0" encoding="UTF-8"?>
    <Project xmlns="http://schemas.microsoft.com/project">
      <Tasks>
        <Task><UID>1</UID><ID>1</ID><Name>A</Name><WBS>1</WBS><Summary>0</Summary><Milestone>0</Milestone><Duration>PT2H0M0S</Duration></Task>
        <Task><UID>2</UID><ID>2</ID><Name>B</Name><WBS>2</WBS><Summary>0</Summary><Milestone>0</Milestone><Duration>PT1H0M0S</Duration>
          <PredecessorLink><PredecessorUID>1</PredecessorUID><Type>3</Type><LinkLag>600</LinkLag></PredecessorLink>
        </Task>
      </Tasks>
      <Resources><Resource><UID>1</UID><ID>1</ID><Name>Mec</Name><MaxUnits>4</MaxUnits></Resource></Resources>
      <Assignments><Assignment><TaskUID>1</TaskUID><ResourceUID>1</ResourceUID><Units>2</Units></Assignment></Assignments>
    </Project>'''
    project = load_project_xml(io.BytesIO(xml))
    assert project.capacities["Mec"] == 4
    assert project.tasks[0].modes[0].resources["Mec"] == 2
    assert project.tasks[1].precedences[0].relation == "SS"
    assert project.tasks[1].precedences[0].lag == pytest.approx(1.0)


def test_conditional_chain_becomes_inactive_if_optional_trigger_is_not_selected():
    optional = task("O", "Abrir opcionalmente", 1, activation=ActivationRule(kind="optional"))
    dependent = task(
        "D",
        "Achado dependente",
        2,
        activation=ActivationRule(
            kind="conditional",
            conditions=[TriggerCondition(source_task_id="O", events=["found"])],
        ),
    )
    project = TurnaroundProject(tasks=[optional, dependent], capacities={})
    result = resolve_activation(project, ExecutionState())
    assert result.states["O"].value == "inactive"
    assert result.states["D"].value == "inactive"


def test_resource_check_does_not_sum_disjoint_intervals():
    a = task("A", "A", 2, {"M": 1})
    b = task("B", "B", 2, {"M": 1})
    c = task("C", "C", 6, {"M": 1})
    b.precedences = [Precedence(predecessor_id="A")]
    project = TurnaroundProject(tasks=[a, b, c], capacities={"M": 2})
    result = solve_mrcpsp(project.tasks, project.capacities)
    assert result.makespan == pytest.approx(6)


def test_scope_config_can_turn_xml_task_into_conditional_without_mutating_base():
    base = TurnaroundProject(
        tasks=[task("I", "Inspect", 1), task("R", "Repair", 4, predecessors=["I"])],
        capacities={},
    )
    configured = apply_scope_config(base, {
        "task_overrides": {
            "R": {
                "activation": {
                    "kind": "conditional",
                    "conditions": [{"source_task_id": "I", "events": ["defect"]}],
                    "condition_logic": "all",
                }
            }
        }
    })
    assert base.tasks[1].activation.kind == "mandatory"
    assert configured.tasks[1].activation.kind == "conditional"
