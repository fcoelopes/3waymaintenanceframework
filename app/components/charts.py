"""
Wrappers Plotly para visualizações usadas em múltiplas páginas.

Inclui visualizações específicas para Thomas et al. 2008:
- Curvas X(d) e R(t) sobrepostas com paradas marcadas
- Gantt das paradas com classificação por tipo de decisão
- Tornado de sensibilidade ao threshold
"""
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd


# ---------- Camada PROMETHEE / FUCOM ----------

def grafico_pesos_fucom(criterios: list[str], pesos: np.ndarray) -> go.Figure:
    """Barras horizontais de pesos FUCOM em ordem decrescente."""
    # TODO: px.bar horizontal
    raise NotImplementedError


def diamante_promethee(
    ids: list[str],
    nomes: list[str],
    phi_plus: np.ndarray,
    phi_minus: np.ndarray,
    phi_net: np.ndarray,
) -> go.Figure:
    """Scatter phi+ vs phi- colorido por phi_net."""
    # TODO: scatter customizado
    raise NotImplementedError


def boxplot_robustez(ranks_iter: np.ndarray, ids: list[str]) -> go.Figure:
    """Boxplot de posições por alternativa nas iterações MC."""
    # TODO: go.Box ordenado por mediana
    raise NotImplementedError


def heatmap_top_n(prob_top_n: np.ndarray, ids: list[str], n_top: int) -> go.Figure:
    """Barras coloridas com P(top-N) por ativo."""
    # TODO: barras com colorscale RdYlGn
    raise NotImplementedError


# ---------- Camada Bruss X·R (Thomas et al.) ----------

def curvas_X_R_paradas(
    horizonte_T: float,
    beta: float,
    eta: float,
    gamma: float,
    mttr: float,
    paradas_inicio: np.ndarray,
    paradas_duracao: np.ndarray,
    paradas_X: np.ndarray,
    paradas_R: np.ndarray,
) -> go.Figure:
    """
    Plota R(t) ao longo de [0; T] com markers nas paradas indicando X(d_i).

    Eixo x: tempo; Eixo y esquerdo: R(t) (linha); Eixo y direito: X(d_i) (markers).
    Anota p_i = X·R em cada parada.

    Útil para o decisor visualizar simultaneamente:
    - O envelhecimento do componente (R caindo)
    - A "qualidade" de mantenabilidade de cada parada (duração)
    - O compromisso entre os dois critérios em cada oportunidade
    """
    # TODO: go.Figure com subplot duplo
    raise NotImplementedError


def gantt_paradas_classificadas(
    paradas: list,
    avaliacoes: list,
) -> go.Figure:
    """
    Linha do tempo das paradas coloridas pelo tipo de decisão Bruss X·R.

    Cores:
    - verde: ótima
    - amarelo: ótima_threshold_alto (*)
    - laranja: degradada (/)
    - cinza: eliminada
    """
    # TODO: gantt-like com cores por tipo
    raise NotImplementedError


def tornado_sensibilidade_threshold(
    thresholds: np.ndarray,
    parada_otima_por_threshold: list[int | None],
) -> go.Figure:
    """
    Mostra como a parada ótima muda com o threshold.

    Eixo x: threshold; Eixo y: id da parada ótima (com pontos para None = degradada).
    Faixas em que a parada ótima é estável aparecem como linhas horizontais.
    """
    # TODO: scatter com step
    raise NotImplementedError


def cronograma_integrado(
    decisoes: list,
    horizonte_T: float,
) -> go.Figure:
    """
    Gantt integrado: ativos top-N nas linhas, paradas no eixo x,
    com markers no instante da parada recomendada para cada ativo.
    Cor por tipo de decisão.
    """
    # TODO: gantt multi-linha
    raise NotImplementedError
