"""ComfyUI endpoints used by the batch-node folder picker."""

import asyncio
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


def _is_local_request(request):
    remote = getattr(request, "remote", None)
    return remote in (None, "127.0.0.1", "::1", "::ffff:127.0.0.1")


def _pick_windows_folder(initial_folder: str, title: str):
    """Open the native Windows Shell folder browser and return an absolute path."""
    if os.name != "nt":
        raise NotImplementedError("Windows에서만 사용할 수 있습니다.")

    import ctypes
    from ctypes import wintypes

    browse_callback = ctypes.WINFUNCTYPE(
        ctypes.c_int, wintypes.HWND, wintypes.UINT, wintypes.LPARAM, wintypes.LPARAM
    )

    class BROWSEINFOW(ctypes.Structure):
        _fields_ = [
            ("hwndOwner", wintypes.HWND),
            ("pidlRoot", ctypes.c_void_p),
            ("pszDisplayName", wintypes.LPWSTR),
            ("lpszTitle", wintypes.LPCWSTR),
            ("ulFlags", wintypes.UINT),
            ("lpfn", browse_callback),
            ("lParam", wintypes.LPARAM),
            ("iImage", ctypes.c_int),
        ]

    shell32 = ctypes.windll.shell32
    user32 = ctypes.windll.user32
    ole32 = ctypes.windll.ole32
    shell32.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BROWSEINFOW)]
    shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
    shell32.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]
    shell32.SHGetPathFromIDListW.restype = wintypes.BOOL
    user32.SendMessageW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    ]
    user32.SendMessageW.restype = wintypes.LPARAM
    ole32.CoInitialize.argtypes = [ctypes.c_void_p]
    ole32.CoInitialize.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None

    display_name = ctypes.create_unicode_buffer(32768)
    selected_path = ctypes.create_unicode_buffer(32768)
    initial_path = ctypes.create_unicode_buffer(initial_folder)
    initial_pointer = ctypes.cast(initial_path, ctypes.c_void_p).value or 0
    BFFM_INITIALIZED = 1
    BFFM_SETSELECTIONW = 0x400 + 103
    BIF_RETURNONLYFSDIRS = 0x0001
    BIF_EDITBOX = 0x0010
    BIF_NEWDIALOGSTYLE = 0x0040

    @browse_callback
    def callback(window, message, _lparam, data):
        if message == BFFM_INITIALIZED and data:
            user32.SendMessageW(window, BFFM_SETSELECTIONW, 1, data)
        return 0

    info = BROWSEINFOW(
        None,
        None,
        ctypes.cast(display_name, wintypes.LPWSTR),
        title,
        BIF_RETURNONLYFSDIRS | BIF_EDITBOX | BIF_NEWDIALOGSTYLE,
        callback,
        initial_pointer,
        0,
    )
    initialized = ole32.CoInitialize(None) in (0, 1)
    item_id = None
    try:
        item_id = shell32.SHBrowseForFolderW(ctypes.byref(info))
        if not item_id:
            return None
        if not shell32.SHGetPathFromIDListW(item_id, selected_path):
            raise RuntimeError("선택한 폴더 경로를 읽지 못했습니다.")
        return str(Path(selected_path.value).resolve())
    finally:
        if item_id:
            ole32.CoTaskMemFree(item_id)
        if initialized:
            ole32.CoUninitialize()


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


@PromptServer.instance.routes.post("/korean-book-ocr/pick-folder")
async def korean_book_ocr_pick_folder(request):
    if not _is_local_request(request):
        return web.json_response(
            {"error": "Windows 폴더 창은 ComfyUI를 실행한 PC에서만 열 수 있습니다."},
            status=403,
        )
    if os.name != "nt":
        return web.json_response({"supported": False}, status=501)

    kind = request.query.get("kind", "input")
    if kind == "input":
        initial = Path(folder_paths.get_input_directory()).resolve()
    elif kind == "output":
        initial = Path(folder_paths.get_output_directory()).resolve()
    else:
        return web.json_response({"error": "지원하지 않는 폴더 종류입니다."}, status=400)

    try:
        selected = await asyncio.to_thread(
            _pick_windows_folder, str(initial), "ComfyUI에서 사용할 폴더를 선택하세요"
        )
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)
    return web.json_response({"supported": True, "cancelled": selected is None, "path": selected})
