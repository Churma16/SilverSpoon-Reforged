import os
import json
import pytest
from unittest.mock import patch
from core.settings import load_settings, save_settings


@pytest.mark.unit
def test_load_settings_does_not_save_when_complete_file_exists(tmp_path, monkeypatch):
    test_settings_path = str(tmp_path / "test_settings.json")
    monkeypatch.setattr("core.settings.get_settings_path", lambda: test_settings_path)

    initial_settings = load_settings()
    assert os.path.exists(test_settings_path)
    assert isinstance(initial_settings, dict)

    with patch("core.settings.save_settings", wraps=save_settings) as spy_save_settings:
        for _ in range(5):
            loaded_settings = load_settings()
            assert loaded_settings == initial_settings

        spy_save_settings.assert_not_called()


@pytest.mark.unit
def test_load_settings_saves_when_file_newly_created(tmp_path, monkeypatch):
    test_settings_path = str(tmp_path / "new_settings.json")
    monkeypatch.setattr("core.settings.get_settings_path", lambda: test_settings_path)

    assert not os.path.exists(test_settings_path)

    with patch("core.settings.save_settings", wraps=save_settings) as spy_save_settings:
        loaded_settings = load_settings()
        spy_save_settings.assert_called_once()

    assert os.path.exists(test_settings_path)
    assert isinstance(loaded_settings, dict)
    assert "default_save_dir" in loaded_settings


@pytest.mark.unit
def test_load_settings_saves_when_missing_default_keys_backfilled(tmp_path, monkeypatch):
    test_settings_path = str(tmp_path / "partial_settings.json")
    monkeypatch.setattr("core.settings.get_settings_path", lambda: test_settings_path)

    partial_settings = {
        "max_workers": 7,
        "auto_shutdown_action": "Sleep"
    }
    with open(test_settings_path, "w", encoding="utf-8") as settings_file:
        json.dump(partial_settings, settings_file)

    with patch("core.settings.save_settings", wraps=save_settings) as spy_save_settings:
        loaded_settings = load_settings()
        spy_save_settings.assert_called_once()

    assert loaded_settings["max_workers"] == 7
    assert loaded_settings["auto_shutdown_action"] == "Sleep"
    assert "default_save_dir" in loaded_settings
    assert "last_update_check" in loaded_settings

    with patch("core.settings.save_settings", wraps=save_settings) as spy_save_settings_repeated:
        repeated_loaded_settings = load_settings()
        spy_save_settings_repeated.assert_not_called()

    assert repeated_loaded_settings == loaded_settings
