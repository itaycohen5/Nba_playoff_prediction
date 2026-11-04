"""Optional offline ML experiment. The web application uses its own statistical simulator."""
import os
import tempfile
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from pipeline_utils import BASE, require_columns

FEATURES = [
    "REST_DIFF", "CUM_WIN_PCT_DIFF", "MIN_DIFF", "FGM_DIFF", "FGA_DIFF", "FG_PCT_DIFF",
    "FG3M_DIFF", "FG3A_DIFF", "FG3_PCT_DIFF", "FTM_DIFF", "FTA_DIFF", "FT_PCT_DIFF",
    "OREB_DIFF", "DREB_DIFF", "REB_DIFF", "AST_DIFF", "STL_DIFF", "BLK_DIFF", "TOV_DIFF",
    "PF_DIFF", "PTS_DIFF", "PLUS_MINUS_DIFF", "OFF_RATING_DIFF",
]


def main():
    frame = pd.read_csv(BASE / "data" / "clean_real_nba_games.csv", dtype={"GAME_ID": str})
    require_columns(frame, ["GAME_DATE", "GAME_ID", "WIN"] + FEATURES)
    frame["GAME_DATE"] = pd.to_datetime(frame["GAME_DATE"], errors="raise")
    if frame["GAME_DATE"].isna().any() or frame["GAME_ID"].duplicated().any():
        raise ValueError("Missing dates or duplicate games; rerun ETL")
    if not frame["WIN"].isin([0, 1]).all() or not np.isfinite(frame[FEATURES].to_numpy()).all():
        raise ValueError("Invalid labels or features")
    frame = frame.sort_values(["GAME_DATE", "GAME_ID"])
    dates = frame["GAME_DATE"].drop_duplicates().sort_values()
    if len(dates) < 2:
        raise ValueError("Need multiple dates for temporal validation")
    cutoff = dates.iloc[max(1, min(len(dates) - 1, int(len(dates) * .8)))]
    training = frame["GAME_DATE"] < cutoff
    x_train, x_test = frame.loc[training, FEATURES], frame.loc[~training, FEATURES]
    y_train, y_test = frame.loc[training, "WIN"], frame.loc[~training, "WIN"]
    if y_train.nunique() < 2 or x_test.empty:
        raise ValueError("Insufficient temporal train/test data")
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, random_state=42))
    model.fit(x_train, y_train)
    print(f"Future-period accuracy: {accuracy_score(y_test, model.predict(x_test)):.3f}")
    print(f"Future-period log loss: {log_loss(y_test, model.predict_proba(x_test), labels=[0, 1]):.3f}")
    target = BASE / "models" / "nba_prediction_model.pkl"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="nba-model-", suffix=".tmp", dir=target.parent)
    os.close(fd)
    try:
        joblib.dump(model, temporary)
        os.replace(temporary, target)
    finally:
        from pathlib import Path
        Path(temporary).unlink(missing_ok=True)
    print("Saved the temporally evaluated model. This model is not used by the web simulator.")


if __name__ == "__main__":
    main()
