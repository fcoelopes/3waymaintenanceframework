"""Selective Maintenance estocástica sobre RBD série/paralelo.

A formulação clássica usa tempos determinísticos. Nesta evolução, cada ação tem
uma distribuição lognormal definida por MTTR + sigma_T e a viabilidade é uma
restrição de chance:

    P(T_portfolio <= T0) >= alpha

O modo determinístico é mantido para benchmarking e reprodução do artigo-base.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp

import numpy as np

from app.core.rbd import confiabilidade_rbd, validar_referencias
from app.core.reliability import amostrar_lognormal_por_media_desvio
from app.models import (
    ComponenteSelective,
    ItemPlanoSelective,
    NoRBD,
    ResultadoSelective,
    TipoAcaoSelective,
    TipoTempoSelective,
)

ACTIONS: tuple[TipoAcaoSelective, ...] = ("none", "minimal_repair", "replace")


@dataclass(slots=True)
class _Candidate:
    actions: dict[str, TipoAcaoSelective]
    reliability: float
    expected_time: float
    completion_probability: float
    p50: float
    p90: float
    p95: float


class SelectiveMaintenanceProblem:
    def __init__(
        self,
        componentes: list[ComponenteSelective],
        topologia: NoRBD,
        duracao_missao: float,
        janela_manutencao: float,
        *,
        alpha_conclusao: float = 0.90,
        modo_tempo: TipoTempoSelective = "stochastic",
        n_simulacoes: int = 5000,
        seed: int = 42,
        ativos_candidatos: set[str] | None = None,
    ) -> None:
        if duracao_missao <= 0 or janela_manutencao <= 0:
            raise ValueError("duracao_missao e janela_manutencao devem ser > 0")
        if not 0 <= alpha_conclusao <= 1:
            raise ValueError("alpha_conclusao deve estar em [0,1]")
        if n_simulacoes < 100:
            raise ValueError("n_simulacoes deve ser >= 100")
        if not componentes:
            raise ValueError("É necessário informar pelo menos um componente")

        self.componentes = {c.ativo_id: c for c in componentes}
        if len(self.componentes) != len(componentes):
            raise ValueError("ativo_id deve ser único")
        # A camada operacional deve avaliar a consequência no sistema inteiro.
        # Componentes fora da lista de candidatos permanecem com ação "none",
        # mas continuam presentes no RBD e afetam R_sys.
        validar_referencias(topologia, set(self.componentes), exigir_todos=True)

        self.topologia = topologia
        self.duracao_missao = float(duracao_missao)
        self.janela_manutencao = float(janela_manutencao)
        self.alpha_conclusao = float(alpha_conclusao)
        self.modo_tempo = modo_tempo
        self.n_simulacoes = int(n_simulacoes)
        self.seed = int(seed)
        self.ativos_candidatos = set(ativos_candidatos) if ativos_candidatos is not None else None
        if self.ativos_candidatos is not None:
            desconhecidos = self.ativos_candidatos - set(self.componentes)
            if desconhecidos:
                raise ValueError(f"Ativos candidatos ausentes do RBD: {sorted(desconhecidos)}")

        self._rng = np.random.default_rng(self.seed)
        self._samples: dict[tuple[str, TipoAcaoSelective], np.ndarray] = {}
        self._prepare_duration_samples()
        self._cache: dict[tuple[tuple[str, str], ...], _Candidate] = {}

    # ------------------------------------------------------------------
    # Tempos de ação
    # ------------------------------------------------------------------
    @staticmethod
    def _sigma_or_default(mttr: float, sigma: float | None) -> float:
        return float(sigma if sigma is not None else 0.4 * mttr)

    def action_duration_params(
        self, component_id: str, action: TipoAcaoSelective
    ) -> tuple[float, float]:
        c = self.componentes[component_id]
        if action == "none":
            return 0.0, 0.0
        if action == "minimal_repair":
            if c.operacional:
                raise ValueError(f"Reparo mínimo inválido para componente operacional {component_id}")
            return c.tempo_reparo_minimo, self._sigma_or_default(
                c.tempo_reparo_minimo, c.sigma_reparo_minimo
            )
        if action == "replace":
            if c.operacional:
                mttr = c.tempo_substituicao_operacional
                sigma = c.sigma_substituicao_operacional
            else:
                mttr = c.tempo_substituicao_falhado
                sigma = c.sigma_substituicao_falhado
            return mttr, self._sigma_or_default(mttr, sigma)
        raise ValueError(f"Ação desconhecida: {action}")

    def _prepare_duration_samples(self) -> None:
        for cid in self.componentes:
            for action in self.valid_actions(cid, ignore_candidate_filter=True):
                mttr, sigma = self.action_duration_params(cid, action)
                if action == "none":
                    self._samples[(cid, action)] = np.zeros(self.n_simulacoes)
                elif self.modo_tempo == "deterministic":
                    self._samples[(cid, action)] = np.full(self.n_simulacoes, mttr)
                else:
                    self._samples[(cid, action)] = amostrar_lognormal_por_media_desvio(
                        mttr, sigma, self.n_simulacoes, self._rng
                    )

    # ------------------------------------------------------------------
    # Modelo físico
    # ------------------------------------------------------------------
    @staticmethod
    def _weibull_conditional(
        idade: float, missao: float, beta: float, eta: float, gamma: float = 0.0
    ) -> float:
        inicio = max(0.0, idade - gamma)
        fim = max(0.0, idade + missao - gamma)
        expoente = -((fim / eta) ** beta - (inicio / eta) ** beta)
        return float(exp(expoente))

    def valid_actions(
        self, component_id: str, *, ignore_candidate_filter: bool = False
    ) -> tuple[TipoAcaoSelective, ...]:
        if (
            not ignore_candidate_filter
            and self.ativos_candidatos is not None
            and component_id not in self.ativos_candidatos
        ):
            return ("none",)
        c = self.componentes[component_id]
        return ("none", "replace") if c.operacional else ACTIONS

    def component_reliability(self, component_id: str, action: TipoAcaoSelective) -> float:
        c = self.componentes[component_id]
        if action == "none":
            if not c.operacional:
                return 0.0
            idade = c.idade
        elif action == "minimal_repair":
            if c.operacional:
                raise ValueError(f"Reparo mínimo inválido para {component_id}")
            idade = c.idade
        elif action == "replace":
            idade = 0.0
        else:
            raise ValueError(f"Ação desconhecida: {action}")
        return self._weibull_conditional(
            idade,
            self.duracao_missao,
            c.weibull_beta,
            c.weibull_eta,
            c.weibull_gamma,
        )

    def evaluate(self, actions: dict[str, TipoAcaoSelective]) -> _Candidate:
        completas: dict[str, TipoAcaoSelective] = {}
        reliabilities: dict[str, float] = {}
        total_samples = np.zeros(self.n_simulacoes)
        expected = 0.0

        for cid in self.componentes:
            action = actions.get(cid, "none")
            if action not in self.valid_actions(cid):
                raise ValueError(f"Ação {action} inválida para {cid}")
            completas[cid] = action
            reliabilities[cid] = self.component_reliability(cid, action)
            mttr, _ = self.action_duration_params(cid, action)
            expected += mttr
            total_samples += self._samples[(cid, action)]

        key = tuple(sorted((cid, str(a)) for cid, a in completas.items()))
        if key in self._cache:
            return self._cache[key]

        r_sys = confiabilidade_rbd(self.topologia, reliabilities)
        prob = float(np.mean(total_samples <= self.janela_manutencao + 1e-12))
        p50, p90, p95 = np.quantile(total_samples, [0.50, 0.90, 0.95])
        candidate = _Candidate(
            completas,
            float(r_sys),
            float(expected),
            prob,
            float(p50),
            float(p90),
            float(p95),
        )
        self._cache[key] = candidate
        return candidate

    def baseline(self) -> _Candidate:
        return self.evaluate({cid: "none" for cid in self.componentes})

    def feasible(self, candidate: _Candidate) -> bool:
        if self.modo_tempo == "deterministic":
            return candidate.expected_time <= self.janela_manutencao + 1e-12
        return candidate.completion_probability + 1e-12 >= self.alpha_conclusao

    # ------------------------------------------------------------------
    # Heurística construtiva
    # ------------------------------------------------------------------
    def _minimum_recovery_plan(self) -> dict[str, TipoAcaoSelective]:
        def merge(a, b):
            out = dict(a)
            out.update(b)
            return out

        def plan(no: NoRBD) -> tuple[float, dict[str, TipoAcaoSelective]]:
            if no.tipo == "component":
                cid = no.componente_id
                assert cid is not None
                c = self.componentes[cid]
                if c.operacional:
                    return 0.0, {}
                choices = []
                for action in self.valid_actions(cid):
                    if action == "none":
                        continue
                    mttr, _ = self.action_duration_params(cid, action)
                    choices.append((mttr, {cid: action}))
                if not choices:
                    return float("inf"), {}
                return min(choices, key=lambda item: item[0])

            children = [plan(child) for child in no.filhos]
            if no.tipo == "series":
                total = sum(t for t, _ in children)
                merged = {}
                for _, child_plan in children:
                    merged = merge(merged, child_plan)
                return total, merged
            if no.tipo == "parallel":
                return min(children, key=lambda item: item[0])
            raise ValueError(no.tipo)

        _, actions = plan(self.topologia)
        if not actions:
            return {}
        candidate = self.evaluate(actions)
        return actions if self.feasible(candidate) else {}

    @staticmethod
    def _better(a: _Candidate, b: _Candidate) -> bool:
        if a.reliability > b.reliability + 1e-15:
            return True
        if abs(a.reliability - b.reliability) <= 1e-15:
            if a.completion_probability > b.completion_probability + 1e-12:
                return True
            if abs(a.completion_probability - b.completion_probability) <= 1e-12:
                return a.expected_time < b.expected_time - 1e-12
        return False

    def solve_heuristic(self) -> ResultadoSelective:
        current = self.baseline()
        if current.reliability == 0.0:
            recovery = self._minimum_recovery_plan()
            if recovery:
                current = self.evaluate(recovery)

        while True:
            best = None
            best_ratio = 0.0
            for cid in self.componentes:
                old = current.actions[cid]
                for new in self.valid_actions(cid):
                    if new == old:
                        continue
                    actions = dict(current.actions)
                    actions[cid] = new
                    cand = self.evaluate(actions)
                    if not self.feasible(cand):
                        continue
                    delta_t = cand.expected_time - current.expected_time
                    delta_r = cand.reliability - current.reliability
                    if delta_t <= 1e-12 or delta_r <= 1e-15:
                        continue
                    ratio = delta_r / delta_t
                    if ratio > best_ratio + 1e-15:
                        best_ratio = ratio
                        best = cand
            if best is None:
                break
            current = best
        return self._to_result(current, "heuristic")

    # ------------------------------------------------------------------
    # Tabu Search
    # ------------------------------------------------------------------
    def solve_tabu(self, max_iterations: int = 1000, tabu_tenure: int = 7) -> ResultadoSelective:
        if max_iterations <= 0 or tabu_tenure <= 0:
            raise ValueError("max_iterations e tabu_tenure devem ser > 0")
        h = self.solve_heuristic()
        current = self.evaluate({i.ativo_id: i.acao for i in h.itens})
        best = current
        tabu_until: dict[tuple[str, TipoAcaoSelective], int] = {}

        for iteration in range(max_iterations):
            neighbors = []
            for cid in self.componentes:
                old = current.actions[cid]
                for new in self.valid_actions(cid):
                    if new == old:
                        continue
                    actions = dict(current.actions)
                    actions[cid] = new
                    cand = self.evaluate(actions)
                    if not self.feasible(cand):
                        continue
                    is_tabu = tabu_until.get((cid, new), -1) > iteration
                    aspiration = self._better(cand, best)
                    if not is_tabu or aspiration:
                        neighbors.append((cand, cid, old))
            if not neighbors:
                break
            cand, cid, old = max(
                neighbors,
                key=lambda item: (
                    item[0].reliability,
                    item[0].completion_probability,
                    -item[0].expected_time,
                ),
            )
            current = cand
            tabu_until[(cid, old)] = iteration + tabu_tenure
            if self._better(current, best):
                best = current

        return self._to_result(
            best,
            "tabu",
            {"iterations": max_iterations, "tabu_tenure": tabu_tenure},
        )

    # ------------------------------------------------------------------
    # Exato (branch-and-bound para instâncias pequenas)
    # ------------------------------------------------------------------
    def solve_exact(self) -> ResultadoSelective:
        ids = list(self.componentes)
        incumbent = self.solve_heuristic()
        best = self.evaluate({i.ativo_id: i.acao for i in incumbent.itens})
        stats = {"nodes": 0, "pruned_chance": 0, "pruned_bound": 0}
        baseline_actions = {cid: "none" for cid in ids}
        base = self.evaluate(baseline_actions)

        def gain(cid: str) -> float:
            if "replace" not in self.valid_actions(cid):
                return 0.0
            a = dict(baseline_actions)
            a[cid] = "replace"
            return self.evaluate(a).reliability - base.reliability

        ids.sort(key=gain, reverse=True)

        def optimistic_bound(partial):
            a = dict(partial)
            for cid in ids:
                if cid not in a:
                    actions = self.valid_actions(cid)
                    a[cid] = max(actions, key=lambda x: self.component_reliability(cid, x))
            return self.evaluate(a).reliability

        def partial_feasible(partial):
            # Tempos são positivos: se o plano parcial já viola a chance, extensões não recuperam.
            return self.feasible(self.evaluate(partial))

        def dfs(index, partial):
            nonlocal best
            stats["nodes"] += 1
            if not partial_feasible(partial):
                stats["pruned_chance"] += 1
                return
            if optimistic_bound(partial) < best.reliability - 1e-15:
                stats["pruned_bound"] += 1
                return
            if index == len(ids):
                cand = self.evaluate(partial)
                if self._better(cand, best):
                    best = cand
                return
            cid = ids[index]
            local = list(self.valid_actions(cid))
            local.sort(key=lambda a: self.component_reliability(cid, a), reverse=True)
            for action in local:
                partial[cid] = action
                dfs(index + 1, partial)
                partial.pop(cid)

        dfs(0, {})
        return self._to_result(best, "exact", stats)

    def solve(self, solver: str = "heuristic") -> ResultadoSelective:
        if solver == "heuristic":
            return self.solve_heuristic()
        if solver == "tabu":
            return self.solve_tabu()
        if solver == "exact":
            return self.solve_exact()
        raise ValueError(f"Solver desconhecido: {solver}")

    def _to_result(self, candidate: _Candidate, solver: str, metadados=None) -> ResultadoSelective:
        baseline = self.baseline()
        itens = []
        for cid, c in self.componentes.items():
            action = candidate.actions[cid]
            mttr, sigma = self.action_duration_params(cid, action)
            itens.append(ItemPlanoSelective(
                ativo_id=cid,
                ativo_nome=c.nome,
                acao=action,
                mttr_acao=mttr,
                sigma_acao=sigma,
                confiabilidade_componente=self.component_reliability(cid, action),
            ))
        return ResultadoSelective(
            solver=solver,  # type: ignore[arg-type]
            modo_tempo=self.modo_tempo,
            duracao_missao=self.duracao_missao,
            janela_manutencao=self.janela_manutencao,
            alpha_conclusao=self.alpha_conclusao,
            probabilidade_conclusao=candidate.completion_probability,
            confiabilidade_inicial=baseline.reliability,
            confiabilidade_final=candidate.reliability,
            ganho_confiabilidade=candidate.reliability - baseline.reliability,
            tempo_esperado=candidate.expected_time,
            tempo_usado=candidate.expected_time,
            tempo_p50=candidate.p50,
            tempo_p90=candidate.p90,
            tempo_p95=candidate.p95,
            itens=itens,
            metadados=metadados or {},
        )
