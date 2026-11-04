"""Explicit offline download; does not run when imported."""
from nba_api.stats.endpoints import leaguedashteamstats
from pipeline_utils import BASE, atomic_csv, nba_request, require_columns


def main():
    frame = nba_request(leaguedashteamstats.LeagueDashTeamStats, season="2025-26")
    require_columns(frame, ["TEAM_NAME", "GP", "PTS", "W_PCT", "FGA", "FTA", "OREB", "TOV", "REB", "PLUS_MINUS"])
    if frame["TEAM_NAME"].duplicated().any() or len(frame) != 30:
        raise ValueError("Expected 30 unique NBA teams")
    atomic_csv(frame, BASE / "data" / "team_stats.csv")
    print("Season statistics saved.")


if __name__ == "__main__":
    main()
