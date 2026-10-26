"""Start Mihomo in isolation and verify rendered proxy-group membership."""

from __future__ import annotations

import json
import os
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
    else ROOT / "sublink" / "mihomo_fakeip_rule.rendered.yaml"
)
RUNTIME_TEMP = TemporaryDirectory(prefix="sublinkpro-mihomo-runtime-")
RUNTIME_CONFIG = Path(RUNTIME_TEMP.name) / "runtime-validation.yaml"
RUNTIME_HOME = Path(os.environ.get("MIHOMO_TEST_HOME", RUNTIME_TEMP.name))
RUNTIME_LOG = Path(RUNTIME_TEMP.name) / "runtime-validation.log"
SELF_GROUPS = {"自建节点", "自建选1", "自建选2", "自建选3"}
SELF_SLOTS = ["自建选1", "自建选2", "自建选3"]
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
            version = api_get(port, "/version")
            if "自建选3" not in (api_get(port, "/proxies").get("proxies") or {}):
                time.sleep(0.25)
                continue
            return version
        except Exception as error:  # The listener may not exist yet.
            last_error = error
            time.sleep(0.25)
    raise TimeoutError(f"Mihomo API was not ready: {last_error}")


def token_members(names: set[str], *tokens: str) -> set[str]:
    pattern = re.compile(r"(?:^| )(?:" + "|".join(map(re.escape, tokens)) + r")(?: |#|$)")
    return {name for name in names if pattern.search(name)}


def expected_groups(names: list[str], self_names: list[str]) -> dict[str, list[str]]:
    expected: dict[str, list[str]] = {}
    name_set = set(names)
    self_built = set(self_names)
    home = token_members(name_set, "家宽") - self_built
    eligible = name_set - home - self_built
    region_flags = {"US": "🇺🇸", "HK": "🇭🇰", "SG": "🇸🇬", "JP": "🇯🇵"}
    regions = {
        code: {name for name in eligible if name.startswith(flag)}
        for code, flag in region_flags.items()
    }
    other = {name for name in eligible if not name.startswith(tuple(region_flags.values()))}

    expected["自动选择"] = sorted(eligible)
    expected["全部手选"] = sorted(name_set)
    expected["地区手选"] = sorted(name_set)

    for mode in ("负载均衡", "自动测速", "故障转移"):
        for code, members in regions.items():
            expected[f"{mode}-{code}"] = sorted(members)
        expected[f"{mode}-其他"] = sorted(other)

    manual_patterns = {
        "US": r"🇺🇸|美国|美國|US|united\s?states|america|usa|洛杉矶|达拉斯|纽约|西雅图|New\s?York",
        "HK": r"🇭🇰|香港|HK|hong\s?kong",
        "SG": r"🇸🇬|新加坡|狮城|SG|Singapore",
        "JP": r"🇯🇵|日本|東京|东京|JP|japan|tokyo|osaka",
    }
    manual_regions = {
        code: {name for name in name_set if re.search(pattern, name, re.IGNORECASE)}
        for code, pattern in manual_patterns.items()
    }
    for code, members in manual_regions.items():
        expected[f"手选-{code}"] = sorted(members)
    expected["手选-其他"] = sorted(name_set - set().union(*manual_regions.values()))

    for name in SELF_GROUPS:
        expected[name] = sorted(self_built)
    expected["家宽手选"] = [name for name in names if name in home] + self_names
    expected["流媒体解锁"] = sorted(name for name in name_set if re.search(r"流媒体|解锁|IEPL|专线|Premium|网飞|Netflix|Disney|HBO", name, re.IGNORECASE))
    return expected


def main() -> None:
    config = load_mapping(RENDERED)
    controller_port, mixed_port, redir_port, tproxy_port = (free_port() for _ in range(4))

    config["routing-mark"] = 0
    config["allow-lan"] = False
    config["bind-address"] = "127.0.0.1"
    config["external-controller"] = f"127.0.0.1:{controller_port}"
    config["secret"] = API_SECRET
    config["mixed-port"] = mixed_port
    config["redir-port"] = redir_port
    config["tproxy-port"] = tproxy_port
    config.setdefault("tun", {})["enable"] = False
    config.setdefault("dns", {})["listen"] = f"127.0.0.1:{free_port()}"
    config.setdefault("profile", {})["store-selected"] = False
    config["external-ui"] = ""
    config["external-ui-url"] = ""
    RUNTIME_CONFIG.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with RUNTIME_LOG.open("wb") as log:
        process = subprocess.Popen(
            [
                os.environ.get("MIHOMO_BINARY", "mihomo"),
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
            self_group = next(group for group in config["proxy-groups"] if group["name"] == "自建节点")
            expected = expected_groups(proxy_names, self_group.get("proxies") or [])

            for group in config.get("proxy-groups") or []:
                if group["name"] in expected and group.get("type") == "select" and group["name"] not in SELF_GROUPS | {"家宽手选"}:
                    expected[group["name"]] = list(group.get("proxies") or []) + expected[group["name"]]
                if group["name"] not in expected:
                    if group.get("include-all"):
                        raise ValueError(f"Missing membership expectation: {group['name']}")
                    expected[group["name"]] = list(group.get("proxies") or [])

            checks: dict[str, dict[str, Any]] = {}
            failures: list[str] = []
            for group_name, expected_members in expected.items():
                # Mihomo supplies COMPATIBLE when a dynamic group has no matching nodes.
                expected_members = expected_members or ["COMPATIBLE"]
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

            claude = runtime_proxies.get("Claude") or {}
            ai = runtime_proxies.get("AI") or {}
            if claude.get("type") != "Selector" or claude.get("all") != ai.get("all"):
                failures.append("Claude-service-selector")
            for name, expected_default in {"AI": "PROXY", "Claude": "PROXY", "跨境金融": "PROXY", "STUN": "PROXY", "TikTok": "DIRECT", "海淘购物": "PROXY", "IP池": "PROXY"}.items():
                if runtime_proxies.get(name, {}).get("now") != expected_default:
                    failures.append(f"{name}-default")
            if runtime_proxies.get("海淘购物", {}).get("all", [])[:3] != ["PROXY", "DIRECT", "自动选择"]:
                failures.append("shopping-candidate-order")
            if {"AI优选", "AI稳定", "Gemini", "OpenAI", "通用"}.intersection(runtime_proxies):
                failures.append("removed-AI-node-groups")

            home_names = set(expected["家宽手选"]) - set(self_group.get("proxies") or [])
            defined_group_names = {
                str(group.get("name", ""))
                for group in config.get("proxy-groups") or []
                if isinstance(group, dict) and group.get("name")
            }
            manual_group_names = {name for name in defined_group_names if "手选" in name or name == "流媒体解锁"}
            home_membership_violations = {
                group_name: sorted(
                    home_names.intersection(
                        set((runtime_proxies.get(group_name) or {}).get("all") or [])
                    )
                )
                for group_name in sorted(defined_group_names - manual_group_names)
                if home_names.intersection(
                    set((runtime_proxies.get(group_name) or {}).get("all") or [])
                )
            }
            if home_membership_violations:
                failures.append("home-membership-exclusivity")

            self_names = set(expected["自建节点"])
            self_membership_violations = {
                group_name: sorted(self_names.intersection(
                    set((runtime_proxies.get(group_name) or {}).get("all") or [])
                ))
                for group_name in sorted(defined_group_names - SELF_GROUPS - manual_group_names)
                if self_names.intersection(
                    set((runtime_proxies.get(group_name) or {}).get("all") or [])
                )
            }
            if self_membership_violations:
                failures.append("self-membership-exclusivity")

            result = {
                "mihomo": version,
                "process_started": process.poll() is None,
                "runtime_group_count": sum(
                    isinstance(value, dict) and "all" in value for value in runtime_proxies.values()
                ),
                "verified_group_count": len(checks),
                "all_memberships_exact": not failures,
                "failures": failures,
                "home_membership_exclusivity": {
                    "exclusive": not home_membership_violations,
                    "checked_group_count": len(defined_group_names) - 1,
                    "violations": home_membership_violations,
                },
                "self_membership_exclusivity": {
                    "exclusive": not self_membership_violations,
                    "checked_group_count": len(defined_group_names) - len(SELF_GROUPS),
                    "violations": self_membership_violations,
                },
                "groups": checks,
                "claude": {
                    "type": claude.get("type"),
                    "now": claude.get("now"),
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
