import joblib
import pandas as pd
import random
from pathlib import Path

# הגדרת נתיבי בסיס לפרויקט
BASE = Path(__file__).resolve().parent.parent
model_path = BASE / 'models' / 'nba_prediction_model.pkl'
raw_data_path = BASE / 'data' / 'nba_real_games.csv'

# תיקון נתיבים אוטומטי למקרה שהקובץ לא יושב בתיקיית scripts
if not model_path.exists():
    BASE = Path(__file__).resolve().parent
    model_path = BASE / 'models' / 'nba_prediction_model.pkl'
    raw_data_path = BASE / 'data' / 'nba_real_games.csv'

if not model_path.exists() or not raw_data_path.exists():
    raise FileNotFoundError("ודא שהרצת את fetch, etl, ו-train לפני הרצת הסימולציה!")

# טעינת המודל החכם ונתוני העונה הסדירה
model = joblib.load(model_path)
raw_games = pd.read_csv(raw_data_path)
raw_games['GAME_DATE'] = pd.to_datetime(raw_games['GAME_DATE'])

# רשימת השדות הבסיסיים לחישוב ממוצעים
features = [
    'MIN', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT',
    'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB',
    'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS', 'PLUS_MINUS'
]

# חלוקת הקבוצות לקונפרנסים לצורך בניית הפלייאוף
EASTERN_CONFERENCE = [
    "Boston Celtics", "Milwaukee Bucks", "Philadelphia 76ers", "Cleveland Cavaliers",
    "New York Knicks", "Brooklyn Nets", "Atlanta Hawks", "Miami Heat",
    "Toronto Raptors", "Chicago Bulls", "Indiana Pacers", "Washington Wizards",
    "Orlando Magic", "Charlotte Hornets", "Detroit Pistons"
]

# מאגר הנתונים הדינמי של הקבוצות
team_db = {}

print("Initializing dynamic team statuses from end of regular season...")
for team_name in raw_games['TEAM_NAME'].unique():
    team_df = raw_games[raw_games['TEAM_NAME'] == team_name].sort_values(by='GAME_DATE')
    last_games = team_df.tail(5)

    # חישוב אחוז ניצחונות כולל בעונה הסדירה
    total_games = len(team_df)
    wins = len(team_df[team_df['WL'] == 'W'])
    cum_win_pct = wins / total_games if total_games > 0 else 0.5

    # ממוצעים נעים של 5 המשחקים האחרונים
    stats = {f'ROLL_{col}': last_games[col].mean() for col in features}
    stats['CUM_WIN_PCT'] = cum_win_pct

    # חישוב מדד היעילות ההתקפית ל-5 המשחקים האחרונים
    possessions = last_games['FGA'] + 0.44 * last_games['FTA'] - last_games['OREB'] + last_games['TOV']
    possessions = possessions.replace(0, 100)
    off_rating = (last_games['PTS'] / possessions) * 100
    stats['ROLL_OFF_RATING'] = off_rating.mean()

    team_db[team_name] = stats

# דירוג אוטומטי של הקבוצות לפלייאוף לפי אחוז הניצחונות שלהן (כולל התיקון)
east_sorted = [t for t in sorted(team_db.keys(), key=lambda k: team_db[k]['CUM_WIN_PCT'], reverse=True) if
               any(ec in t for ec in EASTERN_CONFERENCE)]
west_sorted = [t for t in sorted(team_db.keys(), key=lambda k: team_db[k]['CUM_WIN_PCT'], reverse=True) if
               t not in east_sorted]

# בניית המילונים החל מאינדקס 1 להתאמה מלאה למבנה הבראקט
east_teams = {i + 1: east_sorted[i] for i in range(min(8, len(east_sorted)))}
west_teams = {i + 1: west_sorted[i] for i in range(min(8, len(west_sorted)))}
if len(east_teams) != 8 or len(west_teams) != 8:
    raise ValueError("The playoff simulation requires eight teams per conference")
east_seeds = {team: seed for seed, team in east_teams.items()}
west_seeds = {team: seed for seed, team in west_teams.items()}


def simulate_game(home_team, away_team):
    """סימולציית משחק בודד מבוססת הסתברות אקראית משוקללת"""
    home_stats = team_db[home_team]
    away_stats = team_db[away_team]

    # יצירת וקטור ההפרשים המדויק (בית פחות חוץ) לפיו המודל אומן
    input_data = {
        'REST_DIFF': [0],
        'CUM_WIN_PCT_DIFF': [home_stats['CUM_WIN_PCT'] - away_stats['CUM_WIN_PCT']],
        'MIN_DIFF': [home_stats['ROLL_MIN'] - away_stats['ROLL_MIN']],
        'FGM_DIFF': [home_stats['ROLL_FGM'] - away_stats['ROLL_FGM']],
        'FGA_DIFF': [home_stats['ROLL_FGA'] - away_stats['ROLL_FGA']],
        'FG_PCT_DIFF': [home_stats['ROLL_FG_PCT'] - away_stats['ROLL_FG_PCT']],
        'FG3M_DIFF': [home_stats['ROLL_FG3M'] - away_stats['ROLL_FG3M']],
        'FG3A_DIFF': [home_stats['ROLL_FG3A'] - away_stats['ROLL_FG3A']],
        'FG3_PCT_DIFF': [home_stats['ROLL_FG3_PCT'] - away_stats['ROLL_FG3_PCT']],
        'FTM_DIFF': [home_stats['ROLL_FTM'] - away_stats['ROLL_FTM']],
        'FTA_DIFF': [home_stats['ROLL_FTA'] - away_stats['ROLL_FTA']],
        'FT_PCT_DIFF': [home_stats['ROLL_FT_PCT'] - away_stats['ROLL_FT_PCT']],
        'OREB_DIFF': [home_stats['ROLL_OREB'] - away_stats['ROLL_OREB']],
        'DREB_DIFF': [home_stats['ROLL_DREB'] - away_stats['ROLL_DREB']],
        'REB_DIFF': [home_stats['ROLL_REB'] - away_stats['ROLL_REB']],
        'AST_DIFF': [home_stats['ROLL_AST'] - away_stats['ROLL_AST']],
        'STL_DIFF': [home_stats['ROLL_STL'] - away_stats['ROLL_STL']],
        'BLK_DIFF': [home_stats['ROLL_BLK'] - away_stats['ROLL_BLK']],
        'TOV_DIFF': [home_stats['ROLL_TOV'] - away_stats['ROLL_TOV']],
        'PF_DIFF': [home_stats['ROLL_PF'] - away_stats['ROLL_PF']],
        'PTS_DIFF': [home_stats['ROLL_PTS'] - away_stats['ROLL_PTS']],
        'PLUS_MINUS_DIFF': [home_stats['ROLL_PLUS_MINUS'] - away_stats['ROLL_PLUS_MINUS']],
        'OFF_RATING_DIFF': [home_stats['ROLL_OFF_RATING'] - away_stats['ROLL_OFF_RATING']]
    }

    X_game = pd.DataFrame(input_data)

    # שימוש ב-predict_proba לקבלת אחוזי הסיכוי לכל תוצאה
    probabilities = model.predict_proba(X_game)[0]
    home_win_prob = probabilities[1]

    # אלמנט הרנדומליות
    if random.random() < home_win_prob:
        return home_team
    else:
        return away_team


def simulate_series(team1, team2):
    """סימולציית סדרת פלייאוף הטוב מ-7"""
    # In conference rounds, home court follows the original seeds even
    # when a lower seed reaches this round through an upset.
    for seeds in (east_seeds, west_seeds):
        if team1 in seeds and team2 in seeds and seeds[team1] > seeds[team2]:
            team1, team2 = team2, team1
            break
    team1_wins = 0
    team2_wins = 0

    for game_num in range(1, 8):
        if game_num in [1, 2, 5, 7]:
            winner = simulate_game(home_team=team1, away_team=team2)
        else:
            winner = simulate_game(home_team=team2, away_team=team1)

        if winner == team1:
            team1_wins += 1
        else:
            team2_wins += 1

        if team1_wins == 4:
            print(f"   🏀 {team1} מנצחת את הסדרה {team1_wins}-{team2_wins} מול {team2}")
            return team1
        if team2_wins == 4:
            print(f"   🏀 {team2} מנצחת את הסדרה {team2_wins}-{team1_wins} מול {team1}")
            return team2


# --- הרצת טורניר הפלייאוף המלא ---

print("\n🏀 --- FIRST ROUND PLAYOFFS --- 🏀")
print("[EAST]")
e_semis_1 = simulate_series(east_teams[1], east_teams[8])
e_semis_2 = simulate_series(east_teams[4], east_teams[5])
e_semis_3 = simulate_series(east_teams[2], east_teams[7])
e_semis_4 = simulate_series(east_teams[3], east_teams[6])

print("\n[WEST]")
w_semis_1 = simulate_series(west_teams[1], west_teams[8])
w_semis_2 = simulate_series(west_teams[4], west_teams[5])
w_semis_3 = simulate_series(west_teams[2], west_teams[7])
w_semis_4 = simulate_series(west_teams[3], west_teams[6])

print("\n🏀 --- CONFERENCE SEMIFINALS --- 🏀")
print("[EAST]")
east_finals_1 = simulate_series(e_semis_1, e_semis_2)
east_finals_2 = simulate_series(e_semis_3, e_semis_4)

print("\n[WEST]")
west_finals_1 = simulate_series(w_semis_1, w_semis_2)
west_finals_2 = simulate_series(w_semis_3, w_semis_4)

print("\n🏀 --- CONFERENCE FINALS --- 🏀")
print("[EAST FINALS]")
east_champion = simulate_series(east_finals_1, east_finals_2)

print("\n[WEST FINALS]")
west_champion = simulate_series(west_finals_1, west_finals_2)

print("\n🏆 ⭐ --- NBA FINALS --- ⭐ 🏆")
if team_db[east_champion]['CUM_WIN_PCT'] >= team_db[west_champion]['CUM_WIN_PCT']:
    nba_champion = simulate_series(east_champion, west_champion)
else:
    nba_champion = simulate_series(west_champion, east_champion)

print("\n" + "=" * 60)
print(f"🎉 THE 2026 NBA CHAMPION IS: {nba_champion} 🎉")
print("=" * 60)
