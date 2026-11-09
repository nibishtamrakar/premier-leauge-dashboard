from pathlib import Path
from typing import Any
import pandas as pd

# create output directory
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

# Three Complete Premier League Seasons
seasons = {
    "2023-2024": "2324",
    "2024-2025": "2425",
    "2025-2026": "2526",
}

columns = [
    "Date",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "FTR",
    "HS",
    "AS",
    "HST",
    "AST",
]

frames = []

# Download data for each season
for season, season_id in seasons.items():
    url = (
        "https://www.football-data.co.uk/"f"mmz4281/{season_id}/E0.csv"
    )
    
    print(f"Downloading {season}...")
    df = pd.read_csv(url, low_memory=False)
    df = df[columns].copy()
    df["Season"] = season
    frames.append(df)
    
# Combine all seasons into a single dataframe
matches = pd.concat(frames, ignore_index=True)

# Clean missing and invalid data
matches["Date"] = pd.to_datetime(matches["Date"], dayfirst=True, errors="coerce")

numeric = ["FTHG", "FTAG", "HS", "AS", "HST", "AST"]
for col in numeric:
    matches[col] = pd.to_numeric(matches[col], errors="coerce")
    
matches = matches.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"])
matches = matches[matches["FTR"].isin(["H", "A", "D"])].copy()

# remove duplicates
matches = matches.drop_duplicates(subset=["Season", "Date", "HomeTeam", "AwayTeam"])

matches["FTHG"] = matches["FTHG"].astype(int)
matches["FTAG"] = matches["FTAG"].astype(int)

# Adding Some useful columns
matches["TotalGoals"] = matches["FTHG"] + matches["FTAG"]

matches["Result"] = matches["FTR"].map({
    "H": "HomeWin",
    "A": "AwayWin", 
    "D": "Draw"
})

# Save the match level data
matches.to_csv(DATA_DIR / "premier_league_matches.csv", index=False)

# Convert each match into two team performance records
home = pd.DataFrame({
    "Season": matches["Season"],
    "Date": matches["Date"],
    "Team": matches["HomeTeam"],
    "Opponent": matches["AwayTeam"],
    "Venue": "Home",
    "GoalsFor": matches["FTHG"],
    "GoalsAgainst": matches["FTAG"],
    "Shots": matches["HS"],
    "ShotsOnTarget": matches["HST"],
    "Outcome": matches["FTR"].map({"H": "Win", "A": "Loss", "D": "Draw"})
})

away = pd.DataFrame({
    "Season": matches["Season"],
    "Date": matches["Date"],
    "Team": matches["AwayTeam"],
    "Opponent": matches["HomeTeam"],
    "Venue": "Away",
    "GoalsFor": matches["FTAG"],
    "GoalsAgainst": matches["FTHG"],
    "Shots": matches["AS"],
    "ShotsOnTarget": matches["AST"],
    "Outcome": matches["FTR"].map({"H": "Loss", "A": "Win", "D": "Draw"})
})

teams = pd.concat([home, away], ignore_index=True)

teams["Points"] = teams["Outcome"].map({"Win": 3, "Draw": 1, "Loss": 0})
teams["GoalDifference"] = teams["GoalsFor"] - teams["GoalsAgainst"]
teams = teams.sort_values(
    ["Season", "Date", "Team"]
).reset_index(drop=True)

teams.to_csv(DATA_DIR / "premier_league_teams.csv", index=False)

# Print Quality Checks and Debugs
print("Dataset preparation complete!")
print("Total Matches: ", len(matches))
print("Team-match records: ", len(teams))
print("Seasons: ", matches["Season"].unique())
print("Missing goals: ", matches[["FTHG", "FTAG"]].isna().sum().sum())

for season, group in matches.groupby("Season"):
    unique_teams = set(group["HomeTeam"]) | set(group["AwayTeam"])

    print(
        season,
        "matches:", len(group),
        "teams:", len(unique_teams)
    )

