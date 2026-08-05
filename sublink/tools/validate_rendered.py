"""Validate the rendered Mihomo YAML without printing proxy credentials."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
RENDERED = (
    Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else ROOT / "sublink" / "mihomo_fakeip_whitelist.rendered.yaml"
)
EXPECTED_PROXY_COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else None
CANDIDATE = ROOT / "sublink" / "sublinkpro_mihomo_fakeip_whitelist.yaml"

FLAG_PATTERN = r"[\U0001F1E6-\U0001F1FF]{2}"
INFO_PATTERN = re.compile(r"剩余流量|套餐到期|下次重置|重置剩余|官网", re.IGNORECASE)
AIRPORT_SEMANTIC_PATTERN = re.compile(r"高速|专线|直连|BGP|CTCU|CMCU|住宅IP", re.IGNORECASE)
RATE_PATTERN = re.compile(
    r"(?:^| )(?:\d+(?:\.\d+)?\s*(?:x|×|倍(?:率)?)|(?:x|×)\s*\d+(?:\.\d+)?)(?: |#|$)",
    re.IGNORECASE,
)
PRIMARY_HOME_FLAGS = ("🇺🇸", "🇭🇰", "🇸🇬", "🇯🇵", "🇹🇼")
AI_TOKENS = ("Claude", "Gemini", "OpenAI")
STREAMING_TOKENS = ("Netflix", "Disney+", "YouTube Premium", "Bahamut")


def load_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is {type(value).__name__}, not a YAML mapping")
    return value


def has_token(name: str, token: str) -> bool:
    return re.search(rf"(?:^| ){re.escape(token)}(?: |#|$)", name) is not None


def count_token(names: list[str], token: str) -> int:
    return sum(has_token(name, token) for name in names)


def excludes_home(group: dict[str, Any]) -> bool:
    pattern = str(group.get("exclude-filter", ""))
    if not pattern:
        return False
    try:
        return re.search(pattern, "🇭🇰 香港 家宽 Netflix") is not None
    except re.error:
        return False


def home_sort_key(name: str) -> tuple[Any, ...]:
    primary_index = next(
        (index for index, flag in enumerate(PRIMARY_HOME_FLAGS) if name.startswith(flag)),
        None,
    )
    if primary_index is not None:
        country_key: tuple[Any, ...] = (0, primary_index)
    elif name.startswith("🏳️"):
        country_key = (2, "")
    else:
        country_key = (1, name.split(" ", 1)[0])

    all_ai = has_token(name, "AI")
    ai_available = tuple(all_ai or has_token(name, token) for token in AI_TOKENS)
    streaming_available = tuple(has_token(name, token) for token in STREAMING_TOKENS)
    return (
        country_key,
        not all_ai,
        -sum(ai_available),
        -sum(streaming_available),
        tuple(not available for available in ai_available),
        tuple(not available for available in streaming_available),
    )


def main() -> None:
    rendered = load_mapping(RENDERED)
    candidate = load_mapping(CANDIDATE)

    proxies = rendered.get("proxies") or []
    proxy_maps = [proxy for proxy in proxies if isinstance(proxy, dict)]
    names = [str(proxy.get("name", "")) for proxy in proxy_maps]
    groups = rendered.get("proxy-groups") or []
    group_map = {str(group["name"]): group for group in groups}

    builtins = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE", "GLOBAL"}
    unresolved = sorted(
        {
            member
            for group in groups
            for member in (group.get("proxies") or [])
            if member not in builtins and member not in group_map and member not in names
        }
    )

    regions = {
        "US": sum(name.startswith("🇺🇸") for name in names),
        "HK": sum(name.startswith("🇭🇰") for name in names),
        "SG": sum(name.startswith("🇸🇬") for name in names),
        "JP": sum(name.startswith("🇯🇵") for name in names),
        "TW": sum(name.startswith("🇹🇼 中国台湾") for name in names),
        "Other": sum(not re.match(r"^(?:🇺🇸|🇭🇰|🇸🇬|🇯🇵)", name) for name in names),
        "Unknown": sum(name.startswith("🏳️ 未知") for name in names),
    }
    features = {
        "HomeBroadband": count_token(names, "家宽"),
        "Rate": sum(RATE_PATTERN.search(name) is not None for name in names),
        "AllAI": count_token(names, "AI"),
        "Claude": sum(has_token(name, "AI") or has_token(name, "Claude") for name in names),
        "Gemini": sum(has_token(name, "AI") or has_token(name, "Gemini") for name in names),
        "OpenAI": sum(has_token(name, "AI") or has_token(name, "OpenAI") for name in names),
        "Netflix": count_token(names, "Netflix"),
        "SelfBuilt": count_token(names, "自建"),
    }

    preserved_keys = (
        "rules",
        "rule-providers",
        "dns",
        "tun",
        "sniffer",
        "hosts",
        "geox-url",
        "profile",
        "external-controller",
        "external-ui",
        "external-ui-url",
        "secret",
    )
    preserved_sections = {key: rendered.get(key) == candidate.get(key) for key in preserved_keys}

    old_markers = ("[LC=", "[G=", "[OA=", "[GM=", "[CL=", "[NF=")
    duplicate_flags = sum(
        re.match(rf"^{FLAG_PATTERN}\s+{FLAG_PATTERN}", name) is not None for name in names
    )
    ai_preferred = group_map["AI优选"]
    media_unlock = group_map["流媒体解锁"]
    home_group = group_map["家宽手选"]
    home_names = [name for name in names if has_token(name, "家宽")]
    home_name_set = set(home_names)
    parent_groups = [
        group for group in groups if "自建手选" in (group.get("proxies") or [])
    ]
    dynamic_groups_without_home_exclusion = [
        str(group.get("name", ""))
        for group in groups
        if group.get("name") != "家宽手选"
        and group.get("include-all") is True
        and not excludes_home(group)
    ]
    explicit_home_membership_violations = {
        str(group.get("name", "")): sorted(
            home_name_set.intersection(set(group.get("proxies") or []))
        )
        for group in groups
        if group.get("name") != "家宽手选"
        and home_name_set.intersection(set(group.get("proxies") or []))
    }

    checks = {
        "proxy_count": bool(proxies)
        and (EXPECTED_PROXY_COUNT is None or len(proxies) == EXPECTED_PROXY_COUNT),
        "all_proxies_are_mappings": len(proxy_maps) == len(proxies),
        "unique_proxy_names": len(names) == len(set(names)),
        "all_names_start_with_one_flag": bool(names)
        and all(re.match(rf"^(?:{FLAG_PATTERN}|🏳️) ", name) is not None for name in names),
        "duplicate_flags_removed": duplicate_flags == 0,
        "airport_info_removed": all(INFO_PATTERN.search(name) is None for name in names),
        "airport_semantics_removed": all(AIRPORT_SEMANTIC_PATTERN.search(name) is None for name in names),
        "old_machine_markers_removed": all(not any(marker in name for marker in old_markers) for name in names),
        "home_nodes_present": bool(home_names),
        "proxy_group_count": len(groups) == 47,
        "unique_proxy_groups": len(groups) == len(group_map),
        "no_unresolved_group_references": not unresolved,
        "home_group_is_select": home_group.get("type") == "select",
        "home_group_has_explicit_members": home_group.get("proxies") == home_names,
        "home_group_dynamic_filter_removed": "include-all" not in home_group
        and "filter" not in home_group,
        "home_nodes_sorted": home_names == sorted(home_names, key=home_sort_key),
        "all_other_dynamic_groups_exclude_home": not dynamic_groups_without_home_exclusion,
        "home_nodes_not_explicit_elsewhere": not explicit_home_membership_violations,
        "home_after_self_in_parent_groups": len(parent_groups) == 15
        and all(
            group["proxies"].index("家宽手选")
            == group["proxies"].index("自建手选") + 1
            for group in parent_groups
        ),
        "home_not_added_to_active_groups": all(
            "家宽手选" not in (group.get("proxies") or [])
            for group in groups
            if group.get("type") in {"load-balance", "fallback", "url-test"}
        ),
        "ai_preferred_is_fallback": ai_preferred.get("type") == "fallback",
        "ai_preferred_order": ai_preferred.get("proxies") == ["通用", "Claude", "Gemini", "OpenAI"],
        "media_unlock_is_url_test": media_unlock.get("type") == "url-test",
        "no_proxy_providers": "proxy-providers" not in rendered,
        "no_groups_with_use": all("use" not in group for group in groups),
        "preserved_core_sections": all(preserved_sections.values()),
    }

    raw = RENDERED.read_bytes()
    result = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "expected_proxy_count": EXPECTED_PROXY_COUNT,
        "proxy_count": len(proxies),
        "proxy_element_types": dict(Counter(type(proxy).__name__ for proxy in proxies)),
        "proxy_group_count": len(groups),
        "regions": regions,
        "features": features,
        "duplicate_flags": duplicate_flags,
        "unresolved_group_references": unresolved,
        "ai_preferred": {
            "type": ai_preferred.get("type"),
            "order": ai_preferred.get("proxies"),
        },
        "media_unlock": {
            "type": media_unlock.get("type"),
            "filter": media_unlock.get("filter"),
            "interval": media_unlock.get("interval"),
            "tolerance": media_unlock.get("tolerance"),
        },
        "home_broadband": {
            "type": home_group.get("type"),
            "explicit_members": len(home_group.get("proxies") or []),
            "count": len(home_names),
            "order": home_names,
            "parent_group_count": len(parent_groups),
            "dynamic_groups_without_exclusion": dynamic_groups_without_home_exclusion,
            "explicit_membership_violations": explicit_home_membership_violations,
        },
        "preserved_sections": preserved_sections,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["all_checks_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
