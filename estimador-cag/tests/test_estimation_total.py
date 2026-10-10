from schemas.estimation import EstimationResult, Phase


def _phase(name: str, cost: int) -> Phase:
    return Phase(
        name=name,
        duration_weeks=2,
        cost_eur=cost,
        summary="Enough text so the phase summary clears the minimum.",
    )


def test_total_follows_phases_not_the_llm_number() -> None:
    result = EstimationResult(
        summary="A mid-size build with auth and a small admin panel.",
        confidence_pct=60,
        phases=[
            _phase("Discovery", 8_000),
            _phase("Build", 18_000),
            _phase("Launch", 15_000),
        ],
        total_duration_weeks=10,
        total_cost_eur=36_000,
    )
    assert result.total_cost_eur == 41_000
