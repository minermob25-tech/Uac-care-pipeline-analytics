# UAC Care Transition Efficiency and Placement Outcome Analytics

Project 1 of my Machine Learning internship at Unified Mentor.

An analytics project on the U.S. Department of Health and Human Services Unaccompanied Alien Children (UAC) program. Instead of only counting children in custody, it measures how efficiently they move through the pipeline: CBP custody, then HHS care, then sponsor placement.

## Key features
- Transfer efficiency, discharge effectiveness, throughput, backlog growth and outcome stability KPIs
- Backlog, stagnation and sudden-drop detection
- Weekday vs weekend and month-over-month analysis
- Interactive Streamlit dashboard with date ranges, previous-period comparison, alert thresholds and a health score

## What is in here

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit dashboard |
| `analysis.py` | Runs the EDA, saves figures and `reports/findings.md` |
| `src/data.py` | Loads and cleans the csv |
| `src/metrics.py` | KPIs, backlog / stagnation / drop detection |
| `src/charts.py` | Plotly charts used by the dashboard |
| `reports/` | Research paper, executive summary, generated findings and figures |
| `data/` | Put the dataset csv here |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate       
pip install -r requirements.txt
```

Copy the dataset csv into `data/`.

## Run

```bash
python analysis.py               
streamlit run app.py             
```

You can also upload the csv from the dashboard sidebar.

## Metric definitions

- Transfer efficiency = children transferred out of CBP / children in CBP custody
- Discharge effectiveness = children discharged from HHS / children in HHS care
- Pipeline throughput = discharges / apprehensions over a rolling window
- Backlog accumulation rate = apprehensions minus discharges per day (7-day average by default)
- Outcome stability = 1 / (1 + coefficient of variation) of discharge effectiveness over 30 days, so values near 1 mean steady outcomes

## Notes and limits

The dataset has daily counts only, with no case-level records. Ratios are therefore
proxies for speed, not true length-of-stay measures. Weekend rows are sometimes empty in
the source data, which affects weekday vs weekend comparisons.
