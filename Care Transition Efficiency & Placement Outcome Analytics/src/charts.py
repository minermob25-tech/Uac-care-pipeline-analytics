import plotly.graph_objects as go
from plotly.subplots import make_subplots


def pipeline_sankey(df):
    inflow = df["apprehended"].sum()
    moved = df["transferred"].sum()
    placed = df["discharged"].sum()
    labels = ["Apprehended", "CBP custody", "HHS care", "Sponsor placement"]
    fig = go.Figure(
        go.Sankey(
            node=dict(label=labels, pad=20, thickness=18),
            link=dict(source=[0, 1, 2], target=[1, 2, 3], value=[inflow, moved, placed]),
        )
    )
    fig.update_layout(title="Total flow through the pipeline (selected dates)", height=380)
    return fig


def load_over_time(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["cbp_custody"], name="In CBP custody"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["hhs_care"], name="In HHS care"))
    fig.update_layout(title="Children in care by stage", yaxis_title="Children", height=380)
    return fig


def daily_flows(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["apprehended"], name="Apprehended"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["transferred"], name="Transferred to HHS"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["discharged"], name="Discharged"))
    fig.update_layout(title="Daily movement", yaxis_title="Children per day", height=380)
    return fig


def ratio_line(df, col, title, threshold=None, smooth=True):
    use = col + "_roll" if smooth and (col + "_roll") in df else col
    fig = go.Figure(go.Scatter(x=df["date"], y=df[use], name=title))
    if threshold is not None:
        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"threshold {threshold:.0%}",
        )
    fig.update_layout(title=title, height=330, yaxis_tickformat=".0%")
    return fig


def throughput_line(df, threshold=None):
    fig = go.Figure(go.Scatter(x=df["date"], y=df["throughput"], name="Throughput"))
    if threshold is not None:
        fig.add_hline(y=threshold, line_dash="dash", line_color="red")
    fig.update_layout(
        title="Pipeline throughput (7-day exits / entries)", height=330, yaxis_tickformat=".0%"
    )
    return fig


def backlog_chart(df, runs=None):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=df["date"], y=df["backlog_rate"], name="Net flow (7-day avg)"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df["date"], y=df["backlog"], name="Cumulative backlog", line=dict(dash="dot")),
        secondary_y=True,
    )
    if runs is not None and len(runs):
        for _, r in runs.iterrows():
            fig.add_vrect(x0=r["start"], x1=r["end"], fillcolor="orange", opacity=0.15, line_width=0)
    fig.add_hline(y=0, line_color="gray")
    fig.update_layout(title="Intake minus discharges", height=400)
    fig.update_yaxes(title_text="Children per day", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative children", secondary_y=True)
    return fig


def weekday_bar(table, col, title):
    fig = go.Figure(go.Bar(x=table.index, y=table[col]))
    fig.update_layout(title=title, height=320)
    return fig


def monthly_bar(m, col, title):
    fig = go.Figure(go.Bar(x=m.index, y=m[col]))
    fig.update_layout(title=title, height=320)
    return fig


def stability_line(df, drops=None):
    fig = go.Figure(go.Scatter(x=df["date"], y=df["stability"], name="Stability score"))
    if drops is not None and len(drops):
        fig.add_trace(
            go.Scatter(
                x=drops["date"],
                y=[df["stability"].min()] * len(drops),
                mode="markers",
                marker=dict(color="red", size=6),
                name="Sharp weekly drop",
            )
        )
    fig.update_layout(title="Outcome stability (30-day rolling)", height=330, yaxis_range=[0, 1])
    return fig


def health_gauge(score):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": " / 100"},
            title={"text": "Pipeline health"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#0f766e"},
                "steps": [
                    {"range": [0, 50], "color": "rgba(220,38,38,0.25)"},
                    {"range": [50, 75], "color": "rgba(245,158,11,0.25)"},
                    {"range": [75, 100], "color": "rgba(34,197,94,0.25)"},
                ],
            },
        )
    )
    fig.update_layout(height=260, margin=dict(t=60, b=10, l=20, r=20))
    return fig


def heatmap(grid, title, fmt=".0f"):
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    fig = go.Figure(
        go.Heatmap(
            z=grid.values,
            x=[names[m - 1] for m in grid.columns],
            y=grid.index,
            colorscale="Teal",
            hoverongaps=False,
            hovertemplate="%{y}, %{x}: %{z:" + fmt + "}<extra></extra>",
        )
    )
    fig.update_layout(title=title, height=360)
    return fig


def lag_chart(lag):
    fig = go.Figure(go.Scatter(x=lag["lag_days"], y=lag["correlation"], mode="lines+markers"))
    if lag["correlation"].notna().any():
        best = lag.loc[lag["correlation"].idxmax()]
        fig.add_vline(x=best["lag_days"], line_dash="dash", line_color="red")
    fig.update_layout(
        title="Transfers vs discharges: correlation by delay",
        xaxis_title="Days after transfer",
        yaxis_title="Correlation",
        height=340,
    )
    return fig


def compare_bars(cur, prev, labels):
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Selected period", x=labels, y=cur))
    fig.add_trace(go.Bar(name="Previous period", x=labels, y=prev))
    fig.update_layout(barmode="group", height=320, yaxis_tickformat=".1%", title="Selected vs previous period")
    return fig