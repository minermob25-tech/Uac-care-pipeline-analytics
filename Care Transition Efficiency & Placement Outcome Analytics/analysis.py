"""Runs the full exploratory analysis and writes figures plus a findings file.

Usage:  python analysis.py data/your_file.csv
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import metrics
from src.data import load_data

OUT = Path("reports")
FIG = OUT / "figures"


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=130)
    plt.close(fig)


def main(path):
    FIG.mkdir(parents=True, exist_ok=True)
    df = metrics.add_metrics(load_data(path))
    kpi = metrics.kpi_summary(df)
    month = metrics.monthly_table(df)
    week = metrics.weekend_split(df)
    wk = metrics.weekday_table(df)
    backlog = metrics.backlog_periods(df)
    stag, cutoff = metrics.stagnation_periods(df)
    drops = metrics.sudden_drops(df)

    # figures
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["date"], df["cbp_custody"], label="CBP custody")
    ax.plot(df["date"], df["hhs_care"], label="HHS care")
    ax.set_title("Children in care by stage")
    ax.legend()
    save(fig, "load_by_stage.png")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["date"], df["apprehended"].rolling(7).mean(), label="Apprehended")
    ax.plot(df["date"], df["transferred"].rolling(7).mean(), label="Transferred")
    ax.plot(df["date"], df["discharged"].rolling(7).mean(), label="Discharged")
    ax.set_title("Daily flows (7-day mean)")
    ax.legend()
    save(fig, "daily_flows.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(df["date"], df["transfer_eff_roll"])
    axes[0].set_title("Transfer efficiency (7-day mean)")
    axes[1].plot(df["date"], df["discharge_eff_roll"])
    axes[1].set_title("Discharge effectiveness (7-day mean)")
    save(fig, "efficiency_ratios.png")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["date"], df["backlog_rate"])
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title("Net flow: intake minus discharges (7-day mean)")
    save(fig, "backlog_rate.png")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(wk.index, wk["discharged"])
    ax.set_title("Average discharges by weekday")
    plt.setp(ax.get_xticklabels(), rotation=30)
    save(fig, "weekday_discharges.png")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(month.index, month["discharged"], width=20)
    ax.set_title("Discharges per month")
    save(fig, "monthly_discharges.png")

    # findings file
    lines = [
        "# Findings",
        "",
        f"Period: {df['date'].min():%d %b %Y} to {df['date'].max():%d %b %Y} ({len(df)} daily records)",
        "",
        "## KPIs",
        f"- Transfer efficiency (mean): {kpi['transfer_eff']:.2%}",
        f"- Discharge effectiveness (mean): {kpi['discharge_eff']:.3%}",
        f"- Pipeline throughput (total exits / total entries): {kpi['throughput']:.1%}",
        f"- Backlog accumulation (mean net children per day): {kpi['backlog_rate']:+.1f}",
        f"- Outcome stability (mean): {kpi['stability']:.2f}",
        "",
        "## Weekday vs weekend (daily averages)",
        week.round(4).to_markdown(),
        "",
        "## Backlog stretches (14+ days of intake above discharges)",
        backlog.to_markdown(index=False) if len(backlog) else "None found.",
        "",
        f"## Stagnation (discharge effectiveness at or under {cutoff:.3%} for 7+ days)",
        stag.to_markdown(index=False) if len(stag) else "None found.",
        "",
        f"## Sharp weekly drops in discharges (25%+): {len(drops)} days flagged",
        "",
        "## Best and worst months by discharges",
        f"- Best: {month['discharged'].idxmax():%b %Y} ({month['discharged'].max():,.0f})",
        f"- Worst: {month['discharged'].idxmin():%b %Y} ({month['discharged'].min():,.0f})",
    ]
    (OUT / "findings.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote reports/findings.md and figures in reports/figures/")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        csvs = sorted(Path("data").glob("*.csv"))
        if not csvs:
            sys.exit("No csv found. Pass a path or place one in data/")
        target = csvs[0]
    main(target)
