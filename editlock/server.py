"""Loopback-only service used by the native Mac interface."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import re
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from PIL import Image, ImageOps

from .model import FluxGenerator
from .pipeline import EditPipeline, EditRequest
from .pipeline import ROOT


class EditPayload(BaseModel):
    image_path: str
    mask_path: str
    instruction: str = Field(min_length=1)
    seed: int = 42
    feather_px: int = Field(default=10, ge=0, le=100)


class PreparePayload(BaseModel):
    image_path: str


class UploadPayload(BaseModel):
    data_url: str
    kind: str


def create_app(token: str, pipeline: EditPipeline | None = None) -> FastAPI:
    if not token:
        raise ValueError("A local session token is required.")
    app = FastAPI(title="EditLock Local Engine", docs_url=None, redoc_url=None, openapi_url=None)
    engine = pipeline or EditPipeline(FluxGenerator())
    job_lock = asyncio.Lock()

    def authorize(x_editlock_token: str | None = Header(default=None)) -> None:
        if x_editlock_token != token:
            raise HTTPException(status_code=401, detail="Invalid local session token.")

    def authorize_query(value: str) -> None:
        if value != token:
            raise HTTPException(status_code=401, detail="Invalid local session token.")

    @app.get("/", response_class=HTMLResponse)
    def web_editor(token_value: str = Query(alias="token")):
        authorize_query(token_value)
        html = (Path(__file__).parent / "web" / "index.html").read_text()
        return HTMLResponse(html.replace("__EDITLOCK_TOKEN__", json.dumps(token)))

    @app.get("/health", dependencies=[Depends(authorize)])
    def health():
        return {"status": "ready", "busy": job_lock.locked()}

    @app.post("/prepare", dependencies=[Depends(authorize)])
    def prepare(payload: PreparePayload):
        image_path = Path(payload.image_path).expanduser()
        if not image_path.is_file():
            raise HTTPException(status_code=400, detail="Photo file does not exist.")
        try:
            with Image.open(image_path) as image_file:
                image = ImageOps.exif_transpose(image_file).convert("RGB")
        except OSError as exc:
            raise HTTPException(status_code=400, detail=f"Cannot open photo: {exc}") from exc
        folder = ROOT / "outputs" / "imports"
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / f"{uuid.uuid4().hex}.png"
        image.save(output)
        return {"image_path": str(output), "width": image.width, "height": image.height}

    @app.post("/upload", dependencies=[Depends(authorize)])
    def upload(payload: UploadPayload):
        if payload.kind not in {"photo", "mask"}:
            raise HTTPException(status_code=400, detail="Upload kind must be photo or mask.")
        if len(payload.data_url) > 50_000_000 or not payload.data_url.startswith("data:image/"):
            raise HTTPException(status_code=400, detail="Choose an image smaller than 35 MB.")
        try:
            encoded = payload.data_url.split(",", 1)[1]
            raw = base64.b64decode(encoded, validate=True)
            with Image.open(BytesIO(raw)) as image_file:
                image = ImageOps.exif_transpose(image_file).convert("RGB" if payload.kind == "photo" else "L")
        except (IndexError, ValueError, binascii.Error, OSError) as exc:
            raise HTTPException(status_code=400, detail="Could not read that image.") from exc
        folder = ROOT / "outputs" / "imports"
        folder.mkdir(parents=True, exist_ok=True)
        image_id = uuid.uuid4().hex
        output = folder / f"{image_id}.png"
        image.save(output)
        return {
            "image_path": str(output),
            "width": image.width,
            "height": image.height,
            "asset_url": f"/asset/{image_id}?token={token}",
        }

    @app.get("/asset/{image_id}")
    def asset(image_id: str, token_value: str = Query(alias="token")):
        authorize_query(token_value)
        if not re.fullmatch(r"[0-9a-f]{32}", image_id):
            raise HTTPException(status_code=404)
        path = ROOT / "outputs" / "imports" / f"{image_id}.png"
        if not path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type="image/png")

    @app.get("/session/{session_id}/result.png")
    def result_image(session_id: str, token_value: str = Query(alias="token")):
        authorize_query(token_value)
        if not re.fullmatch(r"[0-9a-f]{12}", session_id):
            raise HTTPException(status_code=404)
        path = engine.session_root / session_id / "result.png"
        if not path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type="image/png")

    @app.post("/edit", dependencies=[Depends(authorize)])
    async def edit(payload: EditPayload):
        if job_lock.locked():
            raise HTTPException(status_code=409, detail="Another edit is running.")
        image_path = Path(payload.image_path).expanduser()
        mask_path = Path(payload.mask_path).expanduser()
        if not image_path.is_file() or not mask_path.is_file():
            raise HTTPException(status_code=400, detail="Image or mask file does not exist.")
        request = EditRequest(
            image_path=image_path,
            mask_path=mask_path,
            instruction=payload.instruction,
            seed=payload.seed,
            feather_px=payload.feather_px,
        )
        async with job_lock:
            try:
                result = await asyncio.to_thread(engine.run, request)
            except (ValueError, FileNotFoundError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Edit failed: {exc}") from exc
        return {
            "session_id": result.session_id,
            "source_path": str(result.source_path),
            "mask_path": str(result.mask_path),
            "candidate_path": str(result.candidate_path),
            "output_path": str(result.output_path),
            "elapsed_seconds": result.elapsed_seconds,
            "protected_pixels_identical": result.protected_pixels_identical,
            "alignment_used": result.alignment_used,
            "result_url": f"/session/{result.session_id}/result.png?token={token}",
        }

    return app
