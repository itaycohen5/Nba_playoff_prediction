"""Explicit offline download with bounded timeout/retry and atomic output."""
from nba_api.stats.endpoints import leaguegamelog
from pipeline_utils import BASE, atomic_csv, nba_request, require_columns


def main():
    frame = nba_request(leaguegamelog.LeagueGameLog, season="2025-26", season_type_all_star="Regular Season")
    require_columns(frame, ["GAME_ID", "GAME_DATE", "TEAM_ID", "TEAM_NAME", "MATCHUP", "WL"])
    if frame.duplicated(["GAME_ID", "TEAM_ID"]).any():
        raise ValueError("Duplicate team/game rows")
    atomic_csv(frame, BASE / "data" / "nba_real_games.csv")
    print("Regular-season games saved.")


if __name__ == "__main__":
    main()
