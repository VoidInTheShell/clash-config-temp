"""Validate maintained template source boundaries and self-built selectors."""
from pathlib import Path
import json
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
SLOTS = ["自建选1", "自建选2", "自建选3"]
SELF_GROUPS = ["自建节点", *SLOTS]
PANEL_GROUPS = [f"自选{i}" for i in range(1, 5)]
REMOVED_AI_GROUPS = {"AI优选", "AI稳定", "Gemini", "OpenAI", "通用"}
FILES = [
    "multi_providers_mihomo.yaml",
    "multi_providers_mihomo_fakeip_whitelist.yaml",
    "multi_providers_mihomo_fakeip_rule.yaml",
    "panel_mihomo_fakeip_rule.yaml",
    "sublink/sublinkpro_mihomo_fakeip_rule.yaml",
]

CLAUDE_DNS_OVERLAP_PROVIDER = "VoidAClaudeOverlap"


class UniqueLoader(yaml.SafeLoader):
    """Reject repeated keys, allowing YAML merge keys."""


def mapping(loader, node, deep=False):
    keys = [key.value for key, _ in node.value if key.value != "<<"]
    assert len(keys) == len(set(keys)), f"Duplicate YAML key at line {node.start_mark.line + 1}"
    loader.flatten_mapping(node)
    return loader.construct_mapping(node, deep=deep)


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def validate(filename):
    config = yaml.load((ROOT / filename).read_text(), Loader=UniqueLoader)
    groups = config["proxy-groups"]
    group_map = {g["name"]: g for g in groups}
    assert len(groups) == len(group_map), "Duplicate group name"
    names = list(group_map)
    panel = filename.startswith("panel_")
    selectors = PANEL_GROUPS if panel else SELF_GROUPS
    slots = PANEL_GROUPS[:3] if panel else SLOTS
    start = names.index(selectors[0])
    assert names[start:start + 4] == selectors
    assert "自建手选" not in names and "家宽节点" not in names
    assert not REMOVED_AI_GROUPS.intersection(names)
    if panel:
        assert not any(name.startswith(("自建", "自动测速-")) for name in names)
        assert [g["name"] for g in groups if g["type"] == "url-test"] == ["自动选择"]
    for group in groups:
        members = group.get("proxies") or []
        assert len(members) == len(set(members)), group["name"]
        if group["name"] in selectors:
            assert group["type"] == "select"
            assert not set(selectors).intersection(members), "Selector cycle"
            assert not any(k in group for k in ("filter", "exclude-filter", "exclude-type"))
        elif group["type"] == "select":
            assert set(selectors if panel else slots).issubset(members), group["name"]
            if set(selectors).issubset(members):
                i = members.index(selectors[0])
                assert members[i:i + 4] == selectors, group["name"]
        else:
            assert not set(slots).intersection(members), group["name"]
        for member in members:
            assert member in group_map or member in {"DIRECT", "REJECT"} or (
                filename.startswith("panel_") and member.startswith("/") and member.endswith("/")
            ), (group["name"], member)
    # Every possible group reference must be acyclic, not only the default path.
    def visit(name, stack):
        assert name not in stack, f"Group cycle: {stack + [name]}"
        for member in group_map[name].get("proxies") or []:
            if member in group_map:
                visit(member, stack + [name])
    for name in names:
        visit(name, [])
    assert group_map["IP池"]["proxies"] == ["PROXY", *group_map["PROXY"]["proxies"]]
    assert group_map["IP池"]["default-selected"] == "PROXY"
    for name, slot in {"AI": slots[0], "Claude": slots[0], "TikTok": slots[1], "跨境金融": slots[2]}.items():
        assert group_map[name]["default-selected"] == slot
    assert names[names.index("AI") + 1] == "Claude"
    comparable = lambda group: {k: v for k, v in group.items() if k not in {"name", "icon"}}
    assert comparable(group_map["AI"]) == comparable(group_map["Claude"])
    assert "claude" in group_map["Claude"]["icon"].lower()
    if filename.startswith("multi_"):
        self_providers = config["u_s"]
        airports = config["u"]
        assert len(self_providers) == 1 and not set(self_providers).intersection(airports)
        assert set(config["proxy-providers"]) == set(self_providers + airports)
        for group in groups:
            assert not group.get("include-all"), group["name"]
            if group["name"] in SELF_GROUPS:
                assert group["use"] == self_providers and not group.get("filter")
                assert not group.get("proxies")
            elif group.get("use"):
                assert group["use"] == airports, group["name"]
    else:
        assert "proxy-providers" not in config
        assert all("use" not in group for group in groups)
        for name in selectors:
            assert group_map[name]["proxies"] == []
    if config["dns"]["fake-ip-filter-mode"] == "rule":
        assert config["dns"]["fake-ip-filter-mode"] == "rule"
        assert config["dns"]["fake-ip-filter"] == [
            "RULE-SET,VoidClaude,fake-ip",
            "RULE-SET,VoidSTUN,fake-ip",
            *(["RULE-SET,VoidFakeIPForce,fake-ip"] if "fakeip_rule" in filename else []),
            "RULE-SET,VoidFakeIPBypass,real-ip",
            "MATCH,fake-ip",
        ]
    else:
        assert config["dns"]["fake-ip-filter-mode"] == "whitelist"
        assert config["dns"]["fake-ip-filter"] == [
            "rule-set:VoidClaude", "rule-set:VoidSTUN", "rule-set:VoidFakeIPForce",
        ]
    referenced_filters = set()
    for entry in config["dns"]["fake-ip-filter"]:
        if entry.startswith("RULE-SET,"):
            referenced_filters.add(entry.split(",")[1])
        elif entry.startswith("rule-set:"):
            referenced_filters.update(entry.removeprefix("rule-set:").split(","))
    for name in referenced_filters:
        assert config["rule-providers"][name]["behavior"] == "domain"
    for name, path in {
        "VoidAClaudeOverlap": "void-claude-ai-overlap",
        "VoidClaude": "void-claude-rules",
        "VoidSTUN": "stun",
    }.items():
        provider = config["rule-providers"][name]
        assert provider["format"] == "mrs"
        assert provider["url"].endswith(f"/dist/{path}/mihomo-domain.mrs")
    policy = config["dns"]["nameserver-policy"]
    assert policy["rule-set:VoidClaude"] == [s.replace("#AI", "#Claude") for s in policy["rule-set:VoidAI"]]
    overlap_key = f"rule-set:{CLAUDE_DNS_OVERLAP_PROVIDER}"
    assert overlap_key in policy
    assert policy[overlap_key] == policy["rule-set:VoidClaude"]
    # Xboard/Sublink may sort mapping keys. The generated overlap rule must
    # still precede VoidAI after that transformation.
    sorted_policy_keys = sorted(policy)
    assert sorted_policy_keys.index(overlap_key) < sorted_policy_keys.index("rule-set:VoidAI")
    assert config["rules"].index("RULE-SET,VoidClaude,Claude") < config["rules"].index("RULE-SET,VoidAI,AI")
    assert config["rules"][config["rules"].index("RULE-SET,VoidCrossBorderFinance,跨境金融") + 1] == "RULE-SET,VoidClaude,Claude"
    assert "DOMAIN-SUFFIX,ippure.com,IPCheck,no-resolve" in config["rules"]
    # Rule-set references and DNS-selected group names must resolve.
    for rule in config["rules"]:
        if rule.startswith("RULE-SET,"):
            assert rule.split(",")[1] in config["rule-providers"], rule
    for target in re.findall(r"#([^'\"\s]+)", yaml.safe_dump(config["dns"], allow_unicode=True)):
        assert target in group_map or target == "DIRECT", target
    for key in policy:
        if key.startswith("rule-set:"):
            assert set(key.removeprefix("rule-set:").split(",")) <= config["rule-providers"].keys(), key
    settings = json.loads((ROOT / "zashboard-settings.json").read_text())
    folders = json.loads(settings["config/proxy-folders"])["folders"]
    def matches(folder, name):
        include = [r for r in folder["rules"] if r["type"] == "regex"]
        exclude = [r for r in folder["rules"] if r["type"] == "excludeRegex"]
        return any(re.search(r["pattern"], name) for r in include) and not any(re.search(r["pattern"], name) for r in exclude)
    # Exactly the service groups before automatic selection belong in Strategies.
    for i, name in enumerate(names):
        service = i < names.index("自动选择")
        assert matches(folders[0], name) == service, name
        assert matches(folders[1], name) != service, name
    print(f"PASS {filename}: {len(groups)} groups, source isolation, selector coverage, references")


if __name__ == "__main__":
    for filename in FILES:
        validate(filename)
