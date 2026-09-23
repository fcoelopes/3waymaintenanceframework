from app.core.rcpsp_adapter import rascunho_rcpsp_do_selective
from app.models import ItemPlanoSelective, ResultadoSelective


def test_adapter_selective_cria_apenas_acoes_selecionadas():
    resultado = ResultadoSelective(
        solver="heuristic",
        modo_tempo="deterministic",
        duracao_missao=40,
        janela_manutencao=10,
        alpha_conclusao=0.9,
        probabilidade_conclusao=1.0,
        confiabilidade_inicial=0.8,
        confiabilidade_final=0.9,
        ganho_confiabilidade=0.1,
        tempo_esperado=4,
        tempo_usado=4,
        tempo_p50=4,
        tempo_p90=4,
        tempo_p95=4,
        itens=[
            ItemPlanoSelective(
                ativo_id="A",
                ativo_nome="Bomba A",
                acao="replace",
                mttr_acao=3,
                sigma_acao=1,
                confiabilidade_componente=0.99,
            ),
            ItemPlanoSelective(
                ativo_id="B",
                ativo_nome="Motor B",
                acao="none",
                mttr_acao=0,
                sigma_acao=0,
                confiabilidade_componente=0.95,
            ),
        ],
    )

    instancia = rascunho_rcpsp_do_selective(
        resultado,
        janela_h=10,
        capacidade_equipe_geral=2,
    )

    assert len(instancia.atividades) == 1
    assert instancia.atividades[0].ativo_id == "A"
    assert instancia.atividades[0].acao_origem == "replace"
    assert instancia.recursos[0].capacidade == 2
