"""Enforces the clean-architecture dependency rules (see docs/ARCHITECTURE.md).

    interfaces  ->  application  ->  domain
    infrastructure  ->  domain
    container (composition root) may import everything

Fails if an inner layer imports a framework, a database driver, or an outer layer.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"

# Third-party technology that must stay out of the inner layers.
TECHNOLOGY = ("fastapi", "starlette", "pydantic", "pymongo", "bson", "motor", "cloudinary", "google")
# Legacy packages that predate the migration (outer-layer or mixed code).
LEGACY = ("app.api", "app.services", "app.repositories", "app.db", "app.backend", "app.config")

RULES = {
    "domain": TECHNOLOGY + LEGACY + ("app.application", "app.infrastructure", "app.interfaces", "app.container"),
    "application": TECHNOLOGY + LEGACY + ("app.infrastructure", "app.interfaces", "app.container"),
    "infrastructure": ("fastapi", "starlette", "app.interfaces", "app.application"),
}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def _violations(layer: str) -> list[str]:
    forbidden = RULES[layer]
    found = []
    for path in sorted((APP / layer).rglob("*.py")):
        for name in _imports(path):
            if any(name == f or name.startswith(f + ".") for f in forbidden):
                found.append(f"{path.relative_to(APP.parent)} imports {name}")
    return found


@pytest.mark.parametrize("layer", sorted(RULES))
def test_layer_dependencies(layer):
    assert (APP / layer).is_dir(), f"missing layer app/{layer}"
    assert _violations(layer) == []
