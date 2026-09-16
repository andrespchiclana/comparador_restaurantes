import hashlib
import pickle
import time
from pathlib import Path


CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_TTL_SECONDS = 12 * 60 * 60


def _cache_path(nombre_fuente, *partes_clave):
    CACHE_DIR.mkdir(exist_ok=True)
    clave = "|".join(str(p) for p in (nombre_fuente, *partes_clave))
    digest = hashlib.sha256(clave.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{nombre_fuente}_{digest}.pkl"


def _leer_cache(path):
    if not path.exists():
        return None

    try:
        with path.open("rb") as f:
            payload = pickle.load(f)
    except (OSError, pickle.PickleError, EOFError):
        return None

    if not isinstance(payload, dict):
        return None
    if time.time() - payload.get("created_at", 0) > CACHE_TTL_SECONDS:
        return None
    return payload.get("data")


def _guardar_cache(path, data):
    try:
        with path.open("wb") as f:
            pickle.dump({"created_at": time.time(), "data": data}, f)
    except OSError as exc:
        print(f"Aviso: no se pudo escribir cache {path.name}: {exc}")


def obtener_con_cache(nombre_fuente, fetcher, *args):
    path = _cache_path(nombre_fuente, *args)
    data_cacheada = _leer_cache(path)
    if data_cacheada is not None:
        return data_cacheada

    try:
        data = fetcher(*args) or []
    except Exception as exc:
        print(f"Error en {nombre_fuente}: {exc}")
        return []

    if data:
        _guardar_cache(path, data)
    return data


def borrar_cache():
    if not CACHE_DIR.exists():
        return 0

    eliminados = 0
    for path in CACHE_DIR.glob("*.pkl"):
        try:
            path.unlink()
            eliminados += 1
        except OSError as exc:
            print(f"Aviso: no se pudo borrar cache {path.name}: {exc}")

    return eliminados
