from pathlib import Path
from typing import Callable

def cache_output_text(fn: Callable[[], str], path: Path):
    if path.exists():
        return path.read_text()
    else:
        result = fn()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result)
        return result
