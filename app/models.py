"""Modelos de dados compartilhados pelas três camadas do framework.

Fluxo:
1) FUCOM + PROMETHEE II -> quais ativos;
2) Bruss X·RUL condicional -> quando intervir;
3) RBD completo + Selective Maintenance estocástica -> o que fazer na janela.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Direcao = Literal["max", "min"]


class Criterio(BaseModel):
    nome: str
    direcao: Direcao = "max"
    q: float = Field(ge=0)
    p: float = Field(gt=0)

    @field_validator("p")
    @classmethod
    def p_maior_que_q(cls, p, info):
        q = info.data.get("q")
        if q is not None and p <= q:
            raise ValueError(f"p ({p}) deve ser maior que q ({q})")
        return p


class CriterioFUCOM(BaseModel):
    posicao: int = Field(ge=1)
    nome: str
    phi: float = Field(ge=1.0)


class Ativo(BaseModel):
    id: str
    nome: str
    desempenhos: dict[str, float]


class ResultadoPROMETHEE(BaseModel):
    ids: list[str]
    phi_plus: list[float]
    phi_minus: list[float]
    phi_net: list[float]
    ranks: list[int]


class ConfigMC(BaseModel):
    n_iteracoes: int = Field(default=1000, ge=100, le=10000)
    delta_pesos: float = Field(default=0.20, ge=0.0, le=0.5)
    delta_desempenho: float = Field(default=0.15, ge=0.0, le=0.5)
    seed: int | None = None


class ResultadoMC(BaseModel):
    ids: list[str]
    rank_nominal: list[int]
    rank_modal: list[int]
    rank_medio: list[float]
    rank_p5: list[float]
    rank_p95: list[float]
    prob_top_n: list[float]
    n_top: int


class Parada(BaseModel):
    id: int = Field(ge=1)
    inicio: float = Field(ge=0)
    duracao: float = Field(gt=0)


class AgendaParadasPlanta(BaseModel):
    horizonte_T: float = Field(gt=0)
    paradas: list[Parada]

    @field_validator("paradas")
    @classmethod
    def paradas_dentro_do_horizonte(cls, paradas, info):
        T = info.data.get("horizonte_T")
        if T is not None:
            for p in paradas:
                if p.inicio + p.duracao > T:
                    raise ValueError(f"Parada {p.id} extrapola o horizonte T={T}h")
        return paradas


class ParametrosAtivoBruss(BaseModel):
    ativo_id: str
    idade_atual: float = Field(default=0.0, ge=0)
    weibull_beta: float = Field(gt=0)
    weibull_eta: float = Field(gt=0)
    weibull_gamma: float = Field(ge=0, default=0.0)
    mttr: float = Field(gt=0)
    sigma_t: float = Field(gt=0)
    threshold_override: float | None = Field(default=None, ge=0.0, le=1.0)


class ConfigBruss(BaseModel):
    threshold_global: float = Field(default=0.35, ge=0.0, le=1.0)
    tipo_mantenabilidade: Literal["lognormal", "exponencial"] = "lognormal"


TipoDecisao = Literal["otima", "otima_threshold_alto", "degradada", "eliminada"]


class AvaliacaoParada(BaseModel):
    parada_id: int
    inicio: float
    duracao: float
    X: float
    R: float
    p: float
    odd: float
    rank: int | None = None
    tipo_decisao: TipoDecisao
    soma_odds_acumulada: float | None = None


class ResultadoBrussAtivo(BaseModel):
    ativo_id: str
    ativo_nome: str
    threshold_aplicado: float
    avaliacoes: list[AvaliacaoParada]
    parada_otima_id: int | None
    n_otimas: int
    n_degradadas: int
    n_eliminadas: int


class DecisaoIntegrada(BaseModel):
    rank_promethee: int
    ativo_id: str
    ativo_nome: str
    parada_recomendada_id: int | None
    instante_parada: float | None
    duracao_parada: float | None
    p_sucesso: float | None
    tipo_decisao: TipoDecisao
    threshold_usado: float
    observacao: str


TipoNoRBD = Literal["component", "series", "parallel"]
TipoAcaoSelective = Literal["none", "minimal_repair", "replace"]
TipoTempoSelective = Literal["stochastic", "deterministic"]


class NoRBD(BaseModel):
    tipo: TipoNoRBD
    componente_id: str | None = None
    filhos: list["NoRBD"] = Field(default_factory=list)

    @field_validator("filhos")
    @classmethod
    def validar_filhos(cls, filhos, info):
        tipo = info.data.get("tipo")
        if tipo in {"series", "parallel"} and len(filhos) < 2:
            raise ValueError(f"Nó {tipo} deve possuir pelo menos dois filhos")
        return filhos

    def model_post_init(self, __context):
        if self.tipo == "component":
            if not self.componente_id:
                raise ValueError("Nó component exige componente_id")
            if self.filhos:
                raise ValueError("Nó component não pode possuir filhos")
        elif self.componente_id is not None:
            raise ValueError("Nós series/parallel não devem possuir componente_id")


class ComponenteSelective(BaseModel):
    """Parâmetros físicos e distribuições de duração por ativo x ação.

    idade representa a idade do componente no início da janela de manutenção.
    Os campos tempo_* representam a média observada/estimada (MTTR da ação).
    sigma_* representa a dispersão em horas. Se omitido, o motor usa 0.4*MTTR.
    """
    ativo_id: str
    nome: str
    operacional: bool = True
    idade: float = Field(ge=0)
    weibull_beta: float = Field(gt=0)
    weibull_eta: float = Field(gt=0)
    weibull_gamma: float = Field(default=0.0, ge=0)

    tempo_reparo_minimo: float = Field(gt=0, description="MTTR do reparo mínimo")
    sigma_reparo_minimo: float | None = Field(default=None, gt=0)
    tempo_substituicao_falhado: float = Field(gt=0, description="MTTR da substituição de falhado")
    sigma_substituicao_falhado: float | None = Field(default=None, gt=0)
    tempo_substituicao_operacional: float = Field(gt=0, description="MTTR da substituição preventiva")
    sigma_substituicao_operacional: float | None = Field(default=None, gt=0)

    def model_post_init(self, __context):
        if self.tempo_substituicao_falhado < self.tempo_reparo_minimo:
            raise ValueError("tempo_substituicao_falhado deve ser >= tempo_reparo_minimo")


class ItemPlanoSelective(BaseModel):
    ativo_id: str
    ativo_nome: str
    acao: TipoAcaoSelective
    mttr_acao: float = Field(ge=0)
    sigma_acao: float = Field(ge=0)
    confiabilidade_componente: float = Field(ge=0, le=1)


class ResultadoSelective(BaseModel):
    solver: Literal["heuristic", "tabu", "exact"]
    modo_tempo: TipoTempoSelective
    duracao_missao: float = Field(gt=0)
    janela_manutencao: float = Field(gt=0)
    alpha_conclusao: float = Field(ge=0, le=1)
    probabilidade_conclusao: float = Field(ge=0, le=1)
    confiabilidade_inicial: float = Field(ge=0, le=1)
    confiabilidade_final: float = Field(ge=0, le=1)
    ganho_confiabilidade: float
    tempo_esperado: float = Field(ge=0)
    tempo_usado: float = Field(ge=0, description="Compatibilidade: igual ao tempo esperado/MTTR agregado")
    tempo_p50: float = Field(ge=0)
    tempo_p90: float = Field(ge=0)
    tempo_p95: float = Field(ge=0)
    itens: list[ItemPlanoSelective]
    metadados: dict[str, float | int | str] = Field(default_factory=dict)


class EstrategiaParada(BaseModel):
    """Saída final das três camadas para uma parada."""
    parada_id: int
    inicio: float
    duracao: float
    ativos_candidatos: list[str]
    resultado_selective: ResultadoSelective
