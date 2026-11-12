import numpy as np
import pandas as pd


def add_metrics(df, window=7):
    """Adds the ratio columns and rolling versions used by the dashboard."""
    out = df.copy()

    out["transfer_eff"] = out["transferred"] / out["cbp_custody"].replace(0, np.nan)
    out["discharge_eff"] = out["discharged"] / out["hhs_care"].replace(0, np.nan)

    out["total_load"] = out["cbp_custody"] + out["hhs_care"]
    out["net_flow"] = out["apprehended"] - out["discharged"]
    out["backlog"] = out["net_flow"].cumsum()
    out["backlog_rate"] = out["net_flow"].rolling(window, min_periods=1).mean()

    entries = out["apprehended"].rolling(window, min_periods=1).sum()
    exits = out["discharged"].rolling(window, min_periods=1).sum()
    out["throughput"] = exits / entries.replace(0, np.nan)

    out["transfer_eff_roll"] = out["transfer_eff"].rolling(window, min_periods=1).mean()
    out["discharge_eff_roll"] = out["discharge_eff"].rolling(window, min_periods=1).mean()
    out["discharged_roll"] = out["discharged"].rolling(window, min_periods=1).sum()

    # stability: 1 when discharge effectiveness barely moves, lower when it swings
    roll = out["discharge_eff"].rolling(30, min_periods=10)
    cv = roll.std() / roll.mean().replace(0, np.nan)
    out["stability"] = 1 / (1 + cv)

    out["weekday"] = out["date"].dt.day_name()
    out["is_weekend"] = out["date"].dt.dayofweek >= 5
    return out


def kpi_summary(df):
    total_in = df["apprehended"].sum()
    total_out = df["discharged"].sum()
    return {
        "transfer_eff": df["transfer_eff"].mean(),
        "discharge_eff": df["discharge_eff"].mean(),
        "throughput": total_out / total_in if total_in else np.nan,
        "backlog_rate": df["net_flow"].mean(),
        "stability": df["stability"].mean(),
    }


def weekday_table(df):
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return (
        df.groupby("weekday")[["transfer_eff", "discharge_eff", "transferred", "discharged"]]
        .mean()
        .reindex(order)
    )


def weekend_split(df):
    return (
        df.groupby("is_weekend")[["transfer_eff", "discharge_eff", "transferred", "discharged"]]
        .mean()
        .rename(index={False: "Weekday", True: "Weekend"})
    )


def monthly_table(df):
    m = df.set_index("date").resample("MS").agg(
        {
            "apprehended": "sum",
            "transferred": "sum",
            "discharged": "sum",
            "transfer_eff": "mean",
            "discharge_eff": "mean",
            "hhs_care": "mean",
            "cbp_custody": "mean",
        }
    )
    m["throughput"] = m["discharged"] / m["apprehended"].replace(0, np.nan)
    m["discharged_mom"] = m["discharged"].pct_change()
    m["discharge_eff_mom"] = m["discharge_eff"].pct_change()
    return m


def find_runs(mask, dates, min_days):
    """Consecutive stretches where mask is True and that last at least min_days rows."""
    mask = pd.Series(np.asarray(mask, dtype=bool))
    dates = pd.Series(np.asarray(dates))
    group = (mask != mask.shift()).cumsum()
    rows = []
    for _, chunk in mask.groupby(group):
        if chunk.iloc[0] and len(chunk) >= min_days:
            rows.append(
                {
                    "start": dates.iloc[chunk.index[0]],
                    "end": dates.iloc[chunk.index[-1]],
                    "days": len(chunk),
                }
            )
    return pd.DataFrame(rows, columns=["start", "end", "days"])


def backlog_periods(df, min_days=14):
    """Stretches where intake kept beating discharges on a rolling basis."""
    return find_runs(df["backlog_rate"] > 0, df["date"], min_days)


def stagnation_periods(df, quantile=0.2, min_days=7):
    """Stretches where discharge effectiveness stayed in its lowest quantile."""
    cutoff = df["discharge_eff"].quantile(quantile)
    runs = find_runs(df["discharge_eff"] <= cutoff, df["date"], min_days)
    return runs, cutoff


def sudden_drops(df, lookback=7, drop_pct=0.25):
    """Days where weekly discharges fell sharply versus a week earlier."""
    change = df["discharged_roll"].pct_change(lookback)
    flagged = change <= -drop_pct
    hits = df.loc[flagged, ["date", "discharged_roll"]].copy()
    hits["change"] = change[flagged]
    return hits.reset_index(drop=True)


def health_score(kpi, limits):
    """0-100 score: how close each KPI is to its target, capped at the target."""
    parts = [
        min(kpi["transfer_eff"] / limits["transfer"], 1.0),
        min(kpi["discharge_eff"] / limits["discharge"], 1.0),
        min(kpi["throughput"] / limits["throughput"], 1.0),
        kpi["stability"],
    ]
    return 100 * float(np.nanmean(parts))


def lag_correlation(df, max_lag=45):
    """Correlation between weekly transfers and discharges some days later.
    The peak gives a rough idea of how long children stay in HHS care."""
    a = df["transferred"].rolling(7, min_periods=3).mean()
    b = df["discharged"].rolling(7, min_periods=3).mean()
    rows = [(lag, a.corr(b.shift(-lag))) for lag in range(0, max_lag + 1)]
    return pd.DataFrame(rows, columns=["lag_days", "correlation"])


def weekday_month_grid(df, col):
    grid = df.assign(month=df["date"].dt.month).pivot_table(
        index="weekday", columns="month", values=col, aggfunc="mean"
    )
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return grid.reindex(order)


def make_insights(df):
    notes = []
    m = monthly_table(df)
    if len(m) > 1:
        notes.append(
            f"Discharges were highest in {m['discharged'].idxmax():%B %Y} "
            f"({m['discharged'].max():,.0f}) and lowest in {m['discharged'].idxmin():%B %Y} "
            f"({m['discharged'].min():,.0f})."
        )

    net = df["net_flow"].mean()
    if net < 0:
        notes.append(
            f"Discharges exceeded new apprehensions by {abs(net):.0f} children per day on average, "
            "so the system was draining rather than filling up."
        )
    else:
        notes.append(f"Apprehensions exceeded discharges by {net:.0f} children per day on average.")

    runs = backlog_periods(df)
    if len(runs):
        longest = runs.sort_values("days", ascending=False).iloc[0]
        notes.append(
            f"There were {len(runs)} backlog stretches of two weeks or more. The longest ran "
            f"{longest['days']} days, from {longest['start']:%d %b %Y} to {longest['end']:%d %b %Y}."
        )
    else:
        notes.append("No backlog stretch lasted two weeks or more in this range.")

    split = weekend_split(df)
    if len(split) == 2:
        wd, we = split.loc["Weekday", "discharged"], split.loc["Weekend", "discharged"]
        notes.append(
            f"Average daily discharges are {wd:.0f} on weekdays and {we:.0f} on weekends. "
            "Weekend rows may include catch-up reporting, so treat this gap with care."
        )

    drops = sudden_drops(df)
    if len(drops):
        worst = drops.sort_values("change").iloc[0]
        notes.append(
            f"{len(drops)} days showed a weekly discharge drop of 25% or more. The sharpest was "
            f"{worst['change']:.0%} around {worst['date']:%d %b %Y}."
        )

    lag = lag_correlation(df)
    if lag["correlation"].notna().any():
        best = lag.loc[lag["correlation"].idxmax()]
        notes.append(
            f"Discharges track transfers most closely after about {int(best['lag_days'])} days "
            f"(correlation {best['correlation']:.2f}), a rough sign of typical time in HHS care."
        )
    return notes