import streamlit as st
from typing import List, Tuple
import io

st.title("dPCR results — upload and analyze CSVs")

st.write("Upload one or more CSV files (exported from the dPCR instrument). Click 'Process' to run the analysis.")

uploaded_files = st.file_uploader("Choose CSV files", type=["csv"], accept_multiple_files=True)

process = st.button("Process")

if process:
    if not uploaded_files:
        st.error("Please upload at least one CSV file before processing.")
    else:
        # Import here to avoid importing heavy libs unless needed
        from combine_results import analyze_files

        # Prepare (filename, fileobj) pairs for analyze_files
        file_pairs: List[Tuple[str, io.BytesIO]] = []
        for up in uploaded_files:
            # Streamlit's UploadedFile supports read() and is file-like
            # but pandas can consume it directly. We'll pass the UploadedFile
            # together with its name.
            file_pairs.append((up.name, up))

        try:
            fig, pivot = analyze_files(file_pairs)
            st.pyplot(fig)
            st.subheader("Counts per sample and pattern")
            st.dataframe(pivot)
        except Exception as e:
            st.exception(e)

# streamlit run app.py --server.address 0.0.0.0 --server.port 8501

