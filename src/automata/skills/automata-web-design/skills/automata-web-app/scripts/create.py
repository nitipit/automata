"""Copy the webapp example into a new owned directory; never modify installed assets."""

import argparse
import json
import shutil
from pathlib import Path


def create(output: Path, adaptive_ui: Path) -> None:
    skill = Path(__file__).resolve().parents[1]
    adaptive_ui = adaptive_ui.expanduser().resolve()
    source = skill / "examples/webapp"
    config = json.loads((source / "deno.json").read_text())
    for name, value in config["imports"].items():
        if name.startswith("@adaptive/"):
            relative = Path(value).relative_to("../../../automata-adaptive-ui")
            target = adaptive_ui / relative
            if not target.is_file():
                raise FileNotFoundError(f"Missing Adaptive UI source: {target}")
            config["imports"][name] = target.as_uri()
    if output.exists():
        raise FileExistsError(f"Destination already exists: {output}")
    shutil.copytree(source, output, ignore=shutil.ignore_patterns(
        "node_modules", "browser", ".venv", "__pycache__", "*.pyc",
    ))
    (output / "deno.json").write_text(json.dumps(config, indent=2) + "\n")
    print(f"Created {output}; Adaptive UI source dependency: {adaptive_ui}")


if __name__ == "__main__":
    skill = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="New task-owned project directory (must not exist)")
    parser.add_argument("--adaptive-ui", type=Path,
                        default=skill.parent / "automata-adaptive-ui",
                        help="Adaptive UI skill directory; defaults to sibling skill")
    args = parser.parse_args()
    create(args.output.expanduser().absolute(), args.adaptive_ui)
