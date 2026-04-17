# dPCR STX Streamlit app (stx_app)

This folder contains a Streamlit app to upload dPCR CSV exports and analyze patterns (STX/eaeC/Ecoli). It produces stacked-bar plots (Plotly), CSV exports (with metadata header), and PNG downloads using Kaleido.

Requirements
------------
- Python 3.10+ (this project was developed with Python 3.14 in a conda env)
- The packages in `requirements.txt` (you can use pip or conda)
- Kaleido requires a Chromium/Chrome installation for PNG export. On Debian/Ubuntu install with:

```bash
sudo apt update && sudo apt install -y chromium
```

Install with pip (recommended inside a virtualenv or conda env):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or with conda:

```bash
conda create -n streamlit python=3.14
conda activate streamlit
pip install -r requirements.txt
```

Run the app
-----------

From the repository root (or from within `stx_app/`):

```bash
streamlit run stx_app/app.py --server.address 0.0.0.0 --server.port 8501
```

Notes
-----
- The app caches generated PNG/CSV bytes in Streamlit's `session_state` so download buttons won't trigger a full recomputation.
- If PNG export fails with Kaleido, check that Chromium/Chrome is installed and available in PATH. You can also fall back to an HTML download which the app provides when PNG generation fails.
- If you want pinned package versions tailored to your environment, adjust `requirements.txt` accordingly.

If you want, I can also produce a `environment.yml` for conda with explicit channels and the same packages. Would you like that?