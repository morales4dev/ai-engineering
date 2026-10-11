"""Single place for the rate card. Prompts and bands read from here."""

DEV_HOURLY_EUR = 62.50
DESIGNER_HOURLY_EUR = 50.00
PRODUCTIVE_HOURS_PER_WEEK = 32
DEV_WEEK_EUR = int(DEV_HOURLY_EUR * PRODUCTIVE_HOURS_PER_WEEK)


def prompt_vars() -> dict[str, object]:
    """Jinja values so templates never hard-code the tariff."""
    return {
        "dev_hourly_eur": f"{DEV_HOURLY_EUR:.2f}",
        "designer_hourly_eur": f"{DESIGNER_HOURLY_EUR:.2f}",
        "hours_per_week": PRODUCTIVE_HOURS_PER_WEEK,
        "dev_week_eur": DEV_WEEK_EUR,
    }


def weekly_band_eur(team_size: int | None) -> int | None:
    """EUR per calendar week if the whole team is billed at the dev rate."""
    if not team_size:
        return None
    return team_size * DEV_WEEK_EUR
