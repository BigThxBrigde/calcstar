"""settings_store 设置持久化测试（基于 tmp_path 独立文件）。"""

import json

import pytest

from calcstar.data.settings_store import load_settings, save_settings
from calcstar.services.settings_service import SettingsService


def _full_settings() -> dict:
    """构造一份与设置页 collectConfig 输出一致的完整设置。"""
    return {
        "category": "mul_div",
        "range_n": 50,
        "count": 100,
        "duration_minutes": 10,
        "allow_negative": True,
        "include_parentheses": False,
        "per_page": 20,
        "operand_count": "random",
        "blank_position": "any",
    }


class TestSettingsStore:
    def test_load_missing_file_returns_empty(self, tmp_path):
        """文件不存在时返回空字典。"""
        assert load_settings(tmp_path / "settings.json") == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        """保存后读取，字段完整保留。"""
        path = tmp_path / "settings.json"
        save_settings(_full_settings(), path)
        assert load_settings(path) == _full_settings()

    def test_save_filters_unknown_keys(self, tmp_path):
        """未知字段被丢弃，不写入文件。"""
        path = tmp_path / "settings.json"
        settings = dict(_full_settings(), hacker_field="x")
        save_settings(settings, path)
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert "hacker_field" not in on_disk
        assert load_settings(path) == _full_settings()

    def test_load_corrupt_file_returns_empty(self, tmp_path):
        """文件内容损坏（非法 JSON）时返回空字典而不抛异常。"""
        path = tmp_path / "settings.json"
        path.write_text("{not valid json", encoding="utf-8")
        assert load_settings(path) == {}

    def test_load_non_object_returns_empty(self, tmp_path):
        """文件内容为非对象（如数组）时返回空字典。"""
        path = tmp_path / "settings.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert load_settings(path) == {}

    def test_save_creates_parent_dirs(self, tmp_path):
        """父目录不存在时自动创建。"""
        path = tmp_path / "a" / "b" / "settings.json"
        save_settings(_full_settings(), path)
        assert load_settings(path) == _full_settings()

    def test_save_is_atomic_no_tmp_left(self, tmp_path):
        """保存完成后目录中不残留临时文件。"""
        path = tmp_path / "settings.json"
        save_settings(_full_settings(), path)
        assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]

    def test_save_overwrites_previous(self, tmp_path):
        """重复保存以最新内容为准。"""
        path = tmp_path / "settings.json"
        first = _full_settings()
        first["range_n"] = 20
        save_settings(first, path)
        second = _full_settings()
        second["category"] = "add"
        save_settings(second, path)
        loaded = load_settings(path)
        assert loaded["range_n"] == 50
        assert loaded["category"] == "add"


class TestSettingsService:
    def test_default_path_via_env(self, tmp_path, monkeypatch):
        """默认路径使用用户数据目录（通过 APPDATA 重定向验证）。"""
        monkeypatch.setenv("APPDATA", str(tmp_path))
        service = SettingsService()
        assert service.load() == {}
        service.save(_full_settings())
        assert service.load() == _full_settings()
        assert (tmp_path / "CalcStar" / "settings.json").exists()

    def test_custom_path_roundtrip(self, tmp_path):
        """注入自定义路径时读写均指向该文件。"""
        service = SettingsService(tmp_path / "custom.json")
        service.save(_full_settings())
        assert service.load() == _full_settings()


@pytest.mark.parametrize("key", sorted(_full_settings().keys()))
def test_all_fields_survive_roundtrip(tmp_path, key):
    """逐字段验证白名单覆盖：每个字段都能完整持久化。"""
    path = tmp_path / "settings.json"
    save_settings(_full_settings(), path)
    assert key in load_settings(path)
