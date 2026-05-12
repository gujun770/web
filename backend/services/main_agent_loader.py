from __future__ import annotations

import importlib
import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_PACKAGE_DIR = PROJECT_ROOT / "main"
AGENT_ALIAS = "news_agent_main"


def ensure_agent_package_loaded() -> str:
    if AGENT_ALIAS in sys.modules:
        return AGENT_ALIAS

    init_file = AGENT_PACKAGE_DIR / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        AGENT_ALIAS,
        init_file,
        submodule_search_locations=[str(AGENT_PACKAGE_DIR)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载新闻 Agent 包：{AGENT_PACKAGE_DIR}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[AGENT_ALIAS] = module
    spec.loader.exec_module(module)
    return AGENT_ALIAS


def import_agent_module(module_name: str):
    package_name = ensure_agent_package_loaded()
    return importlib.import_module(f"{package_name}.{module_name}")


@lru_cache(maxsize=1)
def get_react_agent() -> Any:
    module = import_agent_module("agent.react_agent")
    return module.ReactAgent()


def rebuild_news_vector_store(limit: int = 200) -> dict[str, int]:
    module = import_agent_module("rag.vector_store")
    return module.rebuild_news_vector_store(limit=limit)
