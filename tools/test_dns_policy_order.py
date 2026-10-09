"""Prove Claude/AI DNS overlap survives sorted subscriber YAML output."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import time

import yaml

CLAUDE_OVERLAP_KEY = "rule-set:VoidAClaudeOverlap"
CLAUDE_OVERLAP_FIXTURE = ["+.anthropic.com", "+.claude.ai", "+.claude.com", "anthropic.auth0.com"]


def dns_query(name: str, query_id: int = 1234) -> bytes:
    labels = b"".join(bytes([len(part)]) + part.encode() for part in name.split("."))
    return struct.pack("!HHHHHH", query_id, 0x100, 1, 0, 0, 0) + labels + b"\0" + struct.pack("!HH", 1, 1)


def fixture_server(sock: socket.socket, address: str, stop: threading.Event) -> None:
    sock.settimeout(0.2)
    while not stop.is_set():
        try:
            request, peer = sock.recvfrom(4096)
        except socket.timeout:
            continue
        end = 12
        while request[end]:
            end += request[end] + 1
        question = request[12 : end + 5]
        reply = request[:2] + struct.pack("!HHHHH", 0x8180, 1, 1, 0, 0) + question
        reply += b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 30, 4) + socket.inet_aton(address)
        sock.sendto(reply, peer)


def query(port: int, name: str) -> str:
    request = dns_query(name)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(1)
        sock.sendto(request, ("127.0.0.1", port))
        response, _ = sock.recvfrom(4096)
    assert response[:2] == request[:2]
    assert response[3] & 0xF == 0, response.hex()
    return socket.inet_ntoa(response[-4:])


def main() -> None:
    # Sort exactly as the subscriber output path does. The overlap provider must
    # remain before rule-set:VoidAI, while AI-only domains still use VoidAI.
    policy = {
        CLAUDE_OVERLAP_KEY: ["udp://127.0.0.1:1"],
        "rule-set:VoidAI": ["udp://127.0.0.1:1"],
    }
    sorted_keys = sorted(policy)
    assert sorted_keys.index(CLAUDE_OVERLAP_KEY) < sorted_keys.index("rule-set:VoidAI")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as claude_sock, socket.socket(
        socket.AF_INET, socket.SOCK_DGRAM
    ) as ai_sock, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as default_sock:
        claude_sock.bind(("127.0.0.1", 0))
        ai_sock.bind(("127.0.0.1", 0))
        default_sock.bind(("127.0.0.1", 0))
        ports = [claude_sock.getsockname()[1], ai_sock.getsockname()[1], default_sock.getsockname()[1]]
        stop = threading.Event()
        threads = [
            threading.Thread(target=fixture_server, args=(claude_sock, "203.0.113.11", stop), daemon=True),
            threading.Thread(target=fixture_server, args=(ai_sock, "203.0.113.22", stop), daemon=True),
            threading.Thread(target=fixture_server, args=(default_sock, "203.0.113.33", stop), daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            policy = {
                CLAUDE_OVERLAP_KEY: [f"udp://127.0.0.1:{ports[0]}"],
                "rule-set:VoidAI": [f"udp://127.0.0.1:{ports[1]}"],
            }
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(("127.0.0.1", 0))
                listen_port = probe.getsockname()[1]
            config = {
                "log-level": "error",
                "dns": {
                    "enable": True,
                    "ipv6": False,
                    "listen": f"127.0.0.1:{listen_port}",
                    "enhanced-mode": "redir-host",
                    "nameserver": [f"udp://127.0.0.1:{ports[2]}"],
                    "default-nameserver": ["127.0.0.1"],
                    "nameserver-policy": dict(sorted(policy.items())),
                },
                "rule-providers": {
                    "VoidAClaudeOverlap": {
                        "type": "inline",
                        "behavior": "domain",
                        "payload": CLAUDE_OVERLAP_FIXTURE,
                    },
                    "VoidAI": {
                        "type": "inline",
                        "behavior": "domain",
                        "payload": ["+.anthropic.com", "+.claude.ai", "+.claude.com", "+.auth0.com", "+.chatgpt.com"],
                    }
                },
                "rules": ["MATCH,DIRECT"],
            }
            with tempfile.TemporaryDirectory(prefix="clash-dns-policy-") as directory:
                directory = Path(directory)
                overlap_mrs = os.environ.get("CLAUDE_OVERLAP_MRS")
                if overlap_mrs:
                    provider_path = directory / "claude-ai-overlap.mrs"
                    provider_path.write_bytes(Path(overlap_mrs).read_bytes())
                    config["rule-providers"]["VoidAClaudeOverlap"] = {
                        "type": "file",
                        "behavior": "domain",
                        "format": "mrs",
                        "path": str(provider_path),
                    }
                config_path = directory / "config.yaml"
                config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
                binary = os.environ.get("MIHOMO_BINARY")
                if not binary:
                    binary = "/tmp/clash-template-mihomo" if Path("/tmp/clash-template-mihomo").exists() else "mihomo"
                log_path = directory / "mihomo.log"
                with log_path.open("wb") as log:
                    process = subprocess.Popen([binary, "-d", str(directory), "-f", str(config_path)], stdout=log, stderr=log)
                try:
                    for _ in range(60):
                        try:
                            assert query(listen_port, "api.anthropic.com") == "203.0.113.11"
                            assert query(listen_port, "anthropic.auth0.com") == "203.0.113.11"
                            assert query(listen_port, "other.auth0.com") == "203.0.113.22"
                            assert query(listen_port, "chatgpt.com") == "203.0.113.22"
                            assert query(listen_port, "example.net") == "203.0.113.33"
                            break
                        except (AssertionError, socket.timeout):
                            if process.poll() is not None:
                                raise AssertionError(log_path.read_text())
                            time.sleep(0.1)
                    else:
                        raise AssertionError("Mihomo DNS policy fixture did not become ready")
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
        finally:
            stop.set()
            for thread in threads:
                thread.join(timeout=1)
    print("PASS: sorted subscriber policy keeps Claude overlap on Claude, AI-only and default domains unchanged")


if __name__ == "__main__":
    main()
