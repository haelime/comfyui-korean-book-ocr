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


def _bring_windows_dialog_to_front(user32, window, topmost_handle):
    """Show, activate, and keep the native picker above the ComfyUI window."""
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_SHOWWINDOW = 0x0040
    SW_RESTORE = 9
    user32.ShowWindow(window, SW_RESTORE)
    user32.SetWindowPos(
        window,
        topmost_handle,
        0,
        0,
        0,
        0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW,
    )
    user32.BringWindowToTop(window)
    user32.SetForegroundWindow(window)


def _pick_legacy_windows_folder(initial_folder: str, title: str):
    """Open the legacy Shell folder browser as a compatibility fallback."""
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
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
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
    owner_window = user32.GetForegroundWindow()
    topmost_handle = wintypes.HWND(-1)

    @browse_callback
    def callback(window, message, _lparam, data):
        if message == BFFM_INITIALIZED and data:
            user32.SendMessageW(window, BFFM_SETSELECTIONW, 1, data)
            _bring_windows_dialog_to_front(user32, window, topmost_handle)
        return 0

    info = BROWSEINFOW(
        owner_window,
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


def _pick_modern_windows_folder(initial_folder: str, title: str):
    """Open Explorer's modern IFileOpenDialog in folder-selection mode."""
    if os.name != "nt":
        raise NotImplementedError("Windows에서만 사용할 수 있습니다.")

    import ctypes
    import uuid
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    def guid(value):
        parsed = uuid.UUID(value)
        return GUID(
            parsed.time_low,
            parsed.time_mid,
            parsed.time_hi_version,
            (ctypes.c_ubyte * 8)(*parsed.bytes[8:]),
        )

    def method(interface, index, result_type, *argument_types):
        table = ctypes.cast(
            interface, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        return ctypes.WINFUNCTYPE(
            result_type, ctypes.c_void_p, *argument_types
        )(table[index])

    def check(result, operation):
        if result < 0:
            raise OSError(f"{operation} 실패: HRESULT 0x{result & 0xFFFFFFFF:08X}")

    ole32 = ctypes.windll.ole32
    shell32 = ctypes.windll.shell32
    user32 = ctypes.windll.user32
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(GUID),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    shell32.SHCreateItemFromParsingName.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.POINTER(GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    shell32.SHCreateItemFromParsingName.restype = ctypes.c_long
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND

    CLSID_FILE_OPEN_DIALOG = guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")
    IID_FILE_OPEN_DIALOG = guid("D57C7288-D4AD-4768-BE02-9D969532D960")
    IID_SHELL_ITEM = guid("43826D1E-E718-42EE-BC55-A1E261C37BFE")
    CLSCTX_INPROC_SERVER = 0x1
    COINIT_APARTMENTTHREADED = 0x2
    FOS_PICKFOLDERS = 0x20
    FOS_FORCEFILESYSTEM = 0x40
    FOS_PATHMUSTEXIST = 0x800
    FOS_NOCHANGEDIR = 0x8
    SIGDN_FILESYSPATH = 0x80058000
    ERROR_CANCELLED_HRESULT = ctypes.c_long(0x800704C7).value

    initialized_result = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    initialized = initialized_result in (0, 1)
    if not initialized:
        check(initialized_result, "COM 초기화")

    dialog = ctypes.c_void_p()
    selected_item = ctypes.c_void_p()
    initial_item = ctypes.c_void_p()
    path_pointer = ctypes.c_void_p()
    try:
        check(
            ole32.CoCreateInstance(
                ctypes.byref(CLSID_FILE_OPEN_DIALOG),
                None,
                CLSCTX_INPROC_SERVER,
                ctypes.byref(IID_FILE_OPEN_DIALOG),
                ctypes.byref(dialog),
            ),
            "최신 폴더 선택창 생성",
        )
        get_options = method(dialog, 10, ctypes.c_long, ctypes.POINTER(wintypes.DWORD))
        set_options = method(dialog, 9, ctypes.c_long, wintypes.DWORD)
        set_folder = method(dialog, 12, ctypes.c_long, ctypes.c_void_p)
        set_title = method(dialog, 17, ctypes.c_long, wintypes.LPCWSTR)
        show = method(dialog, 3, ctypes.c_long, wintypes.HWND)
        get_result = method(dialog, 20, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))

        options = wintypes.DWORD()
        check(get_options(dialog, ctypes.byref(options)), "폴더 선택창 옵션 읽기")
        check(
            set_options(
                dialog,
                options.value | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM
                | FOS_PATHMUSTEXIST | FOS_NOCHANGEDIR,
            ),
            "폴더 선택창 옵션 설정",
        )
        check(set_title(dialog, title), "폴더 선택창 제목 설정")

        if Path(initial_folder).is_dir():
            result = shell32.SHCreateItemFromParsingName(
                initial_folder, None, ctypes.byref(IID_SHELL_ITEM), ctypes.byref(initial_item)
            )
            if result >= 0 and initial_item:
                check(set_folder(dialog, initial_item), "시작 폴더 설정")

        result = show(dialog, user32.GetForegroundWindow())
        if result == ERROR_CANCELLED_HRESULT:
            return None
        check(result, "폴더 선택창 표시")
        check(get_result(dialog, ctypes.byref(selected_item)), "선택 폴더 읽기")

        get_display_name = method(
            selected_item, 5, ctypes.c_long, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)
        )
        check(
            get_display_name(selected_item, SIGDN_FILESYSPATH, ctypes.byref(path_pointer)),
            "선택 경로 변환",
        )
        return str(Path(ctypes.wstring_at(path_pointer.value)).resolve())
    finally:
        if path_pointer:
            ole32.CoTaskMemFree(path_pointer)
        for interface in (initial_item, selected_item, dialog):
            if interface:
                release = method(interface, 2, ctypes.c_ulong)
                release(interface)
        if initialized:
            ole32.CoUninitialize()


def _pick_windows_folder(initial_folder: str, title: str):
    """Prefer Explorer's modern picker, falling back to the legacy dialog."""
    try:
        return _pick_modern_windows_folder(initial_folder, title)
    except Exception:
        return _pick_legacy_windows_folder(initial_folder, title)


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
