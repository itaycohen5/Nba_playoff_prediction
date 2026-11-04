"""Explicit offline workflow; downloading is opt-in."""
import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="Download NBA data before processing")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    scripts = ["etl_pipeline.py", "train_model.py"]
    if args.fetch:
        scripts = ["fetch_nba_data.py", "fetch_team_stats.py"] + scripts
    for script in scripts:
        subprocess.run([sys.executable, str(root / "scripts" / script)], cwd=root, check=True, timeout=600)


if __name__ == "__main__":
    main()
