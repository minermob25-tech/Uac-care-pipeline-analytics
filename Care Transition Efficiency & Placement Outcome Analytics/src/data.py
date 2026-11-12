import pandas as pd

NUMERIC_COLS = ["apprehended", "cbp_custody", "transferred", "hhs_care", "discharged"]


def _match_column(name):
    low = name.strip().lower()
    if low == "date":
        return "date"
    if "apprehended" in low:
        return "apprehended"
    if "transferred" in low:
        return "transferred"
    if "discharged" in low:
        return "discharged"
    if "cbp" in low and "custody" in low:
        return "cbp_custody"
    if "hhs" in low and "care" in low:
        return "hhs_care"
    return None


def load_data(source):
    """Read the raw csv (path or uploaded file) and return a clean daily frame."""
    raw = pd.read_csv(source)

    mapping = {}
    for col in raw.columns:
        short = _match_column(col)
        if short and short not in mapping.values():
            mapping[col] = short
    df = raw.rename(columns=mapping)

    missing = [c for c in ["date"] + NUMERIC_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Could not find these columns in the file: {missing}")

    df = df[["date"] + NUMERIC_COLS].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    for col in NUMERIC_COLS:
        # some exports store numbers as text with thousands separators
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False).str.strip(),
            errors="coerce",
        )

    df = (
        df.dropna(subset=NUMERIC_COLS, how="all")
        .drop_duplicates(subset="date")
        .sort_values("date")
        .reset_index(drop=True)
    )
    return df
