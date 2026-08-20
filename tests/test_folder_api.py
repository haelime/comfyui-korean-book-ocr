import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).parents[1]


class _Routes:
    def get(self, _path):
        return lambda function: function

    def post(self, _path):
        return lambda function: function


class FolderApiTests(unittest.TestCase):
    def test_folder_list_is_relative_sorted_and_hides_dot_folders(self):
        fake_folder_paths = types.SimpleNamespace(
            get_input_directory=lambda: "input",
            get_output_directory=lambda: "output",
        )
        fake_server = types.SimpleNamespace(
            PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=_Routes()))
        )
        with patch.dict(sys.modules, {"folder_paths": fake_folder_paths, "server": fake_server}):
            spec = importlib.util.spec_from_file_location("folder_api_test", ROOT / "folder_api.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as temporary:
            base = pathlib.Path(temporary)
            (base / "나" / "하위").mkdir(parents=True)
            (base / "가").mkdir()
            (base / ".숨김").mkdir()

            folders = module._relative_folders(base)

        self.assertEqual(folders, ["가", "나", "나/하위"])

    def test_native_picker_endpoint_is_limited_to_local_requests(self):
        fake_folder_paths = types.SimpleNamespace(
            get_input_directory=lambda: "input",
            get_output_directory=lambda: "output",
        )
        fake_server = types.SimpleNamespace(
            PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=_Routes()))
        )
        with patch.dict(sys.modules, {"folder_paths": fake_folder_paths, "server": fake_server}):
            spec = importlib.util.spec_from_file_location("folder_api_local_test", ROOT / "folder_api.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        self.assertTrue(module._is_local_request(types.SimpleNamespace(remote="127.0.0.1")))
        self.assertTrue(module._is_local_request(types.SimpleNamespace(remote="::1")))
        self.assertFalse(module._is_local_request(types.SimpleNamespace(remote="192.168.0.10")))

    def test_native_dialog_is_made_topmost_and_foreground(self):
        fake_folder_paths = types.SimpleNamespace(
            get_input_directory=lambda: "input",
            get_output_directory=lambda: "output",
        )
        fake_server = types.SimpleNamespace(
            PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=_Routes()))
        )
        with patch.dict(sys.modules, {"folder_paths": fake_folder_paths, "server": fake_server}):
            spec = importlib.util.spec_from_file_location("folder_api_front_test", ROOT / "folder_api.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        calls = []
        user32 = types.SimpleNamespace(
            ShowWindow=lambda *args: calls.append(("show", args)),
            SetWindowPos=lambda *args: calls.append(("topmost", args)),
            BringWindowToTop=lambda *args: calls.append(("bring", args)),
            SetForegroundWindow=lambda *args: calls.append(("foreground", args)),
        )
        module._bring_windows_dialog_to_front(user32, 100, -1)

        self.assertEqual([name for name, _ in calls], ["show", "topmost", "bring", "foreground"])
        self.assertEqual(calls[1][1][1], -1)

    def test_modern_picker_falls_back_to_legacy_dialog(self):
        fake_folder_paths = types.SimpleNamespace(
            get_input_directory=lambda: "input",
            get_output_directory=lambda: "output",
        )
        fake_server = types.SimpleNamespace(
            PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=_Routes()))
        )
        with patch.dict(sys.modules, {"folder_paths": fake_folder_paths, "server": fake_server}):
            spec = importlib.util.spec_from_file_location("folder_api_fallback_test", ROOT / "folder_api.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        with patch.object(module, "_pick_modern_windows_folder", side_effect=OSError("COM 실패")), patch.object(
            module, "_pick_legacy_windows_folder", return_value="C:\\선택"
        ) as legacy:
            selected = module._pick_windows_folder("C:\\시작", "폴더 선택")

        self.assertEqual(selected, "C:\\선택")
        legacy.assert_called_once_with("C:\\시작", "폴더 선택")


if __name__ == "__main__":
    unittest.main()
