"""Utility to combine and plot dPCR CSV results.

This module exposes a single function `analyze_files` which accepts an
iterable of (filename, filelike) pairs (such as what Streamlit's
`file_uploader` returns) and returns a matplotlib Figure and a pivot
DataFrame with counts per sample-pattern.

Notes / assumptions:
- Each CSV is read with pandas.read_csv(skiprows=3) to match the
  original script's behavior.
- The code looks for these columns in the CSV (original German headers):
  "Senf w  Haselnuss", "Mandel Sellerie", "Pistache Cashew",
  "Lupine Walnuss" and expects a sample name to be derived from the
  filename with `os.path.splitext(filename)[0]` and then taking the
  second part after splitting on "_` (this keeps parity with the
  original script). If column names differ, the function will raise
  a ValueError with a helpful message.
"""

from typing import Iterable, Tuple, IO
import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def analyze_files(files: Iterable[Tuple[str, IO]]):
    """Read multiple CSV-like files, combine them and return (pivot_df, values_df).

    Args:
        files: iterable of (filename, filelike) pairs. filelike can be a
               path-like object, an open file, or an in-memory buffer
               (e.g. BytesIO) accepted by pandas.read_csv.

    Returns:
        (pivot_df, values_df): pivot DataFrame and the intermediate
            `values` DataFrame with columns ['sample', 'eaeC','stx1','Ecoli','stx2','count','pattern']
    """

    dataframes = []

    for filename, fileobj in files:
        # Ensure we pass a file-like object to pandas
        # If fileobj is a bytes object or Streamlit's UploadedFile, pandas
        # can read it directly.
        try:
            df = pd.read_csv(fileobj, skiprows=3)
        except Exception as e:
            raise ValueError(f"Failed to read CSV '{filename}': {e}")

        # Derive a sample name from filename to match previous logic
        sample_name = os.path.splitext(os.path.basename(filename))[0]
        # The original code used sample_name.split("_")[1]
        sample_part = None
        parts = sample_name.split("_")
        if len(parts) > 1:
            sample_part = parts[1]
        else:
            sample_part = parts[0]

        df["sample"] = sample_part
        dataframes.append(df)

    if not dataframes:
        raise ValueError("No input files provided")

    combined_df = pd.concat(dataframes, ignore_index=True)

    # Expected column names in the CSV files (as in the original script)
    expected_cols = [
        "Senf w  Haselnuss",
        "Mandel Sellerie",
        "Pistache Cashew",
        "Lupine Walnuss",
        "sample",
    ]

    missing = [c for c in expected_cols if c not in combined_df.columns]
    if missing:
        raise ValueError(f"Missing expected columns in CSVs: {missing}")

    df = combined_df[expected_cols].copy()
    df.columns = ["eaeC", "stx1", "Ecoli", "stx2", "sample"]

    # Compute counts per sample for each marker pattern
    values = df.groupby("sample").value_counts().reset_index(name="count")

    markers = ["eaeC", "stx1", "Ecoli", "stx2"]
    values["pattern"] = values[markers].astype(str).agg("".join, axis=1)

    pivot = values.pivot_table(
        index="sample", columns="pattern", values="count", aggfunc="sum", fill_value=0
    )

    return pivot, values


def make_plotly_stacked_bar(pivot_df: pd.DataFrame, title: str = None, *, counts_df: pd.DataFrame = None, pct_df: pd.DataFrame = None, show_percent: bool = False) -> go.Figure:
    """Build a stacked bar Plotly figure from a pivot table (samples x pattern).

    Args:
        pivot_df: DataFrame where index is sample and columns are patterns.
        title: optional figure title.

    Returns:
        plotly.graph_objects.Figure
    """
    # Ensure consistent row ordering
    df = pivot_df.copy()
    df = df.sort_index()

    # Custom ordering of pattern columns to prioritize Ecoli-related patterns.
    def pattern_key(pat: str):
        # pat is a string like '0101' representing [eaeC, stx1, Ecoli, stx2]
        eae = int(pat[0])
        stx1 = int(pat[1])
        ecoli = int(pat[2])
        stx2 = int(pat[3])
        ones = eae + stx1 + ecoli + stx2

        # Groups (lower value = higher priority)
        # 0: Ecoli only (0010)
        if ecoli == 1 and ones == 1:
            group = 0
        # 1: non-Ecoli but stx1 positive
        elif ecoli == 0 and stx1 == 1:
            group = 1
        # 2: Ecoli + stx2 (but not the simple Ecoli-only)
        elif ecoli == 1 and stx2 == 1 and ones <= 2:
            group = 2
        # 3: Ecoli + eaeC
        elif ecoli == 1 and eae == 1 and ones <= 2:
            group = 3
        # 4: triple or more positives that include Ecoli
        elif ecoli == 1 and ones >= 3:
            group = 4
        # 5: everything else (fallback)
        else:
            group = 5

        # secondary key: fewer positives first, then pattern string for stable order
        return (group, ones, pat)

    ordered_cols = sorted(list(df.columns.astype(str)), key=pattern_key)

    fig = go.Figure()
    # use a qualitative color palette from plotly express to ensure colored PNG exports
    palette = px.colors.qualitative.Plotly

    def pattern_to_label(pat: str) -> str:
        # pat is e.g. '1010' mapping to [eaeC, stx1, Ecoli, stx2]
        try:
            eae = int(pat[0])
            stx1 = int(pat[1])
            ecoli = int(pat[2])
            stx2 = int(pat[3])
        except Exception:
            # Fallback: show raw pattern
            return f"pattern {pat}"

        parts = []
        if ecoli:
            parts.append("Ecoli")
        if eae:
            parts.append("eaeC")
        if stx1:
            parts.append("stx1")
        if stx2:
            parts.append("stx2")

        if parts:
            label = " + ".join(parts)
        else:
            label = "none"

        return f"{label} ({pat})"

    for i, col in enumerate(ordered_cols):
        label = pattern_to_label(str(col))
        # simplify label if it contains a dash: keep only part before any '-'
        if "-" in label:
            label = label.split("-")[0].strip()
        color = palette[i % len(palette)]
        y = df[col]
        # prepare customdata for hover: count and percent if available
        customdata = None
        hovertemplate = None
        if counts_df is not None and col in counts_df.columns:
            counts = counts_df[col].astype(float)
            if pct_df is not None and col in pct_df.columns:
                pct = pct_df[col].astype(float)
                # customdata as two columns: pct, count
                customdata = list(zip(pct.round(2), counts.astype(int)))
                hovertemplate = "%{y} droplets<br>%{customdata[0]:.2f}% of sample<br>(%{customdata[1]} droplets)<extra></extra>"
            else:
                customdata = list(zip([None]*len(counts), counts.astype(int)))
                hovertemplate = "%{y} droplets<br>(%{customdata[1]} droplets)<extra></extra>"

        trace = go.Bar(name=label, x=df.index.astype(str), y=y, marker_color=color)
        if customdata is not None:
            trace.customdata = customdata
        if hovertemplate is not None:
            trace.hovertemplate = hovertemplate
        fig.add_trace(trace)
    # Show concise legend title listing marker order
    legend_title = 'eaeC, stx1, Ecoli, stx2'
    # If showing percent, adjust y-axis title
    ytitle = 'Droplet Count'
    if show_percent:
        ytitle = 'Percent (%)'

    fig.update_layout(barmode='stack', title=title or 'dPCR droplet patterns per sample',
                      xaxis_title='sample', yaxis_title=ytitle, legend_title=legend_title)
    return fig


def human_label(pat: str) -> str:
    """Return a human-readable label for a binary pattern string.

    Example: '1010' -> 'Ecoli + eaeC'
    """
    try:
        eae = int(pat[0])
        stx1 = int(pat[1])
        ecoli = int(pat[2])
        stx2 = int(pat[3])
    except Exception:
        return pat

    parts = []
    if ecoli:
        parts.append("Ecoli")
    if eae:
        parts.append("eaeC")
    if stx1:
        parts.append("stx1")
    if stx2:
        parts.append("stx2")

    if parts:
        return " + ".join(parts)
    return "none"


if __name__ == "__main__":
    # simple CLI helper: process all CSVs in ./data if run directly
    folder_path = "data"
    csv_files = [
        (os.path.basename(p), p) for p in sorted(os.listdir(folder_path)) if p.lower().endswith(".csv")
    ]
    file_pairs = [(name, open(os.path.join(folder_path, name), "rb")) for name, p in csv_files]
    try:
        fig, pivot = analyze_files(file_pairs)
        fig.show()
    finally:
        for _, f in file_pairs:
            try:
                f.close()
            except Exception:
                pass
