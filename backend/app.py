from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from legoizer.pipeline import generate_mpd_report

app = FastAPI(title="Legoizer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_INPUTS = {".obj", ".dae"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/process")
async def process_model(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mtl: Optional[UploadFile] = File(None),
    unit: str = Form("mm"),
    part: str = Form("plate_1x1"),
    max_dim_limit: float = Form(100.0),
    default_color: int = Form(71),
    color_mode: str = Form("none"),
    surface_thickness_mm: Optional[float] = Form(None),
) -> FileResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing input filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_INPUTS:
        raise HTTPException(status_code=415, detail="Only OBJ and DAE inputs are supported")

    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)
        input_path = working_dir / Path(file.filename).name
        input_bytes = await file.read()
        with open(input_path, "wb") as buffer:
            buffer.write(input_bytes)

        mtl_path = None
        if mtl and mtl.filename:
            mtl_path = working_dir / Path(mtl.filename).name
            mtl_bytes = await mtl.read()
            with open(mtl_path, "wb") as buffer:
                buffer.write(mtl_bytes)

        output_dir = working_dir / "result"
        output_path = output_dir / f"{input_path.stem}.mpd"

        result = generate_mpd_report(
            input_path=input_path,
            output_path=output_path,
            unit=unit,
            part=part,
            max_dim_limit=max_dim_limit,
            mtl_path=mtl_path,
            default_color=default_color,
            color_mode=color_mode,
            surface_thickness_mm=surface_thickness_mm,
        )

        temp_mpd = tempfile.NamedTemporaryFile(delete=False, suffix=".mpd")
        temp_mpd.close()
        mpd_path = Path(temp_mpd.name)
        shutil.copyfile(result["mpd_path"], mpd_path)

    background_tasks.add_task(mpd_path.unlink)

    response = FileResponse(
        mpd_path,
        media_type="application/octet-stream",
        filename=f"{Path(file.filename).stem}.mpd",
        background=background_tasks,
    )
    response.headers["X-Legoizer-Metadata"] = json.dumps(result.get("metadata", {}))
    return response
