"""Run the local edit engine or its loopback service."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
from pathlib import Path

from .model import FluxGenerator
from .pipeline import EditPipeline, EditRequest


def main():
    parser = argparse.ArgumentParser(prog="editlock")
    commands = parser.add_subparsers(dest="command", required=True)
    edit = commands.add_parser("edit", help="Make one protected image edit")
    edit.add_argument("--image", type=Path, required=True)
    edit.add_argument("--mask", type=Path, required=True)
    edit.add_argument("--instruction", required=True)
    edit.add_argument("--output", type=Path)
    edit.add_argument("--seed", type=int, default=42)
    edit.add_argument("--feather", type=int, default=10)
    edit.add_argument("--max-side", type=int, default=768)
    serve = commands.add_parser("serve", help="Start the local Mac app service")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--token", required=True)
    web = commands.add_parser("web", help="Open the browser editor on localhost")
    web.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.command in {"serve", "web"}:
        import uvicorn
        from .server import create_app

        token = args.token if args.command == "serve" else secrets.token_urlsafe(20)
        if args.command == "web":
            print(f"Open http://127.0.0.1:{args.port}/?token={token}", flush=True)
        uvicorn.run(create_app(token), host="127.0.0.1", port=args.port, log_level="warning")
        return

    engine = EditPipeline(FluxGenerator())
    result = engine.run(EditRequest(
        image_path=args.image,
        mask_path=args.mask,
        instruction=args.instruction,
        seed=args.seed,
        feather_px=args.feather,
        max_model_side=args.max_side,
    ))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result.output_path, args.output)
    print(json.dumps({
        "session_id": result.session_id,
        "output_path": str(args.output or result.output_path),
        "candidate_path": str(result.candidate_path),
        "elapsed_seconds": result.elapsed_seconds,
        "protected_pixels_identical": result.protected_pixels_identical,
        "alignment_used": result.alignment_used,
    }, indent=2))


if __name__ == "__main__":
    main()
