# legoizer (MVP)

Convert an OBJ mesh to an LDraw MPD using a single LEGO part size and a fixed color.

The repository now ships a web-friendly pipeline with a FastAPI backend and a lightweight frontend so you can upload models from the browser and download the generated MPD package.

## Install
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage
```bash
python -m legoizer.cli --input examples/ren.obj --unit mm --part plate_1x1 --out output.mpd
```

### Supported parts (MVP)
- `plate_1x1` (LDraw 3024), height = 1 plate = 3.2 mm
- `brick_1x1` (LDraw 3005), height = 1 brick = 9.6 mm

> Note: MVP supports only 1×1 parts to ensure every occupied voxel can be covered.

## Web app

### Backend (FastAPI)

```bash
uvicorn backend.app:app --reload
```

The API exposes `POST /api/process` for model conversion and `GET /health` for health checks. Upload an `.obj`/`.dae` model (and optional `.mtl` file), choose the desired parameters, and the service streams back the generated `.mpd` file. Metadata derived from the report is returned via the `X-Legoizer-Metadata` header for clients that want to display stats.

### Frontend (static)

Serve the `frontend/` directory with any static server, then point the UI at the backend URL (defaults to `http://localhost:8000`). For example:

```bash
python -m http.server --directory frontend 5173
```

Open `http://localhost:5173` in your browser, upload your model, and download the generated package when processing completes. Set `window.API_BASE_URL` in a small script tag if the backend runs on a different origin.
