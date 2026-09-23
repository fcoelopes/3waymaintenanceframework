"""Camada operacional: RBD completo + Selective Maintenance estocástica."""
import json

import pandas as pd
import streamlit as st

from app.core.framework import proxima_oportunidade
from app.core.selective_maintenance import SelectiveMaintenanceProblem
from app.models import ComponenteSelective, NoRBD

st.title("9 · Selective Maintenance — O que fazer?")
st.caption(
    "A duração da parada escolhida pelo Bruss vira T0. O Selective otimiza somente "
    "os candidatos da parada, mas R_sys é calculado sobre o RBD completo do sistema."
)

decisoes = st.session_state.get("decisoes_integradas")
grupos = st.session_state.get("candidatos_por_parada")
agenda = st.session_state.get("agenda_planta")
params_bruss = st.session_state.get("parametros_bruss", {})
bruss = st.session_state.get("resultado_bruss", {})
nomes = st.session_state.get("nomes_ativos", {})
ativos_df = st.session_state.get("ativos_df")

if not decisoes or not grupos or agenda is None:
    st.warning("Consolide primeiro a decisão integrada na página 8.")
    st.stop()

parada_ids = sorted(grupos)
parada_id = st.selectbox("Parada a planejar", parada_ids)
parada = next(p for p in agenda.paradas if p.id == parada_id)
candidatos = list(grupos[parada_id])
candidatos_set = set(candidatos)

st.info(
    f"Parada {parada.id}: início em +{parada.inicio:.1f} h, janela T0={parada.duracao:.2f} h. "
    f"Candidatos Bruss: {', '.join(candidatos)}"
)

# ---------------------------------------------------------------------
# Sistema físico: componentes do RBD != candidatos à intervenção.
# ---------------------------------------------------------------------
if ativos_df is not None and not ativos_df.empty:
    carteira_ids = ativos_df["id"].astype(str).tolist()
    nomes_carteira = dict(zip(ativos_df["id"].astype(str), ativos_df["nome"].astype(str)))
    nomes = {**nomes_carteira, **nomes}
else:
    carteira_ids = sorted(set(nomes) | candidatos_set)

for aid in candidatos:
    if aid not in carteira_ids:
        carteira_ids.append(aid)

st.subheader("A · Escopo do sistema")
st.caption(
    "Selecione todos os componentes que pertencem ao sistema cuja confiabilidade será "
    "avaliada. Os candidatos podem receber ações; os demais ficam em 'none', mas continuam "
    "afetando R_sys."
)

system_state_key = f"selective_system_ids_{parada_id}"
previous = st.session_state.get(system_state_key, carteira_ids)
default_ids = [aid for aid in previous if aid in carteira_ids] or carteira_ids
system_ids = st.multiselect(
    "Componentes do RBD completo",
    options=carteira_ids,
    default=default_ids,
    format_func=lambda aid: f"{aid} · {nomes.get(aid, aid)}",
)
st.session_state[system_state_key] = system_ids

if not system_ids:
    st.warning("Selecione pelo menos um componente para o sistema.")
    st.stop()

fora_do_sistema = sorted(candidatos_set - set(system_ids))
if fora_do_sistema:
    st.error(
        "Todos os candidatos da parada precisam pertencer ao sistema/RBD. "
        f"Ausentes: {', '.join(fora_do_sistema)}"
    )
    st.stop()

signature = "__".join(system_ids)
components_key = f"selective_components_{parada_id}_{signature}"

if components_key not in st.session_state:
    rows = []
    for aid in system_ids:
        pb = params_bruss.get(aid)
        mttr = float(pb.mttr if pb else 5.0)
        sigma = float(pb.sigma_t if pb else 2.0)
        idade_atual = float(pb.idade_atual if pb else 0.0)
        rows.append({
            "ativo_id": aid,
            "nome": nomes.get(aid, aid),
            "candidato": aid in candidatos_set,
            "operacional": True,
            # Idade esperada no início da oportunidade, antes de qualquer ação.
            "idade": idade_atual + float(parada.inicio),
            "weibull_beta": float(pb.weibull_beta if pb else 1.5),
            "weibull_eta": float(pb.weibull_eta if pb else 600.0),
            "weibull_gamma": float(pb.weibull_gamma if pb else 0.0),
            "tempo_reparo_minimo": mttr,
            "sigma_reparo_minimo": sigma,
            "tempo_substituicao_falhado": mttr,
            "sigma_substituicao_falhado": sigma,
            "tempo_substituicao_operacional": mttr,
            "sigma_substituicao_operacional": sigma,
        })
    st.session_state[components_key] = pd.DataFrame(rows)

st.subheader("B · Estado e duração por componente × ação")
st.caption(
    "Componentes não candidatos permanecem no RBD, mas o solver só poderá escolher 'none' "
    "para eles. Ajuste idade, Weibull e tempos de ação com dados do sistema real."
)
edited = st.data_editor(
    st.session_state[components_key],
    use_container_width=True,
    num_rows="fixed",
    disabled=["ativo_id", "nome", "candidato"],
    column_config={
        "candidato": st.column_config.CheckboxColumn("Candidato Bruss"),
        "idade": st.column_config.NumberColumn("Idade na parada (h)", min_value=0.0),
    },
)
st.session_state[components_key] = edited

# ---------------------------------------------------------------------
# RBD completo.
# ---------------------------------------------------------------------
st.subheader("C · RBD completo")
if len(system_ids) == 1:
    topo_default = {"tipo": "component", "componente_id": system_ids[0]}
else:
    topo_default = {
        "tipo": "series",
        "filhos": [{"tipo": "component", "componente_id": aid} for aid in system_ids],
    }

topo_key = f"selective_topology_{parada_id}_{signature}"
if topo_key not in st.session_state:
    st.session_state[topo_key] = json.dumps(topo_default, indent=2)

st.warning(
    "A topologia série abaixo é apenas um ponto inicial. Substitua pelo RBD real. "
    "O motor rejeitará uma topologia que omita qualquer componente selecionado do sistema."
)
topology_text = st.text_area(
    "Topologia série/paralelo em JSON",
    value=st.session_state[topo_key],
    height=300,
)
st.session_state[topo_key] = topology_text

# ---------------------------------------------------------------------
# Otimização.
# ---------------------------------------------------------------------
st.subheader("D · Restrição de chance")
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
    format_func=lambda x: (
        "Estocástico — MTTR + σT"
        if x == "stochastic"
        else "Determinístico — benchmark do artigo"
    ),
)

if st.button("▶ Montar estratégia da parada", type="primary"):
    try:
        records = []
        for raw in edited.to_dict("records"):
            row = dict(raw)
            row.pop("candidato", None)
            records.append(row)

        componentes = [ComponenteSelective(**r) for r in records]
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
            ativos_candidatos=candidatos_set,
        )
        result = problem.solve(solver)
        st.session_state[f"resultado_selective_{parada_id}"] = result
    except Exception as exc:
        st.error(f"Não foi possível otimizar a parada: {exc}")

result = st.session_state.get(f"resultado_selective_{parada_id}")
if result:
    st.subheader("E · Estratégia de manutenção")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "R sistema completo",
        f"{result.confiabilidade_inicial:.4f} → {result.confiabilidade_final:.4f}",
    )
    c2.metric("ΔR", f"{result.ganho_confiabilidade:+.4f}")
    c3.metric("P(concluir em T0)", f"{100 * result.probabilidade_conclusao:.1f}%")
    c4.metric("Tempo esperado", f"{result.tempo_esperado:.2f} h")

    st.write(
        f"P50={result.tempo_p50:.2f} h · P90={result.tempo_p90:.2f} h · "
        f"P95={result.tempo_p95:.2f} h · requisito={100 * result.alpha_conclusao:.1f}%"
    )

    df = pd.DataFrame([i.model_dump() for i in result.itens])
    df["candidato"] = df["ativo_id"].isin(candidatos_set)
    df["acao"] = df["acao"].map({
        "none": "Não intervir",
        "minimal_repair": "Reparo mínimo",
        "replace": "Substituir",
    })
    st.dataframe(
        df[[
            "ativo_id",
            "ativo_nome",
            "candidato",
            "acao",
            "mttr_acao",
            "sigma_acao",
            "confiabilidade_componente",
        ]],
        hide_index=True,
        use_container_width=True,
    )

    recusados = [
        i.ativo_id
        for i in result.itens
        if i.ativo_id in candidatos_set and i.acao == "none"
    ]
    if recusados:
        st.subheader("Retorno à camada temporal")
        for aid in recusados:
            prox = proxima_oportunidade(bruss[aid], parada_id) if aid in bruss else None
            if prox is None:
                st.write(
                    f"- {aid}: não selecionado e sem próxima oportunidade "
                    "ranqueada no horizonte."
                )
            else:
                st.write(
                    f"- {aid}: não selecionado nesta janela → próxima oportunidade "
                    f"Bruss: parada {prox}."
                )

    st.session_state.estrategia_final = {
        "parada_id": parada_id,
        "candidatos": candidatos,
        "componentes_sistema": system_ids,
        "resultado": result,
    }
    st.success(
        "Framework fechado: prioridade → oportunidade temporal → portfólio de ações "
        "avaliado no RBD completo."
    )
