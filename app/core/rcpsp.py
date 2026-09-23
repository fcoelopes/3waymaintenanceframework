"""Motor RCPSP determinístico baseado em OR-Tools CP-SAT.

Escopo do MVP:
- precedências;
- recursos renováveis com capacidade (Cumulative);
- recursos exclusivos (NoOverlap);
- indisponibilidades/reduções de capacidade;
- earliest start / latest finish;
- janela total da parada;
- minimização de makespan.

O domínio recebe horas decimais e discretiza de forma conservadora para ticks.
"""
from __future__ import annotations

from collections import defaultdict, deque
from math import ceil, floor

from ortools.sat.python import cp_model

from app.rcpsp_models import (
    AtividadeAgendadaRCPSP,
    AtividadeRCPSP,
    InstanciaRCPSP,
    ResultadoRCPSP,
    UtilizacaoRecursoRCPSP,
)


class RCPSPScheduler:
    def __init__(self, instancia: InstanciaRCPSP) -> None:
        self.instancia = instancia
        self._minutes = instancia.time_unit_minutes
        self._atividades = {a.id: a for a in instancia.atividades}
        self._recursos = {r.id: r for r in instancia.recursos}
        self._validar_dag()

    # ------------------------------------------------------------------
    # Discretização conservadora
    # ------------------------------------------------------------------
    def _dur_ticks(self, horas: float) -> int:
        return max(1, int(ceil((horas * 60.0) / self._minutes - 1e-12)))

    def _lower_ticks(self, horas: float) -> int:
        return max(0, int(ceil((horas * 60.0) / self._minutes - 1e-12)))

    def _upper_ticks(self, horas: float) -> int:
        return max(0, int(floor((horas * 60.0) / self._minutes + 1e-12)))

    def _block_start_ticks(self, horas: float) -> int:
        return max(0, int(floor((horas * 60.0) / self._minutes + 1e-12)))

    def _block_end_ticks(self, horas: float) -> int:
        return max(0, int(ceil((horas * 60.0) / self._minutes - 1e-12)))

    def _to_hours(self, ticks: int | float) -> float:
        return float(ticks) * self._minutes / 60.0

    # ------------------------------------------------------------------
    # Validações estruturais
    # ------------------------------------------------------------------
    def _validar_dag(self) -> None:
        indegree = {aid: 0 for aid in self._atividades}
        succ: dict[str, list[str]] = defaultdict(list)
        for a in self.instancia.atividades:
            for pred in a.predecessores:
                succ[pred].append(a.id)
                indegree[a.id] += 1

        q = deque([aid for aid, degree in indegree.items() if degree == 0])
        visitados = 0
        while q:
            atual = q.popleft()
            visitados += 1
            for nxt in succ[atual]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    q.append(nxt)

        if visitados != len(self._atividades):
            raise ValueError("grafo de precedências contém ciclo")

    def _critical_path_lower_bound_ticks(self) -> int:
        indegree = {aid: 0 for aid in self._atividades}
        succ: dict[str, list[str]] = defaultdict(list)
        for a in self.instancia.atividades:
            for pred in a.predecessores:
                succ[pred].append(a.id)
                indegree[a.id] += 1

        q = deque([aid for aid, degree in indegree.items() if degree == 0])
        earliest_finish: dict[str, int] = {}
        while q:
            aid = q.popleft()
            a = self._atividades[aid]
            start = self._lower_ticks(a.earliest_start_h)
            if a.predecessores:
                start = max(start, max(earliest_finish[p] for p in a.predecessores))
            earliest_finish[aid] = start + self._dur_ticks(a.duracao_h)
            for nxt in succ[aid]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    q.append(nxt)
        return max(earliest_finish.values(), default=0)

    # ------------------------------------------------------------------
    # Modelo CP-SAT
    # ------------------------------------------------------------------
    def solve(self) -> ResultadoRCPSP:
        model = cp_model.CpModel()
        horizon = self._upper_ticks(self.instancia.janela_h)
        if horizon <= 0:
            raise ValueError("janela_h é menor que uma unidade de discretização")

        starts = {}
        ends = {}
        intervals = {}
        durations: dict[str, int] = {}

        for a in self.instancia.atividades:
            dur = self._dur_ticks(a.duracao_h)
            earliest = self._lower_ticks(a.earliest_start_h)
            latest_finish_h = (
                self.instancia.janela_h
                if a.latest_finish_h is None
                else a.latest_finish_h
            )
            latest_finish = min(horizon, self._upper_ticks(latest_finish_h))
            latest_start = latest_finish - dur
            if latest_start < earliest:
                return self._resultado_inviavel(
                    [
                        f"{a.id}: duração discretizada não cabe em sua janela "
                        "earliest/latest."
                    ]
                )

            start = model.new_int_var(earliest, latest_start, f"start_{a.id}")
            end = model.new_int_var(earliest + dur, latest_finish, f"end_{a.id}")
            interval = model.new_interval_var(start, dur, end, f"interval_{a.id}")
            starts[a.id] = start
            ends[a.id] = end
            intervals[a.id] = interval
            durations[a.id] = dur

        # Precedências.
        for a in self.instancia.atividades:
            for pred in a.predecessores:
                model.add(starts[a.id] >= ends[pred])

        # Recursos: atividades + bloqueios fixos.
        for rid, recurso in self._recursos.items():
            r_intervals = []
            demands = []

            for a in self.instancia.atividades:
                req = next((x for x in a.recursos if x.recurso_id == rid), None)
                if req is None:
                    continue
                r_intervals.append(intervals[a.id])
                demands.append(req.quantidade)

            for idx, b in enumerate(
                x for x in self.instancia.bloqueios_recursos if x.recurso_id == rid
            ):
                b_start = self._block_start_ticks(b.inicio_h)
                b_end = self._block_end_ticks(b.fim_h)
                b_size = b_end - b_start
                if b_size <= 0:
                    continue
                fixed = model.new_fixed_size_interval_var(
                    b_start,
                    b_size,
                    f"block_{rid}_{idx}",
                )
                r_intervals.append(fixed)
                demands.append(b.reducao_capacidade)

            if not r_intervals:
                continue

            if recurso.exclusivo:
                model.add_no_overlap(r_intervals)
            else:
                model.add_cumulative(r_intervals, demands, recurso.capacidade)

        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, list(ends.values()))
        model.add(makespan <= horizon)
        model.minimize(makespan)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.instancia.max_solve_seconds
        solver.parameters.num_search_workers = self.instancia.num_workers
        solver.parameters.random_seed = self.instancia.random_seed

        status = solver.solve(model)

        if status == cp_model.INFEASIBLE:
            return self._resultado_inviavel(self._diagnosticar_inviabilidade())
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return ResultadoRCPSP(
                status="unknown",
                janela_h=self.instancia.janela_h,
                time_unit_minutes=self.instancia.time_unit_minutes,
                diagnosticos=[
                    "CP-SAT não encontrou solução nem prova de inviabilidade "
                    "dentro do limite configurado."
                ],
                wall_time_s=float(solver.wall_time),
            )

        scheduled = []
        for a in self.instancia.atividades:
            s = int(solver.value(starts[a.id]))
            e = int(solver.value(ends[a.id]))
            scheduled.append(
                AtividadeAgendadaRCPSP(
                    id=a.id,
                    nome=a.nome,
                    work_package_id=a.work_package_id,
                    inicio_h=self._to_hours(s),
                    fim_h=self._to_hours(e),
                    duracao_h=self._to_hours(durations[a.id]),
                    ativo_id=a.ativo_id,
                    acao_origem=a.acao_origem,
                    recursos=a.recursos,
                )
            )
        scheduled.sort(key=lambda a: (a.inicio_h, a.fim_h, a.id))

        result_status = "optimal" if status == cp_model.OPTIMAL else "feasible"
        return ResultadoRCPSP(
            status=result_status,
            janela_h=self.instancia.janela_h,
            time_unit_minutes=self.instancia.time_unit_minutes,
            makespan_h=self._to_hours(solver.value(makespan)),
            atividades=scheduled,
            utilizacao_recursos=self._calcular_utilizacao(scheduled),
            diagnosticos=[],
            wall_time_s=float(solver.wall_time),
            objective_value_ticks=float(solver.objective_value),
            best_bound_ticks=float(solver.best_objective_bound),
        )

    # ------------------------------------------------------------------
    # Diagnóstico
    # ------------------------------------------------------------------
    def _diagnosticar_inviabilidade(self) -> list[str]:
        diagnostics: list[str] = []
        horizon = self._upper_ticks(self.instancia.janela_h)

        cp = self._critical_path_lower_bound_ticks()
        if cp > horizon:
            diagnostics.append(
                "Caminho crítico mínimo por precedências excede a janela: "
                f"{self._to_hours(cp):.2f} h > {self.instancia.janela_h:.2f} h."
            )

        for rid, recurso in self._recursos.items():
            carga = 0
            for a in self.instancia.atividades:
                req = next((x for x in a.recursos if x.recurso_id == rid), None)
                if req is not None:
                    carga += self._dur_ticks(a.duracao_h) * req.quantidade

            bloqueada = 0
            for b in self.instancia.bloqueios_recursos:
                if b.recurso_id != rid:
                    continue
                b_start = self._block_start_ticks(b.inicio_h)
                b_end = self._block_end_ticks(b.fim_h)
                bloqueada += max(0, b_end - b_start) * b.reducao_capacidade

            capacidade_total = horizon * recurso.capacidade
            if carga + bloqueada > capacidade_total:
                diagnostics.append(
                    f"Capacidade agregada insuficiente em {rid}: "
                    f"carga+indisponibilidade={self._to_hours(carga + bloqueada):.2f} "
                    f"unid·h-equivalentes para capacidade total "
                    f"{self._to_hours(capacidade_total):.2f}."
                )

        if not diagnostics:
            diagnostics.append(
                "CP-SAT provou inviabilidade, mas os limites simples de caminho "
                "crítico e carga agregada não isolam o gargalo. Verifique janelas "
                "individuais, precedências combinadas e competição simultânea por recursos."
            )
        return diagnostics

    def _resultado_inviavel(self, diagnostics: list[str]) -> ResultadoRCPSP:
        return ResultadoRCPSP(
            status="infeasible",
            janela_h=self.instancia.janela_h,
            time_unit_minutes=self.instancia.time_unit_minutes,
            diagnosticos=diagnostics,
            wall_time_s=0.0,
        )

    # ------------------------------------------------------------------
    # Métricas de recurso
    # ------------------------------------------------------------------
    def _calcular_utilizacao(
        self, scheduled: list[AtividadeAgendadaRCPSP]
    ) -> list[UtilizacaoRecursoRCPSP]:
        out = []
        tick = self._minutes / 60.0
        horizon_ticks = self._upper_ticks(self.instancia.janela_h)

        by_id = {a.id: a for a in scheduled}
        for rid, recurso in self._recursos.items():
            carga_h = 0.0
            usage = [0] * max(1, horizon_ticks)

            for original in self.instancia.atividades:
                req = next((x for x in original.recursos if x.recurso_id == rid), None)
                if req is None:
                    continue
                sched = by_id[original.id]
                carga_h += sched.duracao_h * req.quantidade
                s = self._lower_ticks(sched.inicio_h)
                e = self._lower_ticks(sched.fim_h)
                for t in range(max(0, s), min(horizon_ticks, e)):
                    usage[t] += req.quantidade

            capacidade_h = recurso.capacidade * self.instancia.janela_h
            out.append(
                UtilizacaoRecursoRCPSP(
                    recurso_id=rid,
                    nome=recurso.nome,
                    capacidade=recurso.capacidade,
                    carga_h_equivalente=carga_h,
                    capacidade_h_total=capacidade_h,
                    utilizacao_media=(carga_h / capacidade_h if capacidade_h else 0.0),
                    pico_utilizado=max(usage, default=0),
                )
            )
        return out
