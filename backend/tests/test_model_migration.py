import importlib.util
import json
from pathlib import Path


def load_script():
    path = Path(__file__).parents[2] / "scripts" / "migrate_api_pool_model.py"
    spec = importlib.util.spec_from_file_location("migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_only_model_fields_are_changed():
    module = load_script()
    value = {"model": "deepseek-v3", "label": "deepseek-v3", "nested": [{"vision_model": "DeepSeek-V3"}]}
    assert module.migrate(value, "deepseek-v3", "Qwen") == 2
    assert value["label"] == "deepseek-v3"
    assert value["model"] == "Qwen"


def test_all_model_fields_can_be_forced_to_qwen():
    module = load_script()
    value = {
        "model": "forbidden-model",
        "label": "forbidden-model",
        "nested": [{"vision_model": "DeepSeek-V3"}],
    }
    assert module.normalize_all_models(value, "Qwen") == 2
    assert value["label"] == "forbidden-model"
    assert value["model"] == value["nested"][0]["vision_model"] == "Qwen"


def test_committed_pool_example_is_safe_and_only_uses_qwen():
    payload = json.loads((Path(__file__).parents[2] / "backend" / "config" / "api_pool.example.json").read_text())
    model_fields = {"model", "model_name", "default_model", "primary_model", "chat_model", "vision_model"}
    found = []

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in model_fields and isinstance(child, str):
                    found.append(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    assert found
    assert set(found) == {"Qwen"}
    assert payload["entries"]
    assert all(entry["api_key"] == "" and entry["disabled"] is True for entry in payload["entries"])
