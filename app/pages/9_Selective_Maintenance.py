"""Camada operacional: RBD + Selective Maintenance estocástica."""
import json

import pandas as pd
import streamlit as st

from app.core.framework import proxima_oportunidade
from app.core.selective_maintenance import SelectiveMaintenanceProblem
from app.models import ComponenteSelective, NoRBD

st.title("9 · Selective Maintenance — O que fazer?")
st.caption(
    "A duração da parada escolhida pelo Bruss vira T0. As ações têm MTTR + σT e "
    "o portfólio deve satisfazer uma probabilidade mínima de terminar na janela."
)

decisoes = st.session_state.get("decisoes_integradas")
grupos = st.session_state.get("candidatos_por_parada")
agenda = st.session_state.get("agenda_planta")
params_bruss = st.session_state.get("parametros_bruss", {})
bruss = st.session_state.get("resultado_bruss", {})
nomes = st.session_state.get("nomes_ativos", {})

if not decisoes or not grupos or agenda is None:
    st.warning("Consolide primeiro a decisão integrada na página 8.")
    st.stop()

parada_ids = sorted(grupos)
parada_id = st.selectbox("Parada a planejar", parada_ids)
parada = next(p for p in agenda.paradas if p.id == parada_id)
candidatos = grupos[parada_id]

st.info(
    f"Parada {parada.id}: início {parada.inicio:.1f} h, janela T0={parada.duracao:.2f} h. "
    f"Candidatos Bruss: {', '.join(candidatos)}"
)

key = f"selective_components_{parada_id}"
if key not in st.session_state:
    rows = []
    for aid in candidatos:
        pb = params_bruss.get(aid)
        mttr = float(pb.mttr if pb else 5.0)
        sigma = float(pb.sigma_t if pb else 2.0)
        rows.append({
            "ativo_id": aid,
            "nome": nomes.get(aid, aid),
            "operacional": True,
            "idade": float(parada.inicio),
            "weibull_beta": float(pb.weibull_beta if pb else 1.5),
            "weibull_eta": float(pb.weibull_eta if pb else 600.0),
            "weibull_gamma": float(pb.weibull_gamma if pb else 0.0),
            # Valores iniciais herdados do MTTR do ativo. Edite por ação.
            "tempo_reparo_minimo": mttr,
            "sigma_reparo_minimo": sigma,
            "tempo_substituicao_falhado": mttr,
            "sigma_substituicao_falhado": sigma,
            "tempo_substituicao_operacional": mttr,
            "sigma_substituicao_operacional": sigma,
        })
    st.session_state[key] = pd.DataFrame(rows)

st.subheader("A · Estado + duração por ativo × ação")
st.caption(
    "Os valores herdados do Bruss são apenas ponto de partida. Informe MTTR e σT específicos "
    "para reparo mínimo/substituição quando houver dados históricos."
)
edited = st.data_editor(st.session_state[key], use_container_width=True, num_rows="dynamic")
st.session_state[key] = edited

st.subheader("B · RBD")
if len(candidatos) == 1:
    topo_default = {"tipo": "component", "componente_id": candidatos[0]}
else:
    topo_default = {
        "tipo": "series",
        "filhos": [{"tipo": "component", "componente_id": aid} for aid in candidatos],
    }
topo_key = f"selective_topology_{parada_id}"
if topo_key not in st.session_state:
    st.session_state[topo_key] = json.dumps(topo_default, indent=2)
topology_text = st.text_area(
    "Topologia série/paralelo (JSON — o canvas visual poderá substituir esta entrada)",
    value=st.session_state[topo_key],
    height=260,
)
st.session_state[topo_key] = topology_text

st.subheader("C · Restrição de chance")
c1, c2, c3, c4 = st.columns(4)
with c1:
    mission = st.number_input("Próxima missão (h)", min_value=0.01, value=40.0)
with c2:
    alpha = st.slider("P mínima de concluir", 0.50, 0.999, 0.90, 0.01)
with c3:
    n_sim = st.number_input("Simulações", min_value=500, max_value=50000, value=5000, step=500)
with c4:
    solver = st.selectbox("Solver", ["heuristic", "tabu", "exact"])

modo = st.radio(
    "Modelo de duração",
    ["stochastic", "deterministic"],
    horizontal=True,
    format_func=lambda x: "Estocástico — MTTR + σT" if x == "stochastic" else "Determinístico — benchmark do artigo",
)

if st.button("▶ Montar estratégia da parada", type="primary"):
    try:
        componentes = [ComponenteSelective(**r) for r in edited.to_dict("records")]
        topologia = NoRBD.model_validate(json.loads(topology_text))
        problem = SelectiveMaintenanceProblem(
            componentes,
            topologia,
            duracao_missao=float(mission),
            janela_manutencao=float(parada.duracao),
            alpha_conclusao=float(alpha),
            modo_tempo=modo,
            n_simulacoes=int(n_sim),
            seed=42,
            ativos_candidatos=set(candidatos),
        )
        result = problem.solve(solver)
        st.session_state[f"resultado_selective_{parada_id}"] = result
    except Exception as exc:
        st.error(f"Não foi possível otimizar a parada: {exc}")

result = st.session_state.get(f"resultado_selective_{parada_id}")
if result:
    st.subheader("D · Estratégia de manutenção")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("R sistema", f"{result.confiabilidade_inicial:.4f} → {result.confiabilidade_final:.4f}")
    c2.metric("ΔR", f"{result.ganho_confiabilidade:+.4f}")
    c3.metric("P(concluir em T0)", f"{100*result.probabilidade_conclusao:.1f}%")
    c4.metric("Tempo esperado", f"{result.tempo_esperado:.2f} h")

    st.write(
        f"P50={result.tempo_p50:.2f} h · P90={result.tempo_p90:.2f} h · "
        f"P95={result.tempo_p95:.2f} h · requisito={100*result.alpha_conclusao:.1f}%"
    )
    df = pd.DataFrame([i.model_dump() for i in result.itens])
    df["acao"] = df["acao"].map({
        "none": "Não intervir",
        "minimal_repair": "Reparo mínimo",
        "replace": "Substituir",
    })
    st.dataframe(df, hide_index=True, use_container_width=True)

    # Ativos recusados pelo portfólio recebem uma pista de próxima oportunidade Bruss.
    recusados = [i.ativo_id for i in result.itens if i.ativo_id in candidatos and i.acao == "none"]
    if recusados:
        st.subheader("Retorno à camada temporal")
        for aid in recusados:
            prox = proxima_oportunidade(bruss[aid], parada_id) if aid in bruss else None
            if prox is None:
                st.write(f"- {aid}: não selecionado e sem próxima oportunidade ranqueada no horizonte.")
            else:
                st.write(f"- {aid}: não selecionado nesta janela → próxima oportunidade Bruss: parada {prox}.")

    st.session_state.estrategia_final = {
        "parada_id": parada_id,
        "candidatos": candidatos,
        "resultado": result,
    }
    st.success("Framework fechado: quais ativos → quando → o que fazer.")
