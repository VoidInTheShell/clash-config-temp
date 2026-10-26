"""Verify node-only manual selectors using a real, isolated Mihomo process.

All node endpoints are local fixtures. No subscriptions or rule downloads are used.
Panel input is expanded with its documented regex placeholder semantics; Sublink
input passes through the repository's actual subMod hook before kernel startup.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import socket
import subprocess
from tempfile import TemporaryDirectory
import time
from urllib.parse import quote
from urllib.request import urlopen

import yaml

from validate_templates import FILES, ROOT


def fixtures():
    # Include arbitrary self names, names matching old info-node exclusions,
    # residential airport nodes, and an English region name containing a space.
    return [
        ("JP Netflix", "JP", "self", False),
        ("独立出口", "其他", "self", False),
        ("US1-纽约-解锁", "US", "self", False),
        ("官网节点", "其他", "self", False),
        ("🇺🇸 美国 家宽 Netflix", "US", "airport", True),
        ("🇭🇰 香港 家宽", "HK", "airport", True),
        ("🇺🇸 美国 普通", "US", "airport", False),
        ("🇸🇬 新加坡 netflix", "SG", "airport", False),
        ("🇯🇵 日本 Disney+", "JP", "airport", False),
        ("🇩🇪 德国 普通", "其他", "airport", False),
        ("standalone hong kong", "HK", "standalone", False),
    ]


def proxy(name):
    return {"name": name, "type": "socks5", "server": "127.0.0.1", "port": 9}


def render(filename, directory):
    config = yaml.safe_load((ROOT / filename).read_text(encoding="utf-8"))
    groups = deepcopy(config["proxy-groups"])
    records = fixtures()
    providers = {}
    if filename.startswith("multi_"):
        self_names = config["u_s"]
        airport_names = config["u"]
        assignments = {name: [] for name in self_names + airport_names}
        for index, (name, _, source, _) in enumerate(records):
            if source == "standalone":
                continue
            owner = self_names[0] if source == "self" else airport_names[index % len(airport_names)]
            assignments[owner].append(proxy(name))
        for index, (name, nodes) in enumerate(assignments.items()):
            path = directory / f"provider-{index}.yaml"
            path.write_text(yaml.safe_dump({"proxies": nodes}, allow_unicode=True), encoding="utf-8")
            providers[name] = {"type": "file", "path": str(path), "health-check": {"enable": False}}
        proxies = [proxy(name) for name, _, source, _ in records if source == "standalone"]
    elif filename.startswith("panel_"):
        names = [record[0] for record in records]
        for group in groups:
            members = group.get("proxies") or []
            expanded = []
            if not members:
                expanded = names[:]
            for member in members:
                if member.startswith("/") and member.endswith("/"):
                    expanded.extend(name for name in names if re.search(member[1:-1], name))
                else:
                    expanded.append(member)
            group["proxies"] = list(dict.fromkeys(expanded))
        proxies = [proxy(name) for name in names]
    else:
        records = [record for record in records if record[2] != "standalone"]
        proxies = []
        for name, _, source, _ in records:
            if source == "self":
                name = "__SUBLINK_SELF_NAME_" + quote(name, safe="") + "__END_SELF_NAME__"
            proxies.append(proxy(name))
        input_path, output_path = directory / "input.yaml", directory / "output.yaml"
        input_path.write_text(yaml.safe_dump({"proxies": proxies, "proxy-groups": groups}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        subprocess.run(["node", str(ROOT / "sublink/tools/run_submod.mjs"), str(input_path), str(output_path)], check=True, capture_output=True)
        rendered = yaml.safe_load(output_path.read_text(encoding="utf-8"))
        groups, proxies = rendered["proxy-groups"], rendered["proxies"]

    for group in groups:
        # Disable scheduled health probes; only group membership is exercised.
        if group.get("type") in {"url-test", "load-balance", "fallback"}:
            group["interval"] = 0
            group["lazy"] = True
    runtime = {
        "proxies": proxies,
        "proxy-groups": groups,
        "rule-providers": {"VoidSTUN": {"type": "inline", "behavior": "domain", "payload": ["stun.fixture.test"]}},
        "rules": ["RULE-SET,VoidSTUN,STUN", "MATCH,DIRECT"],
        "mode": "rule", "log-level": "error", "allow-lan": False,
        "profile": {"store-selected": False},
    }
    if providers:
        runtime["proxy-providers"] = providers
    return runtime, records


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def check(filename):
    with TemporaryDirectory(prefix="mihomo-manual-groups-") as temp:
        directory = Path(temp)
        config, records = render(filename, directory)
        port = free_port()
        config["external-controller"] = f"127.0.0.1:{port}"
        path = directory / "config.yaml"
        path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        binary = os.environ.get("MIHOMO_BINARY", "mihomo")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        syntax = subprocess.run([binary, "-d", str(directory), "-f", str(path), "-t"], capture_output=True, creationflags=flags)
        assert syntax.returncode == 0, syntax.stdout.decode("utf-8", errors="replace") + syntax.stderr.decode("utf-8", errors="replace")
        names = {record[0] for record in records}
        group_names = {group["name"] for group in config["proxy-groups"]}
        manual_names = {name for name in group_names if "手选" in name or name == "流媒体解锁"}
        self_names = {record[0] for record in records if record[2] == "self"}
        with (directory / "runtime.log").open("wb") as log:
            process = subprocess.Popen([binary, "-d", str(directory), "-f", str(path)], stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError((directory / "runtime.log").read_text(encoding="utf-8"))
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/proxies", timeout=0.5) as response:
                            runtime = json.load(response)["proxies"]
                        if set(runtime.get("全部手选", {}).get("all") or []) == names:
                            break
                    except (OSError, ValueError):
                        pass
                    time.sleep(0.1)
                else:
                    raise AssertionError(f"{filename}: manual node list not ready")
                for name in manual_names:
                    actual = runtime[name]["all"]
                    if name in {"全部手选", "地区手选"}:
                        expected = names
                    elif name == "流媒体解锁":
                        expected = {record[0] for record in records if re.search(r"流媒体|解锁|IEPL|专线|Premium|网飞|Netflix|Disney|HBO", record[0], re.IGNORECASE)}
                    elif name == "家宽手选":
                        expected = self_names | {record[0] for record in records if record[3]}
                    else:
                        region = name.removeprefix("手选-")
                        expected = {record[0] for record in records if record[1] == region}
                    assert set(actual) == expected, (filename, name, "missing", expected - set(actual), "extra", set(actual) - expected)
                    assert len(actual) == len(set(actual)), (filename, name, "duplicate node")
                    assert not group_names.intersection(actual), (filename, name, "group reference")
                    assert runtime[name]["type"] == "Selector", (filename, name)
                if filename.startswith("multi_"):
                    for name in ["自建节点", "自建选1", "自建选2", "自建选3"]:
                        assert set(runtime[name]["all"]) == self_names, (filename, name)
                    for group in config["proxy-groups"]:
                        if group.get("use") == yaml.safe_load((ROOT / filename).read_text(encoding="utf-8"))["u"]:
                            assert not self_names.intersection(runtime[group["name"]]["all"]), (filename, group["name"])
                if filename.startswith("sublink/"):
                    for group in config["proxy-groups"]:
                        if group.get("type") in {"url-test", "load-balance", "fallback"}:
                            assert not self_names.intersection(runtime[group["name"]]["all"]), (filename, group["name"])
                for name, target in {"AI": "PROXY", "Claude": "PROXY", "跨境金融": "PROXY", "IP池": "PROXY", "STUN": "PROXY", "TikTok": "DIRECT", "海淘购物": "PROXY"}.items():
                    assert runtime[name]["now"] == target, (filename, name, "initial selection")
                assert runtime["海淘购物"]["all"][:3] == ["PROXY", "DIRECT", "自动选择"], filename
                with urlopen(f"http://127.0.0.1:{port}/rules", timeout=1) as response:
                    rules = json.load(response)["rules"]
                assert any(rule.get("proxy") == "STUN" and rule.get("payload") == "VoidSTUN" for rule in rules), filename
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        print(f"PASS {filename}: {len(manual_names)} live node-only selectors, {len(names)} fixture nodes, STUN routing")


if __name__ == "__main__":
    for filename in FILES:
        check(filename)
