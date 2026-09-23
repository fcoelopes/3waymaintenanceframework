"""Modelos de dados do motor RCPSP para grandes paradas.

O domínio público usa horas decimais. O solver converte as durações e janelas
para ticks inteiros de forma conservadora, porque o CP-SAT opera sobre inteiros.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

StatusRCPSP = Literal["optimal", "feasible", "infeasible", "unknown"]


class RecursoRCPSP(BaseModel):
    id: str = Field(min_length=1)
    nome: str = Field(min_length=1)
    capacidade: int = Field(ge=1)
    exclusivo: bool = False

    @model_validator(mode="after")
    def validar_exclusivo(self):
        if self.exclusivo and self.capacidade != 1:
            raise ValueError("Recurso exclusivo deve possuir capacidade=1")
        return self


class RequisitoRecursoRCPSP(BaseModel):
    recurso_id: str = Field(min_length=1)
    quantidade: int = Field(ge=1)


class BloqueioRecursoRCPSP(BaseModel):
    """Redução de capacidade durante uma janela.

    Para recurso exclusivo, reducao_capacidade deve ser 1 e o intervalo funciona
    como indisponibilidade total.
    """

    recurso_id: str = Field(min_length=1)
    inicio_h: float = Field(ge=0)
    fim_h: float = Field(gt=0)
    reducao_capacidade: int = Field(ge=1)
    motivo: str | None = None

    @model_validator(mode="after")
    def validar_intervalo(self):
        if self.fim_h <= self.inicio_h:
            raise ValueError("fim_h deve ser maior que inicio_h")
        return self


class AtividadeRCPSP(BaseModel):
    id: str = Field(min_length=1)
    nome: str = Field(min_length=1)
    work_package_id: str = Field(min_length=1)
    duracao_h: float = Field(gt=0)
    predecessores: list[str] = Field(default_factory=list)
    recursos: list[RequisitoRecursoRCPSP] = Field(default_factory=list)
    earliest_start_h: float = Field(default=0.0, ge=0)
    latest_finish_h: float | None = Field(default=None, gt=0)
    ativo_id: str | None = None
    acao_origem: str | None = None
    obrigatoria: bool = True

    @field_validator("predecessores")
    @classmethod
    def predecessores_unicos(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("predecessores não podem conter duplicatas")
        return value

    @field_validator("recursos")
    @classmethod
    def recursos_unicos(cls, value):
        ids = [r.recurso_id for r in value]
        if len(ids) != len(set(ids)):
            raise ValueError("um recurso só pode aparecer uma vez por atividade")
        return value

    @model_validator(mode="after")
    def validar_janela(self):
        if self.latest_finish_h is not None:
            if self.latest_finish_h <= self.earliest_start_h:
                raise ValueError("latest_finish_h deve ser maior que earliest_start_h")
            if self.duracao_h > self.latest_finish_h - self.earliest_start_h:
                raise ValueError(
                    "a duração não cabe entre earliest_start_h e latest_finish_h"
                )
        if self.id in self.predecessores:
            raise ValueError("atividade não pode ser predecessora de si mesma")
        return self


class InstanciaRCPSP(BaseModel):
    """Instância determinística de RCPSP para uma janela de parada."""

    janela_h: float = Field(gt=0)
    atividades: list[AtividadeRCPSP]
    recursos: list[RecursoRCPSP] = Field(default_factory=list)
    bloqueios_recursos: list[BloqueioRecursoRCPSP] = Field(default_factory=list)
    time_unit_minutes: int = Field(default=15, ge=1, le=60)
    max_solve_seconds: float = Field(default=30.0, gt=0, le=3600)
    num_workers: int = Field(default=8, ge=1, le=64)
    random_seed: int = 42

    @model_validator(mode="after")
    def validar_instancia(self):
        if not self.atividades:
            raise ValueError("é necessário informar pelo menos uma atividade")

        ids_atividades = [a.id for a in self.atividades]
        if len(ids_atividades) != len(set(ids_atividades)):
            raise ValueError("IDs de atividades devem ser únicos")

        ids_recursos = [r.id for r in self.recursos]
        if len(ids_recursos) != len(set(ids_recursos)):
            raise ValueError("IDs de recursos devem ser únicos")
        recursos = {r.id: r for r in self.recursos}

        atividades = set(ids_atividades)
        for a in self.atividades:
            desconhecidos = set(a.predecessores) - atividades
            if desconhecidos:
                raise ValueError(
                    f"atividade {a.id} referencia predecessores inexistentes: "
                    f"{sorted(desconhecidos)}"
                )
            if a.earliest_start_h >= self.janela_h:
                raise ValueError(
                    f"earliest_start_h de {a.id} está fora da janela da parada"
                )
            if a.latest_finish_h is not None and a.latest_finish_h > self.janela_h:
                raise ValueError(
                    f"latest_finish_h de {a.id} excede janela_h={self.janela_h}"
                )
            for req in a.recursos:
                if req.recurso_id not in recursos:
                    raise ValueError(
                        f"atividade {a.id} referencia recurso inexistente "
                        f"{req.recurso_id}"
                    )
                if req.quantidade > recursos[req.recurso_id].capacidade:
                    raise ValueError(
                        f"atividade {a.id} exige {req.quantidade} de "
                        f"{req.recurso_id}, acima da capacidade "
                        f"{recursos[req.recurso_id].capacidade}"
                    )
                if recursos[req.recurso_id].exclusivo and req.quantidade != 1:
                    raise ValueError(
                        f"recurso exclusivo {req.recurso_id} deve ser requerido "
                        "com quantidade=1"
                    )

        for b in self.bloqueios_recursos:
            if b.recurso_id not in recursos:
                raise ValueError(
                    f"bloqueio referencia recurso inexistente {b.recurso_id}"
                )
            r = recursos[b.recurso_id]
            if b.reducao_capacidade > r.capacidade:
                raise ValueError(
                    f"bloqueio reduz mais capacidade que a disponível em {r.id}"
                )
            if r.exclusivo and b.reducao_capacidade != 1:
                raise ValueError(
                    f"bloqueio de recurso exclusivo {r.id} deve reduzir 1"
                )
            if b.fim_h > self.janela_h:
                raise ValueError(
                    f"bloqueio de {b.recurso_id} excede janela_h={self.janela_h}"
                )
        return self


class AtividadeAgendadaRCPSP(BaseModel):
    id: str
    nome: str
    work_package_id: str
    inicio_h: float = Field(ge=0)
    fim_h: float = Field(ge=0)
    duracao_h: float = Field(gt=0)
    ativo_id: str | None = None
    acao_origem: str | None = None
    recursos: list[RequisitoRecursoRCPSP] = Field(default_factory=list)


class UtilizacaoRecursoRCPSP(BaseModel):
    recurso_id: str
    nome: str
    capacidade: int
    carga_h_equivalente: float = Field(ge=0)
    capacidade_h_total: float = Field(gt=0)
    utilizacao_media: float = Field(ge=0)
    pico_utilizado: int = Field(ge=0)


class ResultadoRCPSP(BaseModel):
    status: StatusRCPSP
    solver: str = "cp-sat"
    janela_h: float = Field(gt=0)
    time_unit_minutes: int = Field(ge=1)
    makespan_h: float | None = Field(default=None, ge=0)
    objetivo: str = "min_makespan"
    atividades: list[AtividadeAgendadaRCPSP] = Field(default_factory=list)
    utilizacao_recursos: list[UtilizacaoRecursoRCPSP] = Field(default_factory=list)
    diagnosticos: list[str] = Field(default_factory=list)
    wall_time_s: float = Field(ge=0)
    objective_value_ticks: float | None = None
    best_bound_ticks: float | None = None
