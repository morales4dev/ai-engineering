from rates import DEV_HOURLY_EUR, DEV_WEEK_EUR, PRODUCTIVE_HOURS_PER_WEEK, weekly_band_eur


def test_week_rate_follows_hourly_and_hours() -> None:
    assert DEV_WEEK_EUR == int(DEV_HOURLY_EUR * PRODUCTIVE_HOURS_PER_WEEK)
    assert DEV_WEEK_EUR == 2_000


def test_weekly_band_for_three_people() -> None:
    assert weekly_band_eur(3) == 3 * DEV_WEEK_EUR


def test_weekly_band_unknown_without_team() -> None:
    assert weekly_band_eur(None) is None
