"""Prepare past-only differential features for optional offline model training."""
import numpy as np
import pandas as pd
from pipeline_utils import BASE, atomic_csv, require_columns

FEATURES = [
    "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA",
    "FT_PCT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS", "PLUS_MINUS",
]


def main():
    gamelog = pd.read_csv(BASE / "data" / "nba_real_games.csv", dtype={"GAME_ID": str})
    require_columns(gamelog, ["GAME_ID", "TEAM_ID", "GAME_DATE", "WL", "MATCHUP"] + FEATURES)
    if gamelog.duplicated(["GAME_ID", "TEAM_ID"]).any():
        raise ValueError("Duplicate team/game rows")
    if not gamelog["WL"].isin(["W", "L"]).all() or gamelog["MATCHUP"].isna().any():
        raise ValueError("Invalid outcomes or matchups")
    gamelog["GAME_DATE"] = pd.to_datetime(gamelog["GAME_DATE"], errors="raise")
    if gamelog["GAME_DATE"].isna().any():
        raise ValueError("Missing game dates")
    gamelog = gamelog.sort_values(["GAME_DATE", "GAME_ID", "TEAM_ID"]).reset_index(drop=True)
    gamelog[FEATURES] = gamelog[FEATURES].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(gamelog[FEATURES].to_numpy()).all():
        raise ValueError("Non-finite raw statistics")
    possessions = gamelog["FGA"] + .44 * gamelog["FTA"] - gamelog["OREB"] + gamelog["TOV"]
    if (possessions <= 0).any():
        raise ValueError("Invalid possessions")
    gamelog["OFF_RATING"] = gamelog["PTS"] / possessions * 100
    gamelog["WIN"] = gamelog["WL"].map({"W": 1, "L": 0})
    features = FEATURES + ["OFF_RATING"]
    perf = gamelog[["GAME_ID", "GAME_DATE", "TEAM_ID", "WIN"]].copy()
    perf["IS_HOME"] = gamelog["MATCHUP"].str.contains("vs.", regex=False).astype(int)
    if not gamelog["MATCHUP"].str.contains("vs.", regex=False).where(
            perf["IS_HOME"].eq(1), gamelog["MATCHUP"].str.contains("@", regex=False)).all():
        raise ValueError("Cannot identify home/away matchup")
    perf["REST_DAYS"] = gamelog.groupby("TEAM_ID")["GAME_DATE"].diff().dt.days.sub(1).fillna(3)
    if (perf["REST_DAYS"] < 0).any():
        raise ValueError("Multiple games for one team on the same date")
    prior_wins = gamelog.groupby("TEAM_ID")["WIN"].transform(lambda wins: wins.cumsum().shift(1))
    prior_games = gamelog.groupby("TEAM_ID").cumcount()
    perf["CUM_WIN_PCT"] = prior_wins.div(prior_games.replace(0, np.nan)).fillna(.5)
    for col in features:
        perf["ROLL_" + col] = gamelog.groupby("TEAM_ID")[col].transform(
            lambda values: values.shift(1).rolling(window=5, min_periods=1).mean())
    games = perf.groupby("GAME_ID")
    if not games.size().eq(2).all() or not games["GAME_DATE"].nunique().eq(1).all():
        raise ValueError("Expected two teams on the same date for each game")
    if not games["WIN"].sum().eq(1).all():
        raise ValueError("Inconsistent paired outcomes")
    home_counts = games["IS_HOME"].sum()
    if home_counts.gt(1).any():
        raise ValueError("Multiple home teams for one game")
    # Neutral games appear as two away rows. Keep them in team history but
    # exclude them from training labels that require a designated home team.
    home_games = home_counts[home_counts.eq(1)].index
    training_games = perf[perf["GAME_ID"].isin(home_games)]
    home = training_games[training_games["IS_HOME"].eq(1)]
    away = training_games[training_games["IS_HOME"].eq(0)]
    matchups = home.merge(away, on="GAME_ID", suffixes=("_HOME", "_AWAY"), validate="one_to_one")
    result = matchups[["GAME_ID"]].copy()
    result["GAME_DATE"] = matchups["GAME_DATE_HOME"]
    result["WIN"] = matchups["WIN_HOME"]
    result["REST_DIFF"] = matchups["REST_DAYS_HOME"] - matchups["REST_DAYS_AWAY"]
    result["CUM_WIN_PCT_DIFF"] = matchups["CUM_WIN_PCT_HOME"] - matchups["CUM_WIN_PCT_AWAY"]
    for col in features:
        result[col + "_DIFF"] = matchups["ROLL_" + col + "_HOME"] - matchups["ROLL_" + col + "_AWAY"]
    result = result.dropna().sort_values(["GAME_DATE", "GAME_ID"])
    if result.empty:
        raise ValueError("No complete historical features")
    atomic_csv(result, BASE / "data" / "clean_real_nba_games.csv")
    print(f"Excluded {home_counts.eq(0).sum()} neutral games from home-win training labels.")
    print(f"Saved {len(result)} chronological feature rows.")


if __name__ == "__main__":
    main()
