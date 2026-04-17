import streamlit as st
from typing import List, Tuple
import io
import pandas as pd

st.title("dPCR results — upload and analyze CSVs")

st.write("Upload one or more CSV files (exported from the dPCR instrument). Click 'Process' to run the analysis.")

uploaded_files = st.file_uploader("Choose CSV files", type=["csv"], accept_multiple_files=True)

# Option: CSV separator for download (semicolon default for Excel compatibility)
use_semicolon = st.checkbox("Download CSV with ';' separator (Excel compatibility)", value=True)

# Option: show percentages instead of counts in the plot
show_percent = st.checkbox("Show percentages (instead of absolute counts) in plots", value=False)

def clear_results():
    for k in list(st.session_state.keys()):
        if k.startswith("results_"):
            del st.session_state[k]

if "results_ready" not in st.session_state:
    st.session_state["results_ready"] = False

col1, col2 = st.columns([1, 1])
with col1:
    process = st.button("Process")
with col2:
    clear = st.button("Clear results")

if clear:
    clear_results()
    st.session_state["results_ready"] = False

if process:
    if not uploaded_files:
        st.error("Please upload at least one CSV file before processing.")
    else:
        from combine_results import analyze_files, make_plotly_stacked_bar
        import plotly.io as pio

        # Prepare (filename, fileobj) pairs for analyze_files
        file_pairs: List[Tuple[str, io.BytesIO]] = []
        for up in uploaded_files:
            file_pairs.append((up.name, up))

        try:
            pivot, values = analyze_files(file_pairs)

            # Build figures for counts and percentages (pass counts and pct to enable hover data)
            # safe percent pivot (avoid division by zero)
            sums = pivot.sum(axis=1).replace(0, 1)
            pct_pivot = pivot.div(sums, axis=0) * 100
            fig_all = make_plotly_stacked_bar(pivot, title="All events: patterns per sample", counts_df=pivot, pct_df=pct_pivot, show_percent=False)
            fig_all_pct = make_plotly_stacked_bar(pct_pivot, title="All events: patterns per sample (percent)", counts_df=pivot, pct_df=pct_pivot, show_percent=True)

            # Prepare bytes for downloads for both variants and store in session_state
            # Counts PNG
            try:
                img_bytes_counts = pio.to_image(fig_all, format="png")
                st.session_state["results_plot_all_png_counts"] = img_bytes_counts
                st.session_state["results_plot_all_html_counts"] = None
            except Exception:
                html_counts = pio.to_html(fig_all, full_html=False)
                st.session_state["results_plot_all_html_counts"] = html_counts
                st.session_state["results_plot_all_png_counts"] = None

            # Percent PNG
            try:
                img_bytes_pct = pio.to_image(fig_all_pct, format="png")
                st.session_state["results_plot_all_png_pct"] = img_bytes_pct
                st.session_state["results_plot_all_html_pct"] = None
            except Exception:
                html_pct = pio.to_html(fig_all_pct, full_html=False)
                st.session_state["results_plot_all_html_pct"] = html_pct
                st.session_state["results_plot_all_png_pct"] = None

            st.session_state["results_pivot_full"] = pivot
            st.session_state["results_values"] = values
            st.session_state["results_fig_all"] = fig_all
            st.session_state["results_fig_all_pct"] = fig_all_pct
            # Prepare basic CSVs (will replace with header-wrapped versions below)
            # (wrapped CSVs created after metadata)

            # --- prepare metadata-wrapped CSVs ---
            import datetime
            header_lines = []
            header_lines.append("dPCR STX analysis")
            header_lines.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            header_lines.append("used files")
            for name, _ in file_pairs:
                header_lines.append(str(name))
            header_lines.append("")

            from combine_results import human_label
            cols = list(pivot.columns.astype(str))
            human_header = [human_label(c) for c in cols]
            binary_header = cols

            # compute total droplets per sample (from full pivot)
            total_per_sample = pivot.sum(axis=1)

            def make_csv_bytes(df, sep=',', totals: dict = None):
                """Create CSV bytes with metadata header, two header rows (human, binary), and optional totals columns.

                totals: optional dict mapping human_label -> pandas Series indexed by sample
                """
                out_lines = []
                out_lines.extend(header_lines)

                # prepare column lists
                base_cols = list(df.columns.astype(str))
                human_base = [human_label(c) for c in base_cols]

                extra_keys = list(totals.keys()) if totals else []
                # human header row: sample + human labels + extra human labels
                out_lines.append(sep.join(["sample"] + human_base + extra_keys))
                # binary header row: empty + binary codes + identifiers for extras
                extra_binaries = [k.lower().replace(' ', '_') for k in extra_keys]
                out_lines.append(sep.join([""] + base_cols + extra_binaries))

                for idx, row in df.iterrows():
                    vals = [str(idx)] + [str(row[c]) for c in base_cols]
                    if totals:
                        for k in extra_keys:
                            series = totals[k]
                            vals.append(str(series.get(idx, "")))
                    out_lines.append(sep.join(vals))

                txt = '\n'.join(out_lines) + '\n'
                return txt.encode('utf-8')

            # For main pivot include total droplets
            totals_map = {"Total droplets": total_per_sample}
            st.session_state["results_csv_comma"] = make_csv_bytes(pivot, sep=',', totals=totals_map)
            st.session_state["results_csv_semicolon"] = make_csv_bytes(pivot, sep=';', totals=totals_map)


            # Ecoli-only
            ecoli_values = values[values["Ecoli"] == 1].copy()
            if ecoli_values.empty:
                st.session_state["results_ecoli_present"] = False
                st.session_state["results_ecoli_pivot"] = None
                st.session_state["results_plot_ecoli_png"] = None
                st.session_state["results_plot_ecoli_html"] = None
            else:
                ecoli_pivot = ecoli_values.pivot_table(index="sample", columns="pattern", values="count", aggfunc="sum", fill_value=0)
                # compute ecoli percent pivot and both figures
                sums_ec = ecoli_pivot.sum(axis=1).replace(0, 1)
                ecoli_pct = ecoli_pivot.div(sums_ec, axis=0) * 100
                fig_ecoli = make_plotly_stacked_bar(ecoli_pivot, title="Ecoli-positive events (Ecoli==1) patterns per sample", counts_df=ecoli_pivot, pct_df=ecoli_pct, show_percent=False)
                fig_ecoli_pct = make_plotly_stacked_bar(ecoli_pct, title="Ecoli-positive events (percent)", counts_df=ecoli_pivot, pct_df=ecoli_pct, show_percent=True)
                try:
                    img_ec = pio.to_image(fig_ecoli, format="png")
                    st.session_state["results_plot_ecoli_png"] = img_ec
                    st.session_state["results_plot_ecoli_html"] = None
                except Exception:
                    html_ec = pio.to_html(fig_ecoli, full_html=False)
                    st.session_state["results_plot_ecoli_html"] = html_ec
                    st.session_state["results_plot_ecoli_png"] = None

                st.session_state["results_ecoli_present"] = True
                st.session_state["results_ecoli_pivot"] = ecoli_pivot
                st.session_state["results_fig_ecoli"] = fig_ecoli
                st.session_state["results_fig_ecoli_pct"] = fig_ecoli_pct
                # prepare ecoli pivot CSVs with metadata header and totals
                ecoli_base = ecoli_pivot.copy()
                # ecoli-positive droplets: sum of patterns (within ecoli_pivot)
                ecoli_pos_series = ecoli_base.sum(axis=1)
                # total droplets per sample from the main pivot (total_per_sample defined above)
                total_series_for_ecoli = total_per_sample.reindex(ecoli_base.index).fillna(0)
                totals_map_ec = {
                    "Ecoli-positive droplets": ecoli_pos_series,
                    "Total droplets": total_series_for_ecoli,
                }
                st.session_state["results_ecoli_csv_comma"] = make_csv_bytes(ecoli_base, sep=',', totals=totals_map_ec)
                st.session_state["results_ecoli_csv_semicolon"] = make_csv_bytes(ecoli_base, sep=';', totals=totals_map_ec)

            st.session_state["results_ready"] = True

        except Exception as e:
            st.exception(e)

# If results are ready in session_state, show them (this will persist across reruns triggered by downloads)
if st.session_state.get("results_ready"):
    from combine_results import make_plotly_stacked_bar

    st.subheader("Results")

    # Show main figure
    # choose which variant to show based on show_percent
    fig_all = st.session_state.get("results_fig_all_pct") if show_percent else st.session_state.get("results_fig_all")
    if fig_all is not None:
        st.plotly_chart(fig_all, width='stretch')
        # Provide downloads from stored bytes depending on percent mode
        if show_percent:
            if st.session_state.get("results_plot_all_png_pct"):
                st.download_button("Download plot (PNG)", data=st.session_state["results_plot_all_png_pct"], file_name="plot_all_percent.png", mime="image/png")
            elif st.session_state.get("results_plot_all_html_pct"):
                st.download_button("Download plot (HTML)", data=st.session_state["results_plot_all_html_pct"], file_name="plot_all_percent.html", mime="text/html")
        else:
            if st.session_state.get("results_plot_all_png_counts"):
                st.download_button("Download plot (PNG)", data=st.session_state["results_plot_all_png_counts"], file_name="plot_all.png", mime="image/png")
            elif st.session_state.get("results_plot_all_html_counts"):
                st.download_button("Download plot (HTML)", data=st.session_state["results_plot_all_html_counts"], file_name="plot_all.html", mime="text/html")

    # Show pivot and CSV download
    pivot = st.session_state.get("results_pivot_full")
    if pivot is not None:
        st.subheader("Counts per sample and pattern (full)")
        # build MultiIndex columns: (human_label, binary_code)
        from combine_results import human_label
        cols = list(pivot.columns.astype(str))
        human_header = [human_label(c) for c in cols]
        multi_cols = pd.MultiIndex.from_tuples(list(zip(human_header, cols)))

        display_df = pivot.copy()
        # add Total droplets column
        display_df["Total droplets"] = display_df.sum(axis=1)
        # build MultiIndex including totals as tuple labels to keep column dtype consistent
        extended_tuples = list(zip(human_header, cols)) + [("Total droplets", "")]
        display_df.columns = pd.MultiIndex.from_tuples(extended_tuples)
        st.dataframe(display_df)
        # Choose CSV bytes based on user's checkbox selection
        csv_data = st.session_state.get("results_csv_semicolon") if use_semicolon else st.session_state.get("results_csv_comma")
        filename = "counts_full_semicolon.csv" if use_semicolon else "counts_full.csv"
        st.download_button("Download counts CSV", data=csv_data, file_name=filename, mime="text/csv")

    # Ecoli-only
    if st.session_state.get("results_ecoli_present"):
        fig_ecoli = st.session_state.get("results_fig_ecoli_pct") if show_percent else st.session_state.get("results_fig_ecoli")
        if fig_ecoli is not None:
            st.plotly_chart(fig_ecoli, width='stretch')
            if show_percent:
                if st.session_state.get("results_plot_ecoli_png_pct"):
                    st.download_button("Download Ecoli plot (PNG)", data=st.session_state["results_plot_ecoli_png_pct"], file_name="plot_ecoli_percent.png", mime="image/png")
                elif st.session_state.get("results_plot_ecoli_html_pct"):
                    st.download_button("Download Ecoli plot (HTML)", data=st.session_state["results_plot_ecoli_html_pct"], file_name="plot_ecoli_percent.html", mime="text/html")
            else:
                if st.session_state.get("results_plot_ecoli_png"):
                    st.download_button("Download Ecoli plot (PNG)", data=st.session_state["results_plot_ecoli_png"], file_name="plot_ecoli.png", mime="image/png")
                elif st.session_state.get("results_plot_ecoli_html"):
                    st.download_button("Download Ecoli plot (HTML)", data=st.session_state["results_plot_ecoli_html"], file_name="plot_ecoli.html", mime="text/html")

        ecoli_pivot = st.session_state.get("results_ecoli_pivot")
        if ecoli_pivot is not None:
            st.subheader("Counts per sample and pattern (Ecoli-positive only)")
            # display with human/binary MultiIndex columns
            from combine_results import human_label
            cols_ec = list(ecoli_pivot.columns.astype(str))
            human_header_ec = [human_label(c) for c in cols_ec]
            multi_cols_ec = pd.MultiIndex.from_tuples(list(zip(human_header_ec, cols_ec)))
            display_ec = ecoli_pivot.copy()
            # add total droplets and ecoli positive droplets
            display_ec["Total droplets"] = display_ec.sum(axis=1)
            # ecoli positive droplets: sum of all patterns where Ecoli bit == 1
            ecoli_cols = [c for c in display_ec.columns.astype(str) if c[2] == '1']
            display_ec["Ecoli-positive droplets"] = display_ec[ecoli_cols].sum(axis=1) if ecoli_cols else 0
            # build MultiIndex including totals to keep columns uniform
            extended_ec_tuples = list(zip(human_header_ec, cols_ec)) + [("Total droplets", ""), ("Ecoli-positive droplets", "")]
            display_ec.columns = pd.MultiIndex.from_tuples(extended_ec_tuples)
            st.dataframe(display_ec)
            csv_ec_data = st.session_state.get("results_ecoli_csv_semicolon") if use_semicolon else st.session_state.get("results_ecoli_csv_comma")
            filename_ec = "counts_ecoli_semicolon.csv" if use_semicolon else "counts_ecoli.csv"
            st.download_button("Download Ecoli counts CSV", data=csv_ec_data, file_name=filename_ec, mime="text/csv")

# streamlit run app.py --server.address 0.0.0.0 --server.port 8501