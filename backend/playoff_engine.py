"""Offline statistical scenario simulator; independent of the optional ML pipeline."""
import csv
import math
import random
from functools import lru_cache
from pathlib import Path
from statistics import NormalDist
from types import SimpleNamespace

SCORE_MARGIN = NormalDist(sigma=12)

WEST_SEEDING = [
    "Oklahoma City Thunder", "San Antonio Spurs", "Denver Nuggets", "Los Angeles Lakers",
    "Houston Rockets", "Minnesota Timberwolves", "Portland Trail Blazers", "Phoenix Suns",
]
EAST_SEEDING = [
    "Detroit Pistons", "Boston Celtics", "Cleveland Cavaliers", "New York Knicks",
    "Atlanta Hawks", "Toronto Raptors", "Philadelphia 76ers", "Orlando Magic",
]


class PlayoffEngine:
    def __init__(self, data_path=None):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.data_path = Path(data_path or self.base_dir / "data") / "team_stats.csv"
        self.team_db = {}
        self.west_teams = dict(enumerate(WEST_SEEDING, 1))
        self.east_teams = dict(enumerate(EAST_SEEDING, 1))
        self.seeds = {team: (conference, seed)
                      for conference, teams in (("west", self.west_teams), ("east", self.east_teams))
                      for seed, team in teams.items()}
        self.data_source = "Season CSV; statistical simulator; custom playoff scenario; defensive rating estimated"
        self.load_and_clean_data()

    def load_and_clean_data(self):
        required = {"TEAM_NAME", "GP", "W_PCT", "PTS", "PLUS_MINUS", "FGA", "FTA", "OREB", "TOV", "REB"}
        loaded = {}
        try:
            with self.data_path.open(encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                if not required.issubset(reader.fieldnames or []):
                    raise ValueError("Missing required season statistics columns")
                for row in reader:
                    team = (row["TEAM_NAME"] or "").strip()
                    values = {key: float(row[key]) for key in required - {"TEAM_NAME"}}
                    if not team or team in loaded or not all(math.isfinite(v) for v in values.values()):
                        raise ValueError("Invalid or duplicate team statistics")
                    if values["GP"] <= 0 or not 0 <= values["W_PCT"] <= 1:
                        raise ValueError(f"Invalid games or win percentage: {team}")
                    if any(values[key] < 0 for key in ("PTS", "FGA", "FTA", "OREB", "TOV", "REB")):
                        raise ValueError(f"Negative season statistics: {team}")
                    possessions = values["FGA"] + .44 * values["FTA"] - values["OREB"] + values["TOV"]
                    opponent_points = values["PTS"] - values["PLUS_MINUS"]
                    if possessions <= 0 or opponent_points <= 0 or values["PTS"] <= 0:
                        raise ValueError(f"Invalid possessions or points: {team}")
                    loaded[team] = {
                        "CUM_WIN_PCT": values["W_PCT"],
                        "OFF_RATING": values["PTS"] / possessions * 100,
                        "DEF_RATING": opponent_points / possessions * 100,
                        "REB_PER_GAME": values["REB"] / values["GP"],
                        "PACE": possessions / values["GP"],
                    }
                    if not all(math.isfinite(value) for value in loaded[team].values()):
                        raise ValueError(f"Non-finite derived statistics: {team}")
                    if not (1 <= loaded[team]["PACE"] <= 250
                            and 1 <= loaded[team]["OFF_RATING"] <= 300
                            and 1 <= loaded[team]["DEF_RATING"] <= 300
                            and 0 <= loaded[team]["REB_PER_GAME"] <= 150):
                        raise ValueError(f"Out-of-range derived statistics: {team}")
            missing = (set(WEST_SEEDING) | set(EAST_SEEDING)) - loaded.keys()
            if missing:
                raise ValueError("Missing scenario teams: " + ", ".join(sorted(missing)))
        except (OSError, ValueError, TypeError, OverflowError, KeyError, csv.Error) as exc:
            raise RuntimeError("Cannot load team_stats.csv; rebuild offline season statistics. " + str(exc)) from exc
        self.team_db = loaded

    def home_team(self, t1, t2, game_number):
        if t1 == t2 or t1 not in self.team_db or t2 not in self.team_db:
            raise ValueError("Unknown or identical matchup teams")
        seed1, seed2 = self.seeds.get(t1), self.seeds.get(t2)
        if seed1 and seed2 and seed1[0] == seed2[0]:
            team1_has_home_court = seed1[1] < seed2[1]
        else:
            # Finals home court follows regular-season record, with a stable tie break.
            team1_has_home_court = (self.team_db[t1]["CUM_WIN_PCT"], t1) > (self.team_db[t2]["CUM_WIN_PCT"], t2)
        return t1 if team1_has_home_court == (game_number in (1, 2, 5, 7)) else t2

    def _expected_points(self, t1, t2, series_history=None):
        history = list(series_history or [])
        home = self.home_team(t1, t2, len(history) + 1)
        a, b = self.team_db[t1], self.team_db[t2]
        pace = (a["PACE"] + b["PACE"]) / 2
        p1 = (a["OFF_RATING"] + b["DEF_RATING"]) / 2 * pace / 100
        p2 = (b["OFF_RATING"] + a["DEF_RATING"]) / 2 * pace / 100
        home_advantage = 2.0 if home == t1 else -2.0
        momentum = 0.0
        if history:
            if history[-1].winner not in (t1, t2):
                raise ValueError("History contains a different matchup")
            momentum = 1.0 if history[-1].winner == t1 else -1.0
        return max(1.0, p1 + (home_advantage + momentum) / 2), max(1.0, p2 - (home_advantage + momentum) / 2)

    def _game_probability(self, t1, t2, series_history=None):
        p1, p2 = self._expected_points(t1, t2, series_history)
        return SCORE_MARGIN.cdf(p1 - p2)

    def generate_game_stats(self, t1, t2, series_history=None):
        p1, p2 = self._expected_points(t1, t2, series_history)
        draw = random.random()
        expected_margin = p1 - p2
        t1_wins = draw < SCORE_MARGIN.cdf(expected_margin)
        # One draw fixes both winner and margin. Sampling the winner independently
        # of the margin made one side of the spread systematically too profitable.
        quantile = min(1 - 1e-12, max(1e-12, 1 - draw))
        sampled_margin = expected_margin + SCORE_MARGIN.inv_cdf(quantile)
        total = max(2, round(random.gauss(p1 + p2, 14)))
        # A positive integer margin avoids ties and keeps both scores nonnegative.
        margin = max(1, min(total - 1, round(abs(sampled_margin))))
        loser_points = max(0, (total - margin) // 2)
        winner_points = loser_points + margin
        score1, score2 = (winner_points, loser_points) if t1_wins else (loser_points, winner_points)
        return {
            "winner": t1 if t1_wins else t2, "t1_pts": score1, "t2_pts": score2,
            "t1_rebounds": max(0, round(random.gauss(self.team_db[t1]["REB_PER_GAME"], 4))),
            "t2_rebounds": max(0, round(random.gauss(self.team_db[t2]["REB_PER_GAME"], 4))),
            "total_points": score1 + score2,
        }

    def calculate_advanced_odds(self, t1, t2, series_history=None):
        history = list(series_history or [])
        probability = self._game_probability(t1, t2, history)
        wins1 = sum(g.winner == t1 for g in history)
        wins2 = sum(g.winner == t2 for g in history)
        if len(history) > 7 or max(wins1, wins2) >= 4 or wins1 + wins2 != len(history):
            raise ValueError("Series has finished or history is invalid")

        @lru_cache(None)
        def series_probability(w1, w2, last_winner):
            if w1 >= 4:
                return 1.0
            if w2 >= 4:
                return 0.0
            synthetic = [SimpleNamespace(winner=t1)] * (w1 + w2)
            if synthetic:
                synthetic[-1] = SimpleNamespace(winner=last_winner)
            p = self._game_probability(t1, t2, synthetic)
            return p * series_probability(w1 + 1, w2, t1) + (1 - p) * series_probability(w1, w2 + 1, t2)

        series_p = series_probability(wins1, wins2, history[-1].winner if history else "")

        def price(p):
            return round(max(1.01, .95 / max(.000001, p)), 2)

        p1, p2 = self._expected_points(t1, t2, history)
        spread = round((p1 - p2) * 2) / 2
        return {
            "moneyline": {t1: price(probability), t2: price(1 - probability)},
            "series_winner": {t1: price(series_p), t2: price(1 - series_p)},
            "spread": {"team1_spread": -spread, "team2_spread": spread, "odds": 1.90},
            "over_under_points": {"line": round((p1 + p2) * 2) / 2, "over_odds": 1.90, "under_odds": 1.90},
        }
