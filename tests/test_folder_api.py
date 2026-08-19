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


if __name__ == "__main__":
    unittest.main()
