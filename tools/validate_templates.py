"""Validate maintained template source boundaries and self-built selectors."""
from pathlib import Path
import json
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
SLOTS = ["自建选1", "自建选2", "自建选3"]
SELF_GROUPS = ["自建节点", *SLOTS]
PANEL_GROUPS = [f"自选{i}" for i in range(1, 5)]
STUN_PREFIX = ["PROXY", "AI", "Claude", "Google", "跨境金融"]
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
    config = yaml.load((ROOT / filename).read_text(encoding="utf-8"), Loader=UniqueLoader)
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
        manual = "手选" in group["name"] or group["name"] == "流媒体解锁"
        if panel and group["name"] == "流媒体解锁":
            assert group["type"] == "select"
            assert members == [
                "/(?i)(流媒体|解锁|IEPL|专线|Premium|网飞|Netflix|Disney|HBO)/",
                *PANEL_GROUPS,
            ], "Panel media selector must retain exactly four self-selected fallbacks"
        elif manual:
            assert group["type"] == "select"
            assert not set(group_map).intersection(members), (group["name"], "Manual selectors must contain nodes only")
            assert not set(members).intersection({"DIRECT", "REJECT", "COMPATIBLE"}), group["name"]
            if panel:
                assert all(member.startswith("/") and member.endswith("/") for member in members)
            else:
                assert group.get("include-all") is True and not members and "use" not in group, group["name"]
                assert not group.get("exclude-filter") and not group.get("exclude-type"), group["name"]
                if group["name"] in {"全部手选", "地区手选"}:
                    assert not group.get("filter"), group["name"]
                elif group["name"] == "流媒体解锁":
                    assert group.get("filter") == "(?i)(流媒体|解锁|IEPL|专线|Premium|网飞|Netflix|Disney|HBO)"
        elif group["name"] in selectors:
            assert group["type"] == "select"
            assert not set(selectors).intersection(members), "Selector cycle"
            assert not any(k in group for k in ("filter", "exclude-filter", "exclude-type"))
        elif group["type"] == "select":
            assert set(selectors if panel else slots).issubset(members), group["name"]
            if set(selectors).issubset(members):
                ordered = [name for name in selectors if name != group.get("default-selected")]
                i = members.index(ordered[0])
                assert members[i:i + len(ordered)] == ordered, group["name"]
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
    pool_members = [member for member in group_map["IP池"]["proxies"] if member != "/a^/"]
    proxy_members = [member for member in group_map["PROXY"]["proxies"] if member != "/a^/"]
    assert pool_members == ["PROXY", *proxy_members]
    for name, target in {"IP池": "PROXY", "AI": "PROXY", "Claude": "PROXY", "跨境金融": "PROXY", "STUN": "PROXY", "TikTok": "DIRECT", "海淘购物": "PROXY"}.items():
        group = group_map[name]
        assert group.get("default-selected", group["proxies"][0]) == target, name
        assert group["proxies"][0] == target, (name, "Default must also work on older kernels")
    assert "default-selected" not in group_map["TikTok"]
    assert group_map["海淘购物"]["proxies"][:3] == ["PROXY", "DIRECT", "自动选择"]
    assert group_map["STUN"]["proxies"][:len(STUN_PREFIX)] == STUN_PREFIX, "STUN service candidate order"
    assert config["rules"].count("RULE-SET,VoidSTUN,STUN") == 1
    assert config["rules"].index("RULE-SET,VoidSTUN,STUN") < config["rules"].index("DOMAIN-SUFFIX,browserleaks.com,IPCheck")
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
            if "手选" in group["name"] or group["name"] == "流媒体解锁":
                continue
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
            "RULE-SET,VoidClaudeMRS,fake-ip",
            "RULE-SET,VoidSTUN,fake-ip",
            *(["RULE-SET,VoidFakeIPForce,fake-ip"] if "fakeip_rule" in filename else []),
            "RULE-SET,VoidFakeIPBypass,real-ip",
            "MATCH,fake-ip",
        ]
    else:
        assert config["dns"]["fake-ip-filter-mode"] == "whitelist"
        assert config["dns"]["fake-ip-filter"] == [
            "rule-set:VoidClaudeMRS", "rule-set:VoidSTUN", "rule-set:VoidFakeIPForce",
        ]
    referenced_filters = set()
    for entry in config["dns"]["fake-ip-filter"]:
        if entry.startswith("RULE-SET,"):
            referenced_filters.add(entry.split(",")[1])
        elif entry.startswith("rule-set:"):
            referenced_filters.update(entry.removeprefix("rule-set:").split(","))
    # classical providers are supported in fake-ip-filter too: mihomo keeps the
    # domain rules and only ignores non-domain ones (PROCESS-NAME/IP-CIDR/...).
    for name in referenced_filters:
        assert config["rule-providers"][name]["behavior"] in {"domain", "classical"}
    for name, path in {
        "VoidAClaudeOverlap": "void-claude-ai-overlap",
        "VoidSTUN": "stun",
    }.items():
        provider = config["rule-providers"][name]
        assert provider["format"] == "mrs"
        assert provider["url"].endswith(f"/dist/{path}/mihomo-domain.mrs")
    # VoidClaude ships PROCESS-NAME/IP-CIDR/IP-ASN rules, which the domain mrs cannot
    # carry, so the routing provider must stay classical.
    claude_provider = config["rule-providers"]["VoidClaude"]
    assert claude_provider["behavior"] == "classical"
    assert claude_provider["format"] == "yaml"
    assert claude_provider["url"].endswith("/dist/void-claude-rules/mihomo-classical.yaml")
    # VoidClaudeMRS is the domain-only subset used by DNS (fake-ip-filter/nameserver-policy).
    claude_mrs = config["rule-providers"]["VoidClaudeMRS"]
    assert claude_mrs["behavior"] == "domain"
    assert claude_mrs["format"] == "mrs"
    assert claude_mrs["url"].endswith("/dist/void-claude-rules/mihomo-domain.mrs")
    # VoidGlobalLegal is a pure DOMAIN-SUFFIX list, so it ships as a domain mrs.
    global_legal = config["rule-providers"]["VoidGlobalLegal"]
    assert global_legal["behavior"] == "domain"
    assert global_legal["format"] == "mrs"
    assert global_legal["url"].endswith("/dist/global-legal/mihomo-domain.mrs")
    # The PCDN list contains DOMAIN-REGEX entries, which require classical behavior.
    pcdn = config["rule-providers"]["PCDN"]
    assert pcdn["behavior"] == "classical"
    assert pcdn["format"] == "yaml"
    policy = config["dns"]["nameserver-policy"]
    assert policy["rule-set:VoidClaudeMRS"] == [s.replace("#AI", "#Claude") for s in policy["rule-set:VoidAI"]]
    overlap_key = f"rule-set:{CLAUDE_DNS_OVERLAP_PROVIDER}"
    assert overlap_key in policy
    assert policy[overlap_key] == policy["rule-set:VoidClaudeMRS"]
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
    settings = json.loads((ROOT / "zashboard-settings.json").read_text(encoding="utf-8"))
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
