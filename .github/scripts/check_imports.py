"""Import all fidbox integration modules against the installed Home Assistant.

Installs any missing transitive dependency (from HA component manifests)
and retries, so a missing module fails loudly instead of silently passing.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

MODULES = (
    "custom_components.fidbox",
    "custom_components.fidbox.sensor",
    "custom_components.fidbox.config_flow",
    "custom_components.fidbox.const",
)


def install_missing(module_name: str) -> None:
    """Install the requirement that provides a missing module."""
    import homeassistant

    comps = Path(homeassistant.__file__).parent / "components"
    for comp in sorted(comps.iterdir()):
        manifest = comp / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            reqs = json.loads(manifest.read_text()).get("requirements", [])
        except json.JSONDecodeError:
            continue
        for req in reqs:
            base = req.split(" ")[0].split("==")[0].split("@")[-1].strip()
            if base.replace("-", "_").lower() == module_name.replace("_", "-").lower():
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", req], check=True
                )
                print(f"installed {req} for missing module {module_name}")
                return
    raise SystemExit(f"Cannot find a requirement providing module {module_name}")


def main() -> int:
    import homeassistant.components.bluetooth  # noqa: F401  # pulls in deps

    for module in MODULES:
        importlib.import_module(module)
        print(f"imported {module}")
    return 0


if __name__ == "__main__":
    for _ in range(20):
        try:
            raise SystemExit(main())
        except ModuleNotFoundError as err:
            name = err.name or ""
            if not name:
                raise
            print(f"missing module: {name}")
            install_missing(name)
    raise SystemExit("imports kept failing after installing dependencies")
