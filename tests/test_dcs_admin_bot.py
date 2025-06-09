import ast
import types
import pathlib


def load_list_foothold_lua_files():
    path = pathlib.Path(__file__).resolve().parents[1] / "dcs_admin_bot.py"
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    func_node = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "list_foothold_lua_files":
            func_node = node
            break
    if func_node is None:
        raise AssertionError("Function list_foothold_lua_files not found")
    mod = types.ModuleType("temp")
    exec("import os", mod.__dict__)
    code = ast.Module(body=[func_node], type_ignores=[])
    exec(compile(code, str(path), "exec"), mod.__dict__)
    return mod.list_foothold_lua_files


def test_existing_directory(tmp_path):
    func = load_list_foothold_lua_files()
    saves = tmp_path / "Saves"
    saves.mkdir()
    (saves / "mission.lua").write_text("-- lua content")
    (saves / "note.txt").write_text("ignore")
    result = func(str(saves))
    assert result == ["mission.lua"]


def test_missing_directory(tmp_path):
    func = load_list_foothold_lua_files()
    missing = tmp_path / "missing"
    result = func(str(missing))
    assert result == []
