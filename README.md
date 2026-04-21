# dPCR STX Streamlit app 


Run the app
-----------

From the repository root (or from within `stx_app/`):

```bash
streamlit run stx_app/app.py --server.address 0.0.0.0 --server.port 8501
```

Streamlit Community Cloud
-------------------------
If you deploy to Streamlit Community Cloud, add `runtime.txt` (already included) to pin the Python runtime. The file contains `python-3.11` which is supported by the Cloud. Ensure `requirements.txt` lists required packages.
