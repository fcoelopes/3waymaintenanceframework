from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import BinaryIO

from .models import ActivationRule, ExecutionMode, Precedence, TurnaroundProject, TurnaroundTask

_NS = {"p": "http://schemas.microsoft.com/project"}
_TYPE_MAP = {0: "FF", 1: "FS", 2: "SF", 3: "SS"}
_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+(?:\.\d+)?)D)?(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?(?:(?P<minutes>\d+(?:\.\d+)?)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?"
)


def _text(node: ET.Element, name: str, default: str | None = None) -> str | None:
    found = node.find(f"p:{name}", _NS)
    return found.text if found is not None and found.text is not None else default


def _hours(value: str | None) -> float:
    if not value:
        return 0.0
    m = _DURATION_RE.fullmatch(value)
    if not m:
        raise ValueError(f"Duração MSPDI não reconhecida: {value}")
    days = float(m.group("days") or 0)
    hours = float(m.group("hours") or 0)
    minutes = float(m.group("minutes") or 0)
    seconds = float(m.group("seconds") or 0)
    return days * 24 + hours + minutes / 60 + seconds / 3600


def load_project_xml(source: str | Path | BinaryIO) -> TurnaroundProject:
    root = ET.parse(source).getroot()

    resources: dict[str, tuple[str, float]] = {}
    for resource in root.findall("p:Resources/p:Resource", _NS):
        uid = _text(resource, "UID")
        name = _text(resource, "Name")
        if uid is None or name in {None, "Unassigned"}:
            continue
        resources[uid] = (name, float(_text(resource, "MaxUnits", "1") or 1))

    assignments: dict[str, dict[str, float]] = {}
    for assignment in root.findall("p:Assignments/p:Assignment", _NS):
        task_uid = _text(assignment, "TaskUID")
        resource_uid = _text(assignment, "ResourceUID")
        if task_uid is None or resource_uid not in resources:
            continue
        units = float(_text(assignment, "Units", "1") or 1)
        name = resources[resource_uid][0]
        assignments.setdefault(task_uid, {})[name] = (
            assignments.setdefault(task_uid, {}).get(name, 0.0) + units
        )

    tasks: list[TurnaroundTask] = []
    for task in root.findall("p:Tasks/p:Task", _NS):
        uid = _text(task, "UID")
        if uid in {None, "0"}:
            continue
        if _text(task, "Summary", "0") == "1" or _text(task, "Milestone", "0") == "1":
            continue
        duration = _hours(_text(task, "Duration"))
        if duration <= 0:
            continue
        precedences: list[Precedence] = []
        for link in task.findall("p:PredecessorLink", _NS):
            pred = _text(link, "PredecessorUID")
            if pred is None:
                continue
            typ = int(_text(link, "Type", "1") or 1)
            lag_tenths_minute = float(_text(link, "LinkLag", "0") or 0)
            precedences.append(Precedence(
                predecessor_id=pred,
                relation=_TYPE_MAP.get(typ, "FS"),
                lag=lag_tenths_minute / 10 / 60,
            ))
        tasks.append(TurnaroundTask(
            id=uid,
            name=_text(task, "Name", uid) or uid,
            wbs=_text(task, "WBS"),
            modes=[ExecutionMode(
                name="base",
                duration=duration,
                resources=assignments.get(uid, {}),
            )],
            precedences=precedences,
            activation=ActivationRule(kind="mandatory"),
        ))

    included = {t.id for t in tasks}
    for task in tasks:
        task.precedences = [p for p in task.precedences if p.predecessor_id in included]

    capacities = {name: cap for name, cap in resources.values()}
    return TurnaroundProject(tasks=tasks, capacities=capacities)
