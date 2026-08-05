"""Pass file contents to the existing SublinkPro helper without command-line expansion."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HELPER = Path(r"C:\Users\27323\.codex\skills\sublinkpro\scripts\sublink.py")


def main() -> None:
    spec = importlib.util.spec_from_file_location("sublink_skill_helper", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load SublinkPro helper: {HELPER}")

    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    args = sys.argv[1:]
    expanded: list[str] = []
    index = 0
    while index < len(args):
        if args[index] not in {"--form-file", "--json-file"}:
            expanded.append(args[index])
            index += 1
            continue

        if index + 1 >= len(args) or "=" not in args[index + 1]:
            raise SystemExit(f"{args[index]} requires key=path")
        output_flag = "--form" if args[index] == "--form-file" else "--json"
        key, raw_path = args[index + 1].split("=", 1)
        value = Path(raw_path).read_text(encoding="utf-8")
        expanded.extend((output_flag, f"{key}={value}"))
        index += 2

    sys.argv = [str(HELPER), *expanded]
    helper.main()


if __name__ == "__main__":
    main()
