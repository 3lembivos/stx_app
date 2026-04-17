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
import matplotlib.pyplot as plt


def analyze_files(files: Iterable[Tuple[str, IO]]):
    """Read multiple CSV-like files, combine them and return (fig, pivot_df).

    Args:
        files: iterable of (filename, filelike) pairs. filelike can be a
               path-like object, an open file, or an in-memory buffer
               (e.g. BytesIO) accepted by pandas.read_csv.

    Returns:
        (fig, pivot_df): matplotlib.figure.Figure and pandas.DataFrame
            where pivot_df is the table used to draw the stacked bar chart.
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

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 5))
    pivot.plot(kind="bar", stacked=True, ax=ax)
    ax.set_ylabel("Droplet count")
    ax.set_title("dPCR droplet patterns per sample")
    ax.legend(title="eaeC, stx1, Ecoli, stx2", bbox_to_anchor=(1.05, 1))
    fig.tight_layout()

    return fig, pivot


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
