import json
import threading
from pathlib import Path
from typing import Any, Dict


_DATA_PATH = Path(__file__).parent / "users.json"
_LOCK = threading.Lock()


def _load_all() -> Dict[str, Any]:
    if not _DATA_PATH.exists():
        return {}
    try:
        with _DATA_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Corrupt or empty file; start fresh.
        return {}


def _save_all(data: Dict[str, Any]) -> None:
    tmp_path = _DATA_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    tmp_path.replace(_DATA_PATH)


def get_user_settings(user_id: int) -> Dict[str, Any]:
    """
    Retrieve settings for a given user ID.
    """
    with _LOCK:
        data = _load_all()
        return data.get(str(user_id), {})


def set_user_timezone(user_id: int, timezone_code: str) -> None:
    """
    Persist the user's preferred timezone code.
    """
    with _LOCK:
        data = _load_all()
        user = data.get(str(user_id), {})
        user["timezone"] = timezone_code
        data[str(user_id)] = user
        _save_all(data)

