"""
BLUE_AI Config — TOML konfigürasyon yönetimi.

Tüm uygulama ayarlarını merkezi olarak yönetir.
"""

import tomllib
from pathlib import Path
from typing import Any


_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "blue_ai.toml"

_config_cache: dict[str, Any] | None = None


def load_config(path: Path | None = None) -> dict[str, Any]:
    """TOML konfigürasyon dosyasını yükle ve önbellekle."""
    global _config_cache
    config_path = path or _DEFAULT_CONFIG_PATH
    if _config_cache is None or path is not None:
        with open(config_path, "rb") as f:
            _config_cache = tomllib.load(f)
    return _config_cache


def get(key: str, default: Any = None) -> Any:
    """Noktalı anahtar yolu ile konfigürasyon değeri al.

    Örnek: get("thresholds.cpu_warning") -> 80
    """
    cfg = load_config()
    keys = key.split(".")
    val = cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
            if val is None:
                return default
        else:
            return default
    return val


def get_profile(name: str | None = None) -> dict[str, Any]:
    """Belirtilen profili döndür. None ise varsayılan profili döndür."""
    cfg = load_config()
    profile_name = name or cfg.get("general", {}).get("default_profile", "balanced")
    profiles = cfg.get("profiles", {})
    return profiles.get(profile_name, profiles.get("balanced", {}))


def get_plugin_enabled(plugin_name: str) -> bool:
    """Plugin'in aktif olup olmadığını kontrol et."""
    return get(f"plugins.{plugin_name}", True)


def reload() -> dict[str, Any]:
    """Konfigürasyonu yeniden yükle."""
    global _config_cache
    _config_cache = None
    return load_config()
