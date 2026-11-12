from datetime import timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src import charts, metrics
from src.data import load_data

st.set_page_config(page_title="UAC Care Pipeline Analytics", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem;}
    h1 {font-weight: 700; letter-spacing: -0.5px;}
    div[data-testid="stMetric"] {border-radius: 10px;}
    .status-row {padding: 6px 0; border-bottom: 1px solid rgba(128,128,128,0.25);}
    </style>
    """,
    unsafe_allow_html=True,
)

DATA_DIR = Path(__file__).parent / "data"


@st.cache_data(show_spinner=False)
def get_data(source):
    return load_data(source)


st.title("UAC Care Transition Efficiency and Placement Outcomes")
st.caption("How children move from CBP custody to HHS care to sponsor placement.")

# ---------------- sidebar ----------------
st.sidebar.header("Data")
upload = st.sidebar.file_uploader("Upload the UAC csv", type="csv")
source = upload
if source is None:
    found = sorted(DATA_DIR.glob("*.csv"))
    if found:
        source = found[0]
        st.sidebar.caption(f"Using data/{found[0].name}")
if source is None:
    st.info("Upload the dataset in the sidebar, or drop the csv into the data folder.")
    st.stop()

try:
    raw = get_data(source)
except ValueError as err:
    st.error(str(err))
    st.stop()

first, last = raw["date"].min(), raw["date"].max()

st.sidebar.header("Date range")
preset = st.sidebar.selectbox(
    "Quick range",
    ["All data", "Last 12 months", "Last 6 months", "Last 90 days", "Last 30 days", "Custom"],
)
days_back = {"Last 12 months": 365, "Last 6 months": 182, "Last 90 days": 90, "Last 30 days": 30}
if preset == "All data":
    start, end = first, last
elif preset in days_back:
    start, end = max(first, last - timedelta(days=days_back[preset])), last
else:
    picked = st.sidebar.date_input(
        "Custom range", (first.date(), last.date()), min_value=first.date(), max_value=last.date()
    )
    if not isinstance(picked, (tuple, list)) or len(picked) != 2:
        st.warning("Pick both a start and an end date.")
        st.stop()
    start, end = pd.Timestamp(picked[0]), pd.Timestamp(picked[1])

st.sidebar.header("View options")
window = st.sidebar.select_slider("Smoothing window (days)", options=[1, 3, 7, 14, 30], value=7)
smooth = st.sidebar.toggle("Use smoothed ratios", value=True)
compare = st.sidebar.toggle("Compare with previous period", value=True)
show_transfer = st.sidebar.checkbox("Transfer efficiency", True)
show_discharge = st.sidebar.checkbox("Discharge effectiveness", True)
show_throughput = st.sidebar.checkbox("Pipeline throughput", True)

st.sidebar.header("Alert thresholds")
t_transfer = st.sidebar.slider("Min transfer efficiency", 0.0, 1.0, 0.60, 0.01)
t_discharge = st.sidebar.slider("Min discharge effectiveness", 0.0, 0.10, 0.015, 0.0025, format="%.4f")
t_throughput = st.sidebar.slider("Min throughput", 0.0, 2.0, 1.0, 0.05)
t_backlog = st.sidebar.number_input("Max net daily backlog growth", value=50, step=10)

# ---------------- data for the chosen range ----------------
full = metrics.add_metrics(raw, window=window)
df = full[(full["date"] >= start) & (full["date"] <= end)].copy()
if df.empty:
    st.warning("No rows in that range.")
    st.stop()
df["backlog"] = df["net_flow"].cumsum()

kpi = metrics.kpi_summary(df)

prev_kpi = None
if compare:
    span = end - start
    p_end = start - timedelta(days=1)
    p_start = p_end - span
    prev = full[(full["date"] >= p_start) & (full["date"] <= p_end)]
    if len(prev) > 5:
        prev_kpi = metrics.kpi_summary(prev)


def delta_pts(key):
    if prev_kpi is None:
        return None
    return f"{(kpi[key] - prev_kpi[key]) * 100:+.2f} pts"


# ---------------- KPI cards ----------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Transfer efficiency", f"{kpi['transfer_eff']:.1%}", delta_pts("transfer_eff"),
          help="Children transferred out of CBP divided by children in CBP custody.", border=True)
c2.metric("Discharge effectiveness", f"{kpi['discharge_eff']:.2%}", delta_pts("discharge_eff"),
          help="Children discharged to sponsors divided by children in HHS care.", border=True)
c3.metric("Pipeline throughput", f"{kpi['throughput']:.1%}", delta_pts("throughput"),
          help="Total discharges divided by total apprehensions. Above 100% means the system is draining.", border=True)
c4.metric("Backlog growth / day", f"{kpi['backlog_rate']:+.1f}",
          None if prev_kpi is None else f"{kpi['backlog_rate'] - prev_kpi['backlog_rate']:+.1f}",
          delta_color="inverse",
          help="Apprehensions minus discharges per day. Positive means a backlog is building.", border=True)
c5.metric("Outcome stability", f"{kpi['stability']:.2f}",
          None if prev_kpi is None else f"{kpi['stability'] - prev_kpi['stability']:+.2f}",
          help="Closer to 1 means discharge performance is steady from week to week.", border=True)

# ---------------- health score and alerts ----------------
limits = {"transfer": t_transfer, "discharge": t_discharge, "throughput": t_throughput}
score = metrics.health_score(kpi, limits)

recent = df.tail(window)
checks = [
    ("Transfer efficiency", f"{recent['transfer_eff'].mean():.1%}", recent["transfer_eff"].mean() >= t_transfer, f"min {t_transfer:.0%}"),
    ("Discharge effectiveness", f"{recent['discharge_eff'].mean():.2%}", recent["discharge_eff"].mean() >= t_discharge, f"min {t_discharge:.2%}"),
    ("Throughput", f"{recent['throughput'].iloc[-1]:.1%}", recent["throughput"].iloc[-1] >= t_throughput, f"min {t_throughput:.0%}"),
    ("Backlog growth", f"{recent['net_flow'].mean():+.0f} / day", recent["net_flow"].mean() <= t_backlog, f"max {t_backlog:+d} / day"),
]

g_col, a_col = st.columns([1, 2])
g_col.plotly_chart(charts.health_gauge(score), width="stretch")
with a_col:
    st.subheader(f"Alert status, last {window} days to {df['date'].max():%d %b %Y}")
    for name, value, ok, rule in checks:
        if ok:
            flag = "<span style='color:#16a34a'>Within threshold</span>"
        else:
            flag = "<span style='color:#dc2626'>Needs attention</span>"
        st.markdown(
            f"<div class='status-row'><b>{name}</b>: {value} ({rule}) &nbsp; {flag}</div>",
            unsafe_allow_html=True,
        )
    st.caption("Health score: average of how close the four KPIs are to their targets (stability counts as is).")

# ---------------- tabs ----------------
tabs = st.tabs(["Pipeline flow", "Efficiency", "Bottlenecks", "Outcome trends", "Delay analysis", "Insights", "Data"])
t_flow, t_eff, t_bot, t_out, t_lag, t_ins, t_data = tabs

with t_flow:
    left, right = st.columns(2)
    left.plotly_chart(charts.pipeline_sankey(df), width="stretch")
    right.plotly_chart(charts.load_over_time(df), width="stretch")
    st.plotly_chart(charts.daily_flows(df), width="stretch")

with t_eff:
    if show_transfer:
        st.plotly_chart(charts.ratio_line(df, "transfer_eff", "Transfer efficiency", t_transfer, smooth), width="stretch")
    if show_discharge:
        st.plotly_chart(charts.ratio_line(df, "discharge_eff", "Discharge effectiveness", t_discharge, smooth), width="stretch")
    if show_throughput:
        st.plotly_chart(charts.throughput_line(df, t_throughput), width="stretch")
    if prev_kpi is not None:
        keys = ["transfer_eff", "discharge_eff", "throughput"]
        st.plotly_chart(
            charts.compare_bars([kpi[k] for k in keys], [prev_kpi[k] for k in keys],
                                ["Transfer eff.", "Discharge eff.", "Throughput"]),
            width="stretch",
        )
    st.subheader("Weekday vs weekend")
    wk = metrics.weekday_table(df)
    a, b = st.columns(2)
    a.plotly_chart(charts.weekday_bar(wk, "transferred", "Average transfers by weekday"), width="stretch")
    b.plotly_chart(charts.weekday_bar(wk, "discharged", "Average discharges by weekday"), width="stretch")
    st.dataframe(metrics.weekend_split(df).style.format("{:.3f}"), width="stretch")

with t_bot:
    min_run = st.slider("Minimum length of a backlog stretch (days)", 7, 60, 14)
    runs = metrics.backlog_periods(df, min_days=min_run)
    st.plotly_chart(charts.backlog_chart(df, runs), width="stretch")
    st.caption("Shaded areas are stretches where intake stayed above discharges.")
    if len(runs):
        st.dataframe(runs, width="stretch", hide_index=True)
    else:
        st.write("No backlog stretches of that length in this range.")
    st.subheader("Stagnation")
    stag, cutoff = metrics.stagnation_periods(df)
    st.write(f"Stretches of a week or more where discharge effectiveness stayed at or under {cutoff:.2%} (lowest 20% of days).")
    if len(stag):
        st.dataframe(stag, width="stretch", hide_index=True)
    else:
        st.write("None found.")

with t_out:
    m = metrics.monthly_table(df)
    a, b = st.columns(2)
    a.plotly_chart(charts.monthly_bar(m, "discharged", "Discharges per month"), width="stretch")
    b.plotly_chart(charts.monthly_bar(m, "throughput", "Monthly throughput"), width="stretch")
    drop_pct = st.slider("Flag weekly discharge drops larger than", 0.1, 0.6, 0.25, 0.05, format="%.2f")
    drops = metrics.sudden_drops(df, drop_pct=drop_pct)
    st.plotly_chart(charts.stability_line(df, drops), width="stretch")
    st.write(f"{len(drops)} days flagged.")
    if len(drops):
        st.dataframe(drops, width="stretch", hide_index=True)
    st.subheader("Seasonality")
    metric_choice = st.radio("Heatmap metric", ["discharged", "transferred", "discharge_eff"], horizontal=True)
    fmt = ".3f" if metric_choice == "discharge_eff" else ".0f"
    st.plotly_chart(
        charts.heatmap(metrics.weekday_month_grid(df, metric_choice), f"Average {metric_choice} by weekday and month", fmt),
        width="stretch",
    )

with t_lag:
    st.write("This estimates how long transfers take to turn into discharges by finding the delay "
             "at which the two series line up best.")
    lag = metrics.lag_correlation(df)
    st.plotly_chart(charts.lag_chart(lag), width="stretch")
    st.caption("Daily counts only, so this is an approximation, not a true length-of-stay.")

with t_ins:
    st.subheader("Key findings for the selected range")
    for note in metrics.make_insights(df):
        st.markdown(f"- {note}")

with t_data:
    st.dataframe(df, width="stretch", hide_index=True)
    st.download_button(
        "Download filtered data with metrics (csv)",
        df.to_csv(index=False).encode("utf-8"),
        file_name="uac_pipeline_metrics.csv",
        mime="text/csv",
    )