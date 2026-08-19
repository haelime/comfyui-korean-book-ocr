"""Small ComfyUI endpoint used by the batch-node folder picker."""

import os
from pathlib import Path

import folder_paths
from aiohttp import web
from server import PromptServer


def _relative_folders(base: Path, limit: int = 500):
    base.mkdir(parents=True, exist_ok=True)
    found = []
    for root, directories, _ in os.walk(base):
        directories[:] = sorted(name for name in directories if not name.startswith("."))
        for name in directories:
            relative = (Path(root) / name).relative_to(base).as_posix()
            found.append(relative)
            if len(found) >= limit:
                return found
    return found


@PromptServer.instance.routes.get("/korean-book-ocr/folders")
async def korean_book_ocr_folders(request):
    kind = request.query.get("kind", "input")
    if kind == "input":
        base = Path(folder_paths.get_input_directory()).resolve()
    elif kind == "output":
        base = Path(folder_paths.get_output_directory()).resolve()
    else:
        return web.json_response({"error": "지원하지 않는 폴더 종류입니다."}, status=400)
    return web.json_response({"kind": kind, "folders": _relative_folders(base)})
