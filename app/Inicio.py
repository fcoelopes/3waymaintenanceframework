import streamlit as st

st.set_page_config(
    page_title="Framework de Apoio à Decisão em Manutenção",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    st.title("Framework de Apoio à Decisão em Manutenção")
    st.caption("Quais ativos? · Quando intervir? · O que fazer na janela?")

    st.markdown(
        """
        ### Fluxo principal
        1. **FUCOM + PROMETHEE II** — prioriza os ativos (**quais?**)
        2. **Bruss X·R** — combina confiabilidade e mantenabilidade para escolher oportunidades (**quando?**)
        3. **RBD + Selective Maintenance estocástica** — compõe as ações dentro da janela (**o quê?**)

        A terceira camada reutiliza a modelagem de tempo por **MTTR + σT**. Para um portfólio de ações,
        a viabilidade deixa de ser apenas `soma dos tempos <= T0` e passa a exigir uma probabilidade
        mínima de conclusão dentro da parada.

        **Robustez Monte Carlo** e **sensibilidade do threshold** permanecem como análises opcionais.
        """
    )

    st.info("Comece em '1 · Critérios e Pesos' e siga o menu lateral.")


if __name__ == "__main__":
    main()
