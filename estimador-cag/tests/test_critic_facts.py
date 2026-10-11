from schemas.estimation import EstimationResult, Phase
from services.critic import build_critic_facts
from sessions import ProjectMetadata


def _phase(name: str, cost: int) -> Phase:
    return Phase(
        name=name,
        duration_weeks=2,
        cost_eur=cost,
        summary="Enough text so the phase summary clears the minimum.",
    )


def test_cheatsheet_shares_and_rate_band() -> None:
    result = EstimationResult(
        summary="A mid-size CRM with contacts, a pipeline and HubSpot import.",
        confidence_pct=60,
        phases=[
            _phase("Discovery", 4_000),
            _phase("Design", 4_000),
            _phase("Implementation", 16_000),
            _phase("QA", 4_000),
            _phase("Launch", 3_000),
        ],
        total_duration_weeks=10,
        total_cost_eur=0,
    )
    facts = build_critic_facts(
        result, ProjectMetadata(assumed_team_size=3)
    )
    assert result.total_cost_eur == 31_000
    assert facts["phase_shares"][2]["share_pct"] == 51.6
    assert facts["rate_band_eur"] == 60_000
    assert facts["delta_vs_band_pct"] == -48.3
