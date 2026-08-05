"""Start Mihomo in isolation and verify rendered proxy-group membership."""

from __future__ import annotations

import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from typing import Any
from urllib.request import Request, urlopen

import yaml


ROOT = Path(__file__).resolve().parents[2]
RENDERED = (
    Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else ROOT / "sublink" / "mihomo_fakeip_whitelist.rendered.yaml"
)
RUNTIME_TEMP = TemporaryDirectory(prefix="sublinkpro-mihomo-runtime-")
RUNTIME_CONFIG = Path(RUNTIME_TEMP.name) / "runtime-validation.yaml"
RUNTIME_HOME = ROOT / ".planning" / "sublinkpro-mihomo-template" / "mihomo-home"
RUNTIME_LOG = Path(RUNTIME_TEMP.name) / "runtime-validation.log"
API_SECRET = "sublinkpro-runtime-validation"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def load_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not a YAML mapping")
    return value


def api_get(port: int, path: str) -> dict[str, Any]:
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        headers={"Authorization": f"Bearer {API_SECRET}"},
    )
    with urlopen(request, timeout=3) as response:
        return json.load(response)


def wait_for_api(process: subprocess.Popen[bytes], port: int) -> dict[str, Any]:
    deadline = time.monotonic() + 40
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Mihomo exited before API readiness (code {process.returncode})")
        try:
            return api_get(port, "/version")
        except Exception as error:  # The listener may not exist yet.
            last_error = error
            time.sleep(0.25)
    raise TimeoutError(f"Mihomo API was not ready: {last_error}")


def token_members(names: set[str], *tokens: str) -> set[str]:
    pattern = re.compile(r"(?:^| )(?:" + "|".join(map(re.escape, tokens)) + r")(?: |#|$)")
    return {name for name in names if pattern.search(name)}


def expected_groups(names: list[str]) -> dict[str, list[str]]:
    expected: dict[str, list[str]] = {}
    name_set = set(names)
    home = token_members(name_set, "家宽")
    eligible = name_set - home
    region_flags = {"US": "🇺🇸", "HK": "🇭🇰", "SG": "🇸🇬", "JP": "🇯🇵"}
    regions = {
        code: {name for name in eligible if name.startswith(flag)}
        for code, flag in region_flags.items()
    }
    other = {name for name in eligible if not name.startswith(tuple(region_flags.values()))}

    expected["自动选择"] = sorted(eligible)
    expected["全部手选"] = sorted(eligible)

    for mode in ("手选", "负载均衡", "自动测速", "故障转移"):
        for code, members in regions.items():
            expected[f"{mode}-{code}"] = sorted(members)
        expected[f"{mode}-其他"] = sorted(other)

    expected["自建手选"] = sorted(token_members(eligible, "自建"))
    expected["家宽手选"] = [name for name in names if token_members({name}, "家宽")]
    expected["Claude"] = sorted(token_members(eligible, "AI", "Claude"))
    expected["Gemini"] = sorted(token_members(eligible, "AI", "Gemini"))
    expected["OpenAI"] = sorted(token_members(eligible, "AI", "OpenAI"))
    expected["通用"] = sorted(token_members(eligible, "AI"))
    expected["流媒体解锁"] = sorted(token_members(eligible, "Netflix"))
    return expected


def main() -> None:
    config = load_mapping(RENDERED)
    controller_port, mixed_port, redir_port, tproxy_port = (free_port() for _ in range(4))

    config["allow-lan"] = False
    config["bind-address"] = "127.0.0.1"
    config["external-controller"] = f"127.0.0.1:{controller_port}"
    config["secret"] = API_SECRET
    config["mixed-port"] = mixed_port
    config["redir-port"] = redir_port
    config["tproxy-port"] = tproxy_port
    config.setdefault("tun", {})["enable"] = False
    RUNTIME_CONFIG.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with RUNTIME_LOG.open("wb") as log:
        process = subprocess.Popen(
            [
                "mihomo",
                "-d",
                str(RUNTIME_HOME),
                "-f",
                str(RUNTIME_CONFIG),
                "-ext-ctl",
                f"127.0.0.1:{controller_port}",
                "-secret",
                API_SECRET,
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )

        try:
            version = wait_for_api(process, controller_port)
            proxy_payload = api_get(controller_port, "/proxies")
            runtime_proxies = proxy_payload.get("proxies") or {}
            proxy_names = [
                str(proxy.get("name", ""))
                for proxy in config.get("proxies") or []
                if isinstance(proxy, dict) and proxy.get("name")
            ]
            expected = expected_groups(proxy_names)

            checks: dict[str, dict[str, Any]] = {}
            failures: list[str] = []
            for group_name, expected_members in expected.items():
                runtime_group = runtime_proxies.get(group_name) or {}
                actual_members = list(runtime_group.get("all") or [])
                expected_set = set(expected_members)
                actual_set = set(actual_members)
                exact = expected_set == actual_set and len(actual_members) == len(actual_set)
                order_exact = group_name != "家宽手选" or actual_members == expected_members
                checks[group_name] = {
                    "type": runtime_group.get("type"),
                    "expected": len(expected_set),
                    "actual": len(actual_members),
                    "exact": exact,
                    "order_exact": order_exact,
                    "missing": len(expected_set - actual_set),
                    "extra": len(actual_set - expected_set),
                }
                if not exact or not order_exact:
                    failures.append(group_name)

            ai_preferred = runtime_proxies.get("AI优选") or {}
            ai_order = list(ai_preferred.get("all") or [])
            expected_ai_order = ["通用", "Claude", "Gemini", "OpenAI"]
            if ai_order != expected_ai_order:
                failures.append("AI优选-order")

            home_names = set(expected["家宽手选"])
            defined_group_names = {
                str(group.get("name", ""))
                for group in config.get("proxy-groups") or []
                if isinstance(group, dict) and group.get("name")
            }
            home_membership_violations = {
                group_name: sorted(
                    home_names.intersection(
                        set((runtime_proxies.get(group_name) or {}).get("all") or [])
                    )
                )
                for group_name in sorted(defined_group_names - {"家宽手选"})
                if home_names.intersection(
                    set((runtime_proxies.get(group_name) or {}).get("all") or [])
                )
            }
            if home_membership_violations:
                failures.append("home-membership-exclusivity")

            result = {
                "mihomo": version,
                "process_started": process.poll() is None,
                "runtime_group_count": sum(
                    isinstance(value, dict) and "all" in value for value in runtime_proxies.values()
                ),
                "verified_group_count": len(checks) + 1,
                "all_memberships_exact": not failures,
                "failures": failures,
                "home_membership_exclusivity": {
                    "exclusive": not home_membership_violations,
                    "checked_group_count": len(defined_group_names) - 1,
                    "violations": home_membership_violations,
                },
                "groups": checks,
                "ai_preferred": {
                    "type": ai_preferred.get("type"),
                    "order": ai_order,
                    "now": ai_preferred.get("now"),
                },
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if failures:
                raise SystemExit(1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
