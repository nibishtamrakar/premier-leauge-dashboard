"""Premier League prototype dashboard: run with `python app.py`."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dcc, html

DATA_PATH = Path(__file__).resolve().parent / "data" / "premier_league_teams.csv"
if not DATA_PATH.exists():
    raise FileNotFoundError(
        f"Dataset not found: {DATA_PATH}\n"
        "Place app.py in your project root and run prepare_data.py first."
    )

matches = pd.read_csv(DATA_PATH)
required = {"Season", "Team", "Outcome", "GoalsFor", "GoalsAgainst", "Points"}
missing = required - set(matches.columns)
if missing:
    raise ValueError(f"Missing required CSV columns: {sorted(missing)}")

matches = matches.dropna(subset=list(required)).copy()
for col in ("GoalsFor", "GoalsAgainst", "Points"):
    matches[col] = pd.to_numeric(matches[col], errors="coerce")
matches = matches.dropna(subset=["GoalsFor", "GoalsAgainst", "Points"])
matches = matches[matches["Outcome"].isin(["Win", "Draw", "Loss"])].copy()
if matches.empty:
    raise ValueError("There are no valid team-match records in the CSV.")

for result in ("Win", "Draw", "Loss"):
    matches[result + "Count"] = (matches["Outcome"] == result).astype(int)

stats = (matches.groupby(["Season", "Team"], as_index=False)
         .agg(Played=("Outcome", "size"), Wins=("WinCount", "sum"),
              Draws=("DrawCount", "sum"), Losses=("LossCount", "sum"),
              GoalsFor=("GoalsFor", "sum"),
              GoalsAgainst=("GoalsAgainst", "sum"),
              Points=("Points", "sum")))
stats["GoalDifference"] = stats["GoalsFor"] - stats["GoalsAgainst"]
seasons = sorted(stats["Season"].astype(str).unique(), reverse=True)

dash_app = Dash(__name__)
app = dash_app.server  # Vercel loads app:app as a Flask WSGI application
server = app  # Optional alias for existing integrations
dash_app.title = "Premier League | Prototype Dashboard"

PAGE = {"fontFamily": "Arial, sans-serif", "background": "#f4f7fb",
        "minHeight": "100vh", "padding": "24px", "color": "#172b4d"}
CARD = {"background": "white", "borderRadius": "12px", "padding": "18px",
        "boxShadow": "0 2px 9px rgba(15,30,55,.07)"}
BLUE, GRAY = "#0072B2", "#AEB8C4"  # Okabe-Ito blue and neutral gray
# Okabe-Ito-derived categorical palette, with labels as a redundant cue.
OUTCOME_COLORS = {"Win": "#0072B2", "Draw": "#E69F00", "Loss": "#CC79A7"}


def metric_card(label, value):
    return html.Div([
        html.Div(label, style={"color": "#526276", "fontSize": "13px"}),
        html.H2(f"{value:,}", style={"margin": "7px 0 0"}),
    ], style={**CARD, "flex": "1", "minWidth": "145px"})


dash_app.layout = html.Div([
    html.H1("Premier League Performance Dashboard", style={"marginBottom": "4px"}),
    html.P("Compare points, attacking and defensive performance, and match outcomes.",
           style={"color": "#526276"}),
    html.Div([
        html.Div([
            html.Label("Season", htmlFor="season-filter"),
            dcc.Dropdown(id="season-filter", value=seasons[0], clearable=False,
                         options=[{"label": s, "value": s} for s in seasons],
                         style={"width": "205px"}),
        ]),
        html.Div([
            html.Label("Team (or select from a chart)", htmlFor="team-filter"),
            dcc.Dropdown(id="team-filter", placeholder="All teams", clearable=True,
                         style={"width": "255px"}),
        ]),
        html.Button("Reset team", id="reset-button", n_clicks=0,
                    style={"padding": "11px 18px", "border": "0", "borderRadius": "7px",
                           "color": "white", "background": "#172b4d", "cursor": "pointer"}),
    ], style={**CARD, "display": "flex", "gap": "18px", "flexWrap": "wrap",
              "alignItems": "end", "marginBottom": "18px"}),
    html.H2(id="selection-title", style={"fontSize": "20px"}),
    html.Div(id="summary-cards", style={"display": "flex", "flexWrap": "wrap",
                                         "gap": "14px", "marginBottom": "18px"}),
    html.Div([
        html.H3("1. Which teams earned the most points?"),
        html.P("Bar length encodes points. Click a bar to select a team.",
               style={"color": "#526276"}),
        dcc.Graph(id="points-chart"),
    ], style={**CARD, "marginBottom": "18px"}),
    html.Div([
        html.Div([
            html.H3("2. How do goals scored and conceded relate to wins?"),
            html.P("X = goals scored; Y = goals conceded; bubble area = wins. Blue diamond = selected team; gray circles = other teams. Click a bubble.",
                   style={"color": "#526276"}),
            dcc.Graph(id="goals-chart"),
        ], style=CARD),
        html.Div([
            html.H3("3. What proportion of outcomes are wins, draws, or losses?"),
            html.P("Blue = wins; amber = draws; purple = losses. Each slice is labeled with its percentage.",
                   style={"color": "#526276"}),
            dcc.Graph(id="outcomes-chart"),
        ], style=CARD),
    ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(320px, 1fr))",
              "gap": "18px"}),
], style=PAGE)


@dash_app.callback(Output("team-filter", "options"), Input("season-filter", "value"))
def teams_for_season(season):
    names = sorted(stats.loc[stats["Season"] == season, "Team"].tolist())
    return [{"label": t, "value": t} for t in names]


# The dropdown is the ONLY source of selected-team state. Chart clicks change it.
# When the season changes, an old team's selection is cleared automatically.
@dash_app.callback(
    Output("team-filter", "value"),
    Input("points-chart", "clickData"),
    Input("goals-chart", "clickData"),
    Input("season-filter", "value"),
    Input("reset-button", "n_clicks"),
    State("team-filter", "value"),
    prevent_initial_call=True,
)
def select_from_chart(bar_click, scatter_click, season, reset_clicks, previous):
    source = ctx.triggered_id
    if source in ("season-filter", "reset-button"):
        return None
    data = bar_click if source == "points-chart" else scatter_click if source == "goals-chart" else None
    if not data or not data.get("points"):
        return previous
    custom = data["points"][0].get("customdata")
    if not custom:
        return previous
    team = str(custom[0])
    valid = set(stats.loc[stats["Season"] == season, "Team"])
    return team if team in valid else previous


@dash_app.callback(
    Output("points-chart", "figure"),
    Output("goals-chart", "figure"),
    Output("outcomes-chart", "figure"),
    Output("selection-title", "children"),
    Output("summary-cards", "children"),
    Input("season-filter", "value"),
    Input("team-filter", "value"),
)
def update_dashboard(season, selected_team):
    subset = stats.loc[stats["Season"] == season].copy()
    subset = subset.sort_values(["Points", "GoalDifference", "GoalsFor"],
                                ascending=False).reset_index(drop=True)
    if selected_team not in set(subset["Team"]):
        selected_team = None
    # Put the selected team FIRST, followed by other teams in league order.
    # A single bar trace with per-bar colors avoids Plotly grouping the
    # selected team at the end when a categorical color is applied.
    if selected_team:
        first = subset.loc[subset["Team"] == selected_team]
        rest = subset.loc[subset["Team"] != selected_team]
        display_data = pd.concat([first, rest], ignore_index=True)
    else:
        display_data = subset.copy()

    display_data["BarColor"] = display_data["Team"].apply(
        lambda t: BLUE if not selected_team or t == selected_team else GRAY
    )
    bar_custom = display_data[
        ["Team", "Played", "Wins", "Draws", "Losses", "GoalDifference"]
    ].to_numpy()
    bar = go.Figure(go.Bar(
        x=display_data["Team"],
        y=display_data["Points"],
        customdata=bar_custom,
        marker=dict(color=display_data["BarColor"], line=dict(width=0)),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>Points: %{y}"
            "<br>Played: %{customdata[1]} | Wins: %{customdata[2]}"
            "<br>Draws: %{customdata[3]} | Losses: %{customdata[4]}"
            "<br>Goal difference: %{customdata[5]}<extra></extra>"
        ),
    ))
    bar.update_layout(
        showlegend=False, height=420,
        margin=dict(l=35, r=15, t=15, b=95),
        xaxis=dict(
            title="Club", tickangle=-40,
            categoryorder="array", categoryarray=display_data["Team"].tolist(),
        ),
        yaxis_title="League points",
        clickmode="event+select",
    )

    # Accessible encodings: neutral gray circles for the comparison group;
    # the selected team is a blue DIAMOND with a dark outline. Shape and
    # outline preserve the distinction for users with color-vision deficiency.
    # Bubble area (not radius) encodes wins, with a common scale for all teams.
    max_wins = max(1, int(subset["Wins"].max()))
    sizeref = 2.0 * max_wins / (38 ** 2)

    scatter = go.Figure()
    other = subset if selected_team is None else subset.loc[
        subset["Team"] != selected_team
    ]
    selected = subset.loc[subset["Team"] == selected_team] if selected_team else subset.iloc[0:0]

    def add_bubbles(frame, name, fill, symbol, border, border_width):
        if frame.empty:
            return
        custom = frame[["Team", "Wins", "Points", "Played"]].to_numpy()
        scatter.add_trace(go.Scatter(
            x=frame["GoalsFor"], y=frame["GoalsAgainst"],
            mode="markers", name=name,
            customdata=custom,
            marker=dict(
                size=frame["Wins"].clip(lower=1), sizemode="area",
                sizeref=sizeref, sizemin=7,
                color=fill, symbol=symbol,
                opacity=0.9,
                line=dict(color=border, width=border_width),
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>Goals scored: %{x}"
                "<br>Goals conceded: %{y}<br>Wins: %{customdata[1]}"
                "<br>Points: %{customdata[2]}"
                "<br>Matches played: %{customdata[3]}<extra></extra>"
            ),
        ))

    add_bubbles(other, "Other teams" if selected_team else "Teams",
                GRAY, "circle", "#526276", 1)
    add_bubbles(selected, "Selected team", BLUE, "diamond", "#172B4D", 2)

    scatter.update_layout(
        height=420, margin=dict(l=55, r=15, t=15, b=55),
        xaxis_title="Goals scored", yaxis_title="Goals conceded",
        legend=dict(orientation="h", y=1.1, x=0),
        showlegend=True, clickmode="event+select",
    )

    team_matches = matches.loc[matches["Season"] == season]
    if selected_team:
        team_matches = team_matches.loc[team_matches["Team"] == selected_team]
    counts = team_matches["Outcome"].value_counts().reindex(
        ["Win", "Draw", "Loss"], fill_value=0)
    outcomes = pd.DataFrame({"Outcome": counts.index, "Count": counts.values})
    # Explicit per-slice colors prevent a single-color donut. Labels and
    # percentages make the data readable without depending on color alone.
    pie = go.Figure(go.Pie(
        labels=outcomes["Outcome"].tolist(),
        values=outcomes["Count"].tolist(),
        hole=0.52,
        sort=False,
        marker=dict(
            colors=[OUTCOME_COLORS[outcome] for outcome in outcomes["Outcome"]],
            line=dict(color="white", width=3),
        ),
        textinfo="label+percent",
        textposition="outside",
        hovertemplate=(
            "<b>%{label}</b><br>Team-match outcomes: %{value}"
            "<br>Share: %{percent}<extra></extra>"
        ),
    ))
    pie.update_layout(
        height=420, margin=dict(l=55, r=55, t=15, b=35),
        showlegend=True, legend_title_text="Outcome",
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.1),
    )

    focus = subset if selected_team is None else subset.loc[subset["Team"] == selected_team]
    cards = [
        metric_card("Teams selected", focus["Team"].nunique()),
        metric_card("Points earned", int(focus["Points"].sum())),
        metric_card("Matches won", int(focus["Wins"].sum())),
        metric_card("Goals scored", int(focus["GoalsFor"].sum())),
    ]
    heading = f"{selected_team or 'All teams'} — {season}"
    return bar, scatter, pie, heading, cards


if __name__ == "__main__":
    dash_app.run(debug=True)
    
