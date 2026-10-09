"""Check template DNS decisions with a real Mihomo kernel and local DNS fixtures."""
from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import socket
import struct
import subprocess
from tempfile import TemporaryDirectory
import threading
import time

import yaml

from validate_templates import FILES, ROOT


def packet(name: str) -> bytes:
    question = b"".join(bytes([len(part)]) + part.encode() for part in name.split("."))
    return struct.pack("!HHHHHH", 1234, 0x100, 1, 0, 0, 0) + question + b"\0" + struct.pack("!HH", 1, 1)


def query(port: int, name: str) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(0.5)
        request = packet(name)
        sock.sendto(request, ("127.0.0.1", port))
        response, _ = sock.recvfrom(4096)
        assert response[:2] == request[:2]
        assert response[3] & 0xF == 0, response.hex()
        assert struct.unpack("!H", response[6:8])[0] == 1
        return socket.inet_ntoa(response[-4:])


def serve(upstream: socket.socket, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            data, addr = upstream.recvfrom(4096)
        except socket.timeout:
            continue
        cursor = 12
        while data[cursor]:
            cursor += 1 + data[cursor]
        question = data[12:cursor + 5]
        response = data[:2] + struct.pack("!HHHHH", 0x8180, 1, 1, 0, 0) + question
        response += b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + socket.inet_aton("203.0.113.10")
        upstream.sendto(response, addr)


def check(filename: str, upstream_port: int) -> None:
    source = yaml.safe_load((ROOT / filename).read_text())
    dns = source["dns"]
    # Deliberate overlaps prove force-before-bypass and the final fallback.
    payloads = {
        "VoidClaude": ["claude.example", "claude-stun.example"],
        "VoidSTUN": ["stun.example", "claude-stun.example"],
        "VoidFakeIPForce": ["force.example", "force-bypass.example"],
        "VoidFakeIPBypass": ["claude.example", "stun.example", "claude-stun.example", "bypass.example", "force-bypass.example"],
    }
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = {
        "log-level": "error",
        "dns": {
            "enable": True, "ipv6": False, "listen": f"127.0.0.1:{port}",
            "enhanced-mode": dns["enhanced-mode"],
            "fake-ip-range": dns["fake-ip-range"],
            "fake-ip-filter-mode": dns["fake-ip-filter-mode"],
            "fake-ip-filter": dns["fake-ip-filter"],
            "nameserver": [f"udp://127.0.0.1:{upstream_port}"],
            "default-nameserver": ["127.0.0.1"],
        },
        "rules": ["MATCH,DIRECT"],
        "rule-providers": {
            name: {"type": "inline", "behavior": "domain", "payload": entries}
            for name, entries in payloads.items()
        },
    }
    whitelist = dns["fake-ip-filter-mode"] == "whitelist"
    cases = {
        "claude.example": True, "stun.example": True, "claude-stun.example": True,
        "force.example": True, "force-bypass.example": filename != "multi_providers_mihomo.yaml",
        "bypass.example": False, "unmatched.example": not whitelist,
    }
    with TemporaryDirectory(prefix="clash-dns-regression-") as directory:
        directory = Path(directory)
        path = directory / "config.yaml"
        path.write_text(yaml.safe_dump(config, allow_unicode=True))
        with (directory / "runtime.log").open("wb") as log:
            process = subprocess.Popen(
                [os.environ.get("MIHOMO_BINARY", "mihomo"), "-d", str(directory), "-f", str(path)],
                stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    assert process.poll() is None, (directory / "runtime.log").read_text()
                    try:
                        query(port, "ready.example")
                        break
                    except socket.timeout:
                        pass
                else:
                    raise AssertionError("Mihomo DNS listener did not become ready")
                for name, fake in cases.items():
                    address = query(port, name)
                    actual = ipaddress.ip_address(address) in ipaddress.ip_network("198.18.0.0/16")
                    assert actual == fake, (filename, name, address, fake)
                    if not fake:
                        assert address == "203.0.113.10"
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    print(f"PASS {filename}: {len(cases)} live DNS decisions (local fixtures)")


def main() -> None:
    stop = threading.Event()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream:
        upstream.bind(("127.0.0.1", 0))
        upstream.settimeout(0.2)
        thread = threading.Thread(target=serve, args=(upstream, stop), daemon=True)
        thread.start()
        try:
            for filename in FILES:
                check(filename, upstream.getsockname()[1])
        finally:
            stop.set()
            thread.join(timeout=1)


if __name__ == "__main__":
    main()
