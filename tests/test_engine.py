import csv
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.playoff_engine import PlayoffEngine


@pytest.fixture
def engine():
    return PlayoffEngine()


def test_csv_statistics_are_real_and_differ_between_teams(engine):
    assert len(engine.team_db) == 30
    ratings = {round(stats["OFF_RATING"], 3) for stats in engine.team_db.values()}
    assert len(ratings) > 20
    with engine.data_path.open(encoding="utf-8-sig") as source:
        row = next(csv.DictReader(source))
    assert engine.team_db[row["TEAM_NAME"]]["REB_PER_GAME"] == pytest.approx(float(row["REB"]) / float(row["GP"]))


def test_missing_or_bad_data_fails_instead_of_faking_teams(tmp_path):
    with pytest.raises(RuntimeError, match="team_stats.csv"):
        PlayoffEngine(tmp_path)
    (tmp_path / "team_stats.csv").write_text("WIN,REST_DIFF\n1,0\n")
    with pytest.raises(RuntimeError, match="columns"):
        PlayoffEngine(tmp_path)


def test_nonfinite_and_duplicate_rows_are_rejected(tmp_path, engine):
    with engine.data_path.open(encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        fields, rows = reader.fieldnames, list(reader)
    rows[0]["REB"] = "nan"
    target = tmp_path / "team_stats.csv"
    with target.open("w", newline="") as output:
        writer = csv.DictWriter(output, fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(RuntimeError, match="Invalid"):
        PlayoffEngine(tmp_path)


def test_completed_series_has_no_market(engine):
    team1, team2 = engine.west_teams[1], engine.west_teams[8]
    with pytest.raises(ValueError, match="finished"):
        engine.calculate_advanced_odds(team1, team2, [SimpleNamespace(winner=team1)] * 4)


def test_series_prices_reflect_current_score_and_are_at_least_one(engine):
    team1, team2 = engine.west_teams[1], engine.west_teams[8]
    trailing = [SimpleNamespace(winner=team2)] * 3
    leading = [SimpleNamespace(winner=team1)] * 3
    trail_odds = engine.calculate_advanced_odds(team1, team2, trailing)
    lead_odds = engine.calculate_advanced_odds(team1, team2, leading)
    assert trail_odds["series_winner"][team1] > lead_odds["series_winner"][team1]
    for market in (trail_odds, lead_odds):
        for key in ("moneyline", "series_winner"):
            assert all(math.isfinite(price) and price >= 1.01 for price in market[key].values())


def test_simulation_winner_matches_quoted_probability_and_never_ties(engine, monkeypatch):
    team1, team2 = engine.west_teams[1], engine.west_teams[8]
    probability = engine._game_probability(team1, team2)
    monkeypatch.setattr("backend.playoff_engine.random.random", lambda: probability - .001)
    monkeypatch.setattr("backend.playoff_engine.random.gauss", lambda *_: -10000)
    stats = engine.generate_game_stats(team1, team2)
    assert stats["winner"] == team1
    assert stats["t1_pts"] > stats["t2_pts"] >= 0
    assert stats["total_points"] == stats["t1_pts"] + stats["t2_pts"]
    assert stats["t1_rebounds"] == stats["t2_rebounds"] == 0
    monkeypatch.setattr("backend.playoff_engine.random.random", lambda: probability + .001)
    assert engine.generate_game_stats(team1, team2)["winner"] == team2


def test_unknown_or_identical_teams_are_not_silently_accepted(engine):
    with pytest.raises(ValueError):
        engine.generate_game_stats("unknown", engine.east_teams[1])
    with pytest.raises(ValueError):
        engine.calculate_advanced_odds(engine.east_teams[1], engine.east_teams[1])


def test_home_court_follows_seed_even_when_higher_seed_is_second(engine):
    lower, higher = engine.west_teams[8], engine.west_teams[4]
    assert engine.home_team(lower, higher, 1) == higher
    assert engine.home_team(lower, higher, 3) == lower
    engine.team_db[lower] = engine.team_db[higher].copy()
    points_lower, points_higher = engine._expected_points(lower, higher)
    assert points_higher - points_lower == pytest.approx(2.0)
    assert engine._expected_points(higher, lower) == pytest.approx((points_higher, points_lower))


def test_quoted_spreads_do_not_favor_a_side_in_opening_round(engine, monkeypatch):
    samples = 2000
    monkeypatch.setattr('backend.playoff_engine.random.gauss', lambda mean, _sigma: mean)
    for conference in (engine.east_teams, engine.west_teams):
        for a, b in ((1, 8), (2, 7), (3, 6), (4, 5)):
            team1, team2 = conference[a], conference[b]
            spread = engine.calculate_advanced_odds(team1, team2)['spread']
            quantiles = iter((i + .5) / samples for i in range(samples))
            monkeypatch.setattr('backend.playoff_engine.random.random', lambda: next(quantiles))
            outcomes = {1: 0, -1: 0, 0: 0}
            for _ in range(samples):
                game = engine.generate_game_stats(team1, team2)
                margin = game['t1_pts'] - game['t2_pts'] + spread['team1_spread']
                outcomes[(margin > 0) - (margin < 0)] += 1
            best_return = (max(outcomes[1], outcomes[-1]) * spread['odds'] + outcomes[0]) / samples
            assert best_return < 1, (team1, team2, best_return)
