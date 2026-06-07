"""Shared TCP message layer for Pithon Arena.

Networking concepts implemented from the course slides:
- application-layer messages exchanged through sockets
- client/server TCP transport
- framing with a 4-byte length header
- sequence numbers and ACK control messages
- checksum-based error detection
- per-socket traffic statistics for diagnostics
"""

from __future__ import annotations

import hashlib
import json
import socket
import threading
import time
from collections import deque
from typing import Dict, Optional

MAX_FRAME_SIZE = 1_000_000
_NETWORK_LOCK = threading.Lock()
_SOCKET_STATE: Dict[int, dict] = {}


def _canonical_json(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _checksum(packet: dict) -> str:
    clean = dict(packet)
    clean.pop("_checksum", None)
    return hashlib.sha256(_canonical_json(clean)).hexdigest()[:16]


def send_msg(sock: socket.socket, data: dict):
    """Send one JSON message as a framed TCP payload."""
    try:
        state = _get_socket_state(sock)
        packet = dict(data)
        if packet.get("type") != "ack" and "_msg_id" not in packet:
            packet["_msg_id"] = state["next_msg_id"]
            state["next_msg_id"] += 1
        packet["_sent_at"] = time.time()
        packet["_checksum"] = _checksum(packet)
        _record_protocol(state, "OUT", packet)
        raw = json.dumps(packet, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_FRAME_SIZE:
            raise ValueError("message frame too large")
        with state["send_lock"]:
            sock.sendall(len(raw).to_bytes(4, "big") + raw)
        frame_bytes = len(raw) + 4
        state["messages_sent"] += 1
        state["bytes_sent"] += frame_bytes
        _record_throughput(state, "out", frame_bytes)
        state["last_sent_at"] = time.time()
    except Exception:
        _drop_socket_state(sock)


def recv_msg(sock: socket.socket) -> Optional[dict]:
    """Receive one JSON message, validating frame size and checksum."""
    try:
        while True:
            header = _recvall(sock, 4)
            if not header:
                _drop_socket_state(sock)
                return None
            length = int.from_bytes(header, "big")
            if length <= 0 or length > MAX_FRAME_SIZE:
                _drop_socket_state(sock)
                return None
            payload = _recvall(sock, length)
            if not payload:
                _drop_socket_state(sock)
                return None
            msg = json.loads(payload.decode("utf-8"))
            if not isinstance(msg, dict):
                continue
            state = _get_socket_state(sock)
            expected = msg.get("_checksum")
            if expected and expected != _checksum(msg):
                state["checksum_errors"] += 1
                _record_protocol(state, "BAD_CHECKSUM", msg)
                continue
            if msg.get("type") == "ack":
                state["acks_received"] += 1
                _record_protocol(state, "IN", msg)
                continue
            msg_id = msg.get("_msg_id")
            if msg_id is not None:
                if msg_id in state["received_ids"]:
                    state["duplicates_received"] += 1
                    _send_ack(sock, msg_id)
                    continue
                state["received_ids"].add(msg_id)
                if len(state["received_ids"]) > 1000:
                    state["received_ids"] = set(list(state["received_ids"])[-500:])
                _send_ack(sock, msg_id)
                msg = dict(msg)
                msg.pop("_msg_id", None)
                msg["_received_at"] = time.time()
                msg["_seq"] = msg_id
            msg.pop("_checksum", None)
            frame_bytes = length + 4
            state["messages_received"] += 1
            state["bytes_received"] += frame_bytes
            _record_throughput(state, "in", frame_bytes)
            state["last_received_at"] = time.time()
            _record_protocol(state, "IN", msg)
            return msg
    except Exception:
        _drop_socket_state(sock)
        return None


def _send_ack(sock: socket.socket, msg_id: int):
    state = _get_socket_state(sock)
    ack_packet = {"type": "ack", "ack_id": msg_id, "_sent_at": time.time()}
    ack_packet["_checksum"] = _checksum(ack_packet)
    ack = json.dumps(ack_packet, separators=(",", ":")).encode("utf-8")
    _record_protocol(state, "OUT", ack_packet)
    with state["send_lock"]:
        sock.sendall(len(ack).to_bytes(4, "big") + ack)
    ack_frame_bytes = len(ack) + 4
    state["acks_sent"] += 1
    state["bytes_sent"] += ack_frame_bytes
    _record_throughput(state, "out", ack_frame_bytes)
    state["last_sent_at"] = time.time()


def _get_socket_state(sock: socket.socket) -> dict:
    key = sock.fileno()
    with _NETWORK_LOCK:
        state = _SOCKET_STATE.get(key)
        if state is None:
            state = {
                "send_lock": threading.RLock(),
                "next_msg_id": 1,
                "received_ids": set(),
                "messages_sent": 0,
                "messages_received": 0,
                "bytes_sent": 0,
                "bytes_received": 0,
                "acks_sent": 0,
                "acks_received": 0,
                "checksum_errors": 0,
                "duplicates_received": 0,
                "created_at": time.time(),
                "last_sent_at": 0.0,
                "last_received_at": 0.0,
                "protocol_log": [],
                "throughput_samples": deque(maxlen=240),
            }
            _SOCKET_STATE[key] = state
        return state


def get_socket_stats(sock: socket.socket) -> dict:
    state = _get_socket_state(sock)
    with _NETWORK_LOCK:
        data = {k: v for k, v in state.items() if k not in ("send_lock", "protocol_log", "received_ids")}
        data["avg_messages_per_minute"] = _estimate_rate(state)
        data.update(_estimate_throughput(state))
        return data


def get_protocol_log(sock: socket.socket, limit: int = 40) -> list:
    state = _get_socket_state(sock)
    with _NETWORK_LOCK:
        return list(state.get("protocol_log", [])[-limit:])


def _drop_socket_state(sock: socket.socket):
    try:
        key = sock.fileno()
    except Exception:
        return
    with _NETWORK_LOCK:
        _SOCKET_STATE.pop(key, None)


def _record_protocol(state: dict, direction: str, msg: dict):
    try:
        entry = {
            "dir": direction,
            "type": msg.get("type", "?"),
            "seq": msg.get("_msg_id", msg.get("_seq", msg.get("ack_id"))),
            "ts": time.time(),
        }
        if entry["type"] == "ack":
            entry["seq"] = msg.get("ack_id")
        state.setdefault("protocol_log", []).append(entry)
        state["protocol_log"] = state["protocol_log"][-100:]
    except Exception:
        pass



def _record_throughput(state: dict, direction: str, byte_count: int):
    """Store a small rolling window for live throughput in bytes/second."""
    try:
        state.setdefault("throughput_samples", deque(maxlen=240)).append((time.time(), direction, int(byte_count)))
    except Exception:
        pass


def _estimate_throughput(state: dict, window_sec: float = 2.0) -> dict:
    now = time.time()
    cutoff = now - window_sec
    sent = received = 0
    sent_messages = received_messages = 0
    for ts, direction, byte_count in list(state.get("throughput_samples", [])):
        if ts >= cutoff:
            if direction == "out":
                sent += byte_count
                sent_messages += 1
            else:
                received += byte_count
                received_messages += 1
    return {
        "throughput_window_sec": window_sec,
        "throughput_sent_bps": sent / window_sec,
        "throughput_received_bps": received / window_sec,
        "throughput_total_bps": (sent + received) / window_sec,
        "messages_sent_per_sec": sent_messages / window_sec,
        "messages_received_per_sec": received_messages / window_sec,
    }

def _estimate_rate(state: dict) -> float:
    created = state.get("created_at", time.time())
    elapsed_min = max(0.1, (time.time() - created) / 60.0)
    return (state.get("messages_sent", 0) + state.get("messages_received", 0)) / elapsed_min


def _recvall(sock: socket.socket, n: int) -> Optional[bytes]:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data
