"""Offline statistical scenario simulator; independent of the optional ML pipeline."""
import csv
import math
import random
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

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

    def _expected_points(self, t1, t2, series_history=None):
        if t1 == t2 or t1 not in self.team_db or t2 not in self.team_db:
            raise ValueError("Unknown or identical matchup teams")
        a, b = self.team_db[t1], self.team_db[t2]
        pace = (a["PACE"] + b["PACE"]) / 2
        p1 = (a["OFF_RATING"] + b["DEF_RATING"]) / 2 * pace / 100
        p2 = (b["OFF_RATING"] + a["DEF_RATING"]) / 2 * pace / 100
        history = list(series_history or [])
        # Custom scenario: team 1 hosts games 1, 2, 5 and 7.
        home_advantage = 2.0 if len(history) + 1 in (1, 2, 5, 7) else -2.0
        momentum = 0.0
        if history:
            if history[-1].winner not in (t1, t2):
                raise ValueError("History contains a different matchup")
            momentum = 1.0 if history[-1].winner == t1 else -1.0
        return max(1.0, p1 + (home_advantage + momentum) / 2), max(1.0, p2 - (home_advantage + momentum) / 2)

    def _game_probability(self, t1, t2, series_history=None):
        p1, p2 = self._expected_points(t1, t2, series_history)
        exponent = max(-60, min(60, -(p1 - p2) / 8))
        return max(.05, min(.95, 1 / (1 + math.exp(exponent))))

    def generate_game_stats(self, t1, t2, series_history=None):
        p1, p2 = self._expected_points(t1, t2, series_history)
        t1_wins = random.random() < self._game_probability(t1, t2, series_history)
        total = max(2, round(random.gauss(p1 + p2, 14)))
        # Explicit winner uses the same probability as the quoted market.
        # Bounded margin avoids an unbounded tie retry loop.
        margin = max(1, min(total - 1, round(abs(random.gauss(abs(p1 - p2), 8)))))
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
