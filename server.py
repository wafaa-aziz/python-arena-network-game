"""Ultimate Pithon Arena server.
Features: bot opponent, multiple levels, countdown, powerups,
scoreboard persistence, spectator mode, whispers, rematch,
ping/pong support, richer end-game stats.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from network import get_socket_stats, recv_msg, send_msg

BOARD_W = 40
BOARD_H = 30
CELL = 20
FPS = 10
TIME_LIMIT = 120
BASE_HEALTH = 100
MAX_HEALTH = 160
NUM_PIES = 5
NUM_POWERUPS = 3
SCOREBOARD_FILE = os.path.join(os.path.dirname(__file__), "scoreboard.json")
SERVER_LOG_FILE = os.path.join(os.path.dirname(__file__), "server.log")
MATCH_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "match_history.jsonl")
REPLAY_FILE = os.path.join(os.path.dirname(__file__), "replay_log.jsonl")
HEARTBEAT_TIMEOUT = 5.0
CONNECTION_LIMIT = 24
CHAT_WINDOW_SEC = 4.0
CHAT_LIMIT = 6
MOVE_WINDOW_SEC = 1.0
MOVE_LIMIT = 25
CHAT_REACTIONS = ("🔥", "😄", "💀", "👀")
CHAT_STYLES = {"Normal", "Angry", "Troll", "Robot"}
EYE_STYLES = {"Normal", "Sunglasses", "Glowing", "Robot"}
BODY_STYLES = {"Rounded", "Square", "Spiky", "Segmented"}
TRAIL_STYLES = {"None", "Sparkle", "Smoke", "Neon", "Rainbow"}
SKIN_THEMES = {"Default", "Inferno", "Ice", "Galaxy", "Cyber"}
HEAD_STYLES = {"Classic", "Dragon", "Skull", "Cat", "Pixel", "Robot"}

PIE_TYPES = [
    {"kind": "normal", "value": 15, "color": (255, 208, 72)},
    {"kind": "golden", "value": 25, "color": (255, 164, 39)},
    {"kind": "poison", "value": -10, "color": (100, 210, 90)},
    {"kind": "mega", "value": 35, "color": (255, 90, 120)},
]

POWERUP_TYPES = {
    "speed": {"color": (64, 200, 255), "duration": 4.0},
    "shield": {"color": (255, 255, 130), "duration": 4.5},
    "freeze": {"color": (120, 180, 255), "duration": 2.5},
    "radar": {"color": (180, 120, 255), "duration": 6.0},
    "regen": {"color": (110, 255, 140), "duration": 3.5},
}

LEVELS = {
    "Easy": {
        "move_interval": 0.34,
        "speed_boost_interval": 0.22,
        "obstacles": [(10, 10), (10, 11), (10, 12), (29, 17), (29, 18), (29, 19), (20, 14), (20, 15)],
    },
    "Medium": {
        "move_interval": 0.30,
        "speed_boost_interval": 0.20,
        "obstacles": [
        (8, y) for y in range(5, 25)
    ] + [
        (31, y) for y in range(5, 25)
    ] + [
        (x, 8) for x in range(12, 28)
    ] + [
        (x, 21) for x in range(12, 28)
        ],
    },
    "Hard": {
        "move_interval": 0.26,
        "speed_boost_interval": 0.18,
        "obstacles": [
        (20, y) for y in range(4, 26) if y not in (14, 15)
    ] + [
        (x, 15) for x in range(7, 33) if x not in (19, 20, 21)
        ],
    },
    "Impossible": {
        "move_interval": 0.22,
        "speed_boost_interval": 0.15,
        "obstacles": [
        (12, y) for y in range(3, 27) if y not in (10, 19)
    ] + [
        (27, y) for y in range(3, 27) if y not in (10, 19)
    ] + [
        (x, 10) for x in range(6, 34) if x not in (12, 27)
    ] + [
        (x, 19) for x in range(6, 34) if x not in (12, 27)
    ] + [
        (20, y) for y in range(6, 24) if y not in (14, 15)
        ],
    },
}

STYLES = {
    "Emerald": ((90, 230, 140), (44, 170, 95)),
    "Sapphire": ((90, 150, 255), (50, 100, 200)),
    "Violet": ((200, 120, 255), (140, 80, 220)),
}

DIRS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


@dataclass
class ClientInfo:
    username: str
    sock: socket.socket
    role: str = "lobby"  # lobby/player/viewer
    style: str = "Emerald"
    controls: str = "Arrows"
    level_pref: str = "Easy"
    eye_style: str = "Normal"
    body_style: str = "Rounded"
    trail_style: str = "None"
    skin_theme: str = "Default"
    head_style: str = "Classic"
    typing_until: float = 0.0
    last_seen: float = field(default_factory=time.time)
    chat_times: List[float] = field(default_factory=list)
    move_times: List[float] = field(default_factory=list)
    addr: str = ""
    connected_at: float = field(default_factory=time.time)
    ping_ms: float = 0.0
    ping_samples: List[float] = field(default_factory=list)
    disconnects: int = 0
    timeouts: int = 0
    reconnects: int = 0
    chat_throttle_hits: int = 0
    move_throttle_hits: int = 0


class Scoreboard:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> Dict[str, dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self):
        with self.lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)

    def record_user(self, username: str):
        with self.lock:
            self.data.setdefault(username, {"wins": 0, "losses": 0, "games": 0, "pies": 0, "powerups": 0})

    def record_game(self, winner: str, loser: Optional[str], stats: Dict[str, dict]):
        with self.lock:
            for name, st in stats.items():
                self.data.setdefault(name, {"wins": 0, "losses": 0, "games": 0, "pies": 0, "powerups": 0})
                self.data[name]["games"] += 1
                self.data[name]["pies"] += st.get("pies_eaten", 0)
                self.data[name]["powerups"] += st.get("powerups_used", 0)
            if winner and winner != "Draw":
                self.data.setdefault(winner, {"wins": 0, "losses": 0, "games": 0, "pies": 0, "powerups": 0})
                self.data[winner]["wins"] += 1
            if loser:
                self.data.setdefault(loser, {"wins": 0, "losses": 0, "games": 0, "pies": 0, "powerups": 0})
                self.data[loser]["losses"] += 1
        self.save()

    def top(self) -> List[dict]:
        with self.lock:
            items = []
            for name, v in self.data.items():
                items.append({"name": name, **v})
        return sorted(items, key=lambda x: (-x["wins"], -x["games"], x["name"]))[:8]


class GameState:
    def __init__(self, p1: str, p2: str, styles: Dict[str, str], cosmetics: Dict[str, dict], selected_level: str, bot_player: Optional[str] = None):
        self.lock = threading.Lock()
        self.p1 = p1
        self.p2 = p2
        self.bot_player = bot_player
        self.level_name = selected_level if selected_level in LEVELS else "Easy"
        self.level_config = LEVELS[self.level_name]
        self.start_positions = {
            p1: [(4, 5), (3, 5), (2, 5)],
            p2: [(35, 24), (36, 24), (37, 24)],
        }
        self.snakes = {k: list(v) for k, v in self.start_positions.items()}
        self.directions = {p1: (1, 0), p2: (-1, 0)}
        self.health = {p1: BASE_HEALTH, p2: BASE_HEALTH}
        self.alive = {p1: True, p2: True}
        self.styles = styles
        self.cosmetics = cosmetics
        self.tick = 0
        self.started = False
        self.finished = False
        self.winner: Optional[str] = None
        self.countdown = 3.0
        self.created_at = time.time()
        self.start_time: Optional[float] = None
        self.time_limit = TIME_LIMIT
        self.move_accum = {p1: 0.0, p2: 0.0}
        self.effects = {
            p1: {"speed_until": 0.0, "shield_until": 0.0, "frozen_until": 0.0, "radar_until": 0.0, "regen_until": 0.0},
            p2: {"speed_until": 0.0, "shield_until": 0.0, "frozen_until": 0.0, "radar_until": 0.0, "regen_until": 0.0},
        }
        self.stats = {
            p1: {"pies_eaten": 0, "powerups_used": 0, "damage_taken": 0, "collisions": 0},
            p2: {"pies_eaten": 0, "powerups_used": 0, "damage_taken": 0, "collisions": 0},
        }
        self.obstacles = [{"x": x, "y": y, "kind": "wall", "color": (120, 120, 120)} for x, y in self.level_config["obstacles"]]
        self.pies: List[dict] = []
        self.powerups: List[dict] = []
        self.event_log: List[dict] = []
        self.replay_events: List[dict] = []
        self.replay_frames: List[dict] = []
        self.pending_auto_messages: List[dict] = []
        self.critical_sent = {p1: False, p2: False}
        self.domination_sent = False
        self._spawn_pies()
        self._spawn_powerups()

    def queue_auto_message(self, player: str, text: str, style: str = "Angry"):
        self.pending_auto_messages.append({"sender": player, "text": text, "style": style})

    def drain_auto_messages(self) -> List[dict]:
        items = list(self.pending_auto_messages)
        self.pending_auto_messages.clear()
        return items

    def _occupied(self) -> set:
        occ = {(o["x"], o["y"]) for o in self.obstacles}
        for snake in self.snakes.values():
            occ.update(snake)
        occ.update((p["x"], p["y"]) for p in self.pies)
        occ.update((p["x"], p["y"]) for p in self.powerups)
        return occ

    def _random_cell(self) -> Tuple[int, int]:
        occ = self._occupied()
        while True:
            cell = (random.randint(1, BOARD_W - 2), random.randint(1, BOARD_H - 2))
            if cell not in occ:
                return cell

    def _spawn_pies(self):
        while len(self.pies) < NUM_PIES:
            x, y = self._random_cell()
            kind = random.choice(PIE_TYPES)
            self.pies.append({"x": x, "y": y, **kind})

    def _spawn_powerups(self):
        while len(self.powerups) < NUM_POWERUPS:
            x, y = self._random_cell()
            key = random.choice(list(POWERUP_TYPES))
            self.powerups.append({"x": x, "y": y, "kind": key, **POWERUP_TYPES[key]})

    def log_event(self, kind: str, text: str, color=(255,255,255)):
        event = {"kind": kind, "text": text, "ts": time.time(), "tick": self.tick, "color": color}
        self.event_log.append(event)
        self.event_log = self.event_log[-10:]
        self.replay_events.append(event)

    def replay_frame(self, spectator_count: int, tickrate: int) -> dict:
        return {
            "tick": self.tick,
            "ts": time.time(),
            "started": self.started,
            "finished": self.finished,
            "winner": self.winner,
            "level_name": self.level_name,
            "players": [self.p1, self.p2],
            "snakes": {k: list(v) for k, v in self.snakes.items()},
            "health": dict(self.health),
            "styles": dict(self.styles),
            "cosmetics": {k: dict(v) for k, v in self.cosmetics.items()},
            "pies": [dict(p) for p in self.pies],
            "powerups": [dict(p) for p in self.powerups],
            "obstacles": [dict(o) for o in self.obstacles],
            "events": [dict(e) for e in self.event_log[-8:]],
            "spectators": spectator_count,
            "tickrate": tickrate,
        }

    def set_direction(self, player: str, direction: Tuple[int, int]):
        with self.lock:
            cur = self.directions[player]
            if (-direction[0], -direction[1]) == cur:
                return
            self.directions[player] = direction

    def _speed_interval(self, player: str, now: float) -> float:
        if self.effects[player]["speed_until"] > now:
            return self.level_config["speed_boost_interval"]
        return self.level_config["move_interval"]

    def _apply_damage(self, player: str, damage: int, reason: str):
        if self.effects[player]["shield_until"] > time.time():
            return
        self.health[player] = max(0, self.health[player] - damage)
        self.stats[player]["damage_taken"] += damage
        self.stats[player]["collisions"] += 1
        self.log_event("damage", f"{player} took {damage} damage ({reason})", (255, 90, 90))
        if self.health[player] <= 28 and self.alive[player] and not self.critical_sent[player]:
            self.queue_auto_message(player, "⚠️ CRITICAL!", style="Angry")
            self.critical_sent[player] = True
        if self.health[player] <= 0:
            self.alive[player] = False

    def _apply_powerup(self, player: str, power: dict):
        now = time.time()
        kind = power["kind"]
        self.stats[player]["powerups_used"] += 1
        if kind == "speed":
            self.effects[player]["speed_until"] = now + power["duration"]
        elif kind == "shield":
            self.effects[player]["shield_until"] = now + power["duration"]
        elif kind == "freeze":
            other = self.p2 if player == self.p1 else self.p1
            self.effects[other]["frozen_until"] = now + power["duration"]
        elif kind == "radar":
            self.effects[player]["radar_until"] = now + power["duration"]
        elif kind == "regen":
            self.effects[player]["regen_until"] = now + power["duration"]
        self.log_event("powerup", f"{player} picked {kind.upper()}", power["color"])
        self.queue_auto_message(player, f"🔥 {kind.upper()} ACTIVATED", style="Robot")

    def _maybe_regen(self, player: str, now: float, dt: float):
        if self.effects[player]["regen_until"] > now:
            self.health[player] = min(MAX_HEALTH, self.health[player] + int(6 * dt))
        if self.health[player] > 28:
            self.critical_sent[player] = False

    def _ai_choose_direction(self):
        bot = self.bot_player
        if not bot or not self.alive.get(bot):
            return
        head = self.snakes[bot][0]
        targets = self.pies + self.powerups
        if not targets:
            return
        nearest = min(targets, key=lambda i: abs(i["x"] - head[0]) + abs(i["y"] - head[1]))
        options = []
        if nearest["x"] > head[0]:
            options.append((1, 0))
        elif nearest["x"] < head[0]:
            options.append((-1, 0))
        if nearest["y"] > head[1]:
            options.append((0, 1))
        elif nearest["y"] < head[1]:
            options.append((0, -1))
        options += [(1,0),(-1,0),(0,1),(0,-1)]
        occ = set(self.snakes[self.p1][:-1] + self.snakes[self.p2][:-1] + [(o["x"], o["y"]) for o in self.obstacles])
        for d in options:
            if (-d[0], -d[1]) == self.directions[bot]:
                continue
            nxt = (head[0] + d[0], head[1] + d[1])
            if 0 <= nxt[0] < BOARD_W and 0 <= nxt[1] < BOARD_H and nxt not in occ:
                self.directions[bot] = d
                return

    def _move_once(self, player: str):
        now = time.time()
        if self.effects[player]["frozen_until"] > now:
            return
        dx, dy = self.directions[player]
        hx, hy = self.snakes[player][0]
        nxt = (hx + dx, hy + dy)
        if not (0 <= nxt[0] < BOARD_W and 0 <= nxt[1] < BOARD_H):
            self._apply_damage(player, 20, "wall")
            return
        if nxt in {(o["x"], o["y"]) for o in self.obstacles}:
            self._apply_damage(player, 18, "obstacle")
            return
        other = self.p2 if player == self.p1 else self.p1
        bodies = set(self.snakes[player][:-1] + self.snakes[other])
        if nxt in bodies:
            self._apply_damage(player, 28, "snake")
            return
        self.snakes[player].insert(0, nxt)
        ate = False
        for pie in list(self.pies):
            if (pie["x"], pie["y"]) == nxt:
                self.health[player] = max(0, min(MAX_HEALTH, self.health[player] + pie["value"]))
                self.stats[player]["pies_eaten"] += 1
                self.pies.remove(pie)
                self._spawn_pies()
                self.log_event("pie", f"{player} ate {pie['kind']} pie", pie["color"])
                if pie["kind"] == "mega":
                    self.queue_auto_message(player, "🔥 MEGA BOOST!", style="Troll")
                ate = True
                break
        for power in list(self.powerups):
            if (power["x"], power["y"]) == nxt:
                self.powerups.remove(power)
                self._apply_powerup(player, power)
                self._spawn_powerups()
                ate = True
                break
        if not ate:
            self.snakes[player].pop()

    def tick_game(self, dt: float):
        with self.lock:
            now = time.time()
            if self.finished:
                return
            if not self.started:
                self.countdown = max(0.0, self.countdown - dt)
                if self.countdown <= 0:
                    self.started = True
                    self.start_time = now
                    self.log_event("start", "GO!", (255, 220, 60))
                return
            if self.start_time and now - self.start_time >= self.time_limit:
                self.finished = True
                self._decide_winner(timeout=True)
                return
            self._ai_choose_direction()
            for p in [self.p1, self.p2]:
                self._maybe_regen(p, now, dt)
                self.move_accum[p] += dt
                interval = self._speed_interval(p, now)
                while self.move_accum[p] >= interval and self.alive[p]:
                    self.move_accum[p] -= interval
                    self._move_once(p)
            self.tick += 1
            self._check_game_over()

    def _decide_winner(self, timeout: bool = False):
        """Choose a winner professionally, using fair tie-breakers.

        Order: HP, pies eaten, powerups used, lower damage taken, longer snake.
        Only call it a Draw if every meaningful metric is equal.
        """
        p1, p2 = self.p1, self.p2
        metrics = [
            (self.health.get(p1, 0), self.health.get(p2, 0), "health"),
            (self.stats.get(p1, {}).get("pies_eaten", 0), self.stats.get(p2, {}).get("pies_eaten", 0), "pies"),
            (self.stats.get(p1, {}).get("powerups_used", 0), self.stats.get(p2, {}).get("powerups_used", 0), "powerups"),
            (-self.stats.get(p1, {}).get("damage_taken", 0), -self.stats.get(p2, {}).get("damage_taken", 0), "damage"),
            (len(self.snakes.get(p1, [])), len(self.snakes.get(p2, [])), "length"),
        ]
        self.winner = "Draw"
        reason = "all tie-breakers equal"
        for a, b, label in metrics:
            if a > b:
                self.winner = p1
                reason = label
                break
            if b > a:
                self.winner = p2
                reason = label
                break
        if timeout:
            self.log_event("end", f"Time up! Winner: {self.winner} ({reason})", (255, 220, 60))

    def _check_game_over(self):
        if not self.alive[self.p1] and not self.alive[self.p2]:
            self.finished = True
            self._decide_winner()
        elif not self.alive[self.p1]:
            self.finished = True
            self.winner = self.p2
            self.log_event("kill", f"💀 {self.p2} destroyed {self.p1}", (255, 110, 110))
        elif not self.alive[self.p2]:
            self.finished = True
            self.winner = self.p1
            self.log_event("kill", f"💀 {self.p1} destroyed {self.p2}", (255, 110, 110))
        if self.finished and self.winner and self.winner != "Draw" and not self.domination_sent:
            self.queue_auto_message(self.winner, "🏆 DOMINATION!", style="Robot")
            self.domination_sent = True
        if self.finished and not any(e["kind"] == "end" for e in self.event_log[-2:]):
            self.log_event("end", f"Match over! Winner: {self.winner}", (255, 220, 60))

    def serialize(self, spectator_count: int, tickrate: int, typing_users: Optional[List[str]] = None) -> dict:
        elapsed = 0 if not self.start_time else time.time() - self.start_time
        time_left = max(0, self.time_limit - elapsed) if self.started else self.time_limit
        return {
            "type": "game_state",
            "p1": self.p1,
            "p2": self.p2,
            "tick": self.tick,
            "countdown": round(self.countdown, 1),
            "started": self.started,
            "finished": self.finished,
            "winner": self.winner,
            "time_left": round(time_left, 1),
            "snakes": self.snakes,
            "health": self.health,
            "alive": self.alive,
            "styles": self.styles,
            "cosmetics": self.cosmetics,
            "pies": self.pies,
            "powerups": self.powerups,
            "obstacles": self.obstacles,
            "effects": self.effects,
            "stats": self.stats,
            "level_name": self.level_name,
            "map_name": self.level_name,
            "spectators": spectator_count,
            "tickrate": tickrate,
            "events": self.event_log[-6:],
            "typing": typing_users or [],
        }


class PithonServer:
    def __init__(self, port: int):
        self.port = port
        self.lock = threading.Lock()
        self.log_lock = threading.Lock()
        self.running = True
        self.clients: Dict[str, ClientInfo] = {}
        self.disconnected_sessions: Dict[str, dict] = {}
        self.pending_challenges: Dict[str, str] = {}
        self.pending_rematch: Dict[str, str] = {}
        self.chat_history: List[dict] = []
        self.network_events: List[dict] = []
        self.next_chat_id = 1
        self.game_state: Optional[GameState] = None
        self.game_players: List[str] = []
        self.scoreboard = Scoreboard(SCOREBOARD_FILE)
        self.server = None
        self.reconnect_window = 10.0
        self.handlers = {
            "get_lobby": self._handle_get_lobby_msg,
            "challenge": self._handle_challenge_msg,
            "challenge_accept": self._handle_challenge_accept_msg,
            "challenge_decline": self._handle_challenge_decline_msg,
            "watch": self._handle_watch_msg,
            "move": self._handle_move_msg,
            "chat": self._handle_chat_msg,
            "chat_reaction": self._handle_chat_reaction_msg,
            "cheer": self._handle_cheer_msg,
            "rematch_request": self._handle_rematch_request_msg,
            "rematch_accept": self._handle_rematch_accept_msg,
            "rematch_decline": self._handle_rematch_decline_msg,
            "ping": self._handle_ping_msg,
            "ping_sample": self._handle_ping_sample_msg,
            "cosmetic_update": self._handle_cosmetic_update_msg,
            "typing": self._handle_typing_msg,
            "heartbeat": self._handle_heartbeat_msg,
            "disconnect": self._handle_disconnect_msg,
        }

    def log_line(self, text: str):
        stamp = time.strftime("%H:%M:%S")
        line = f"[{stamp}] {text}"
        print(line)
        with self.log_lock:
            with open(SERVER_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def append_jsonl(self, path: str, data: dict):
        with self.log_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data) + "\n")

    def broadcast_system(self, text: str):
        self.log_line(text)
        self._broadcast({"type": "banner", "text": text})

    def _network_event(self, kind: str, text: str, username: Optional[str] = None, extra: Optional[dict] = None):
        event = {
            "type": "network_event",
            "kind": kind,
            "text": text,
            "username": username,
            "ts": time.time(),
        }
        if extra:
            event.update(extra)
        with self.lock:
            self.network_events.append(event)
            self.network_events = self.network_events[-80:]
        self._broadcast(event)
        return event

    def _warn(self, username: str, text: str, kind: str = "warning"):
        self._send_to(username, {"type": "warning", "msg": text, "kind": kind})
        self._network_event(kind, text, username=username)

    def _store_disconnected_session(self, username: str, info: ClientInfo, reason: str, allow_reconnect: bool):
        session = {
            "info": info,
            "addr": info.addr,
            "reason": reason,
            "created_at": time.time(),
            "expires_at": time.time() + self.reconnect_window if allow_reconnect else time.time(),
            "sock_stats": get_socket_stats(info.sock),
            "ping_samples": list(info.ping_samples),
            "disconnects": info.disconnects + 1,
            "timeouts": info.timeouts + (1 if reason == "timeout" else 0),
            "reconnects": info.reconnects,
            "chat_throttle_hits": info.chat_throttle_hits,
            "move_throttle_hits": info.move_throttle_hits,
            "last_role": info.role,
        }
        self.disconnected_sessions[username] = session
        return session

    def _expire_disconnected_session(self, username: str):
        event_extra = None
        winner_name = None
        with self.lock:
            session = self.disconnected_sessions.pop(username, None)
            if not session:
                return
            info: ClientInfo = session.get("info")
            if self.game_state and not self.game_state.finished and username in self.game_players:
                winner_name = next((p for p in self.game_players if p != username), None)
                if winner_name:
                    self.game_state.finished = True
                    self.game_state.winner = winner_name
                    if info:
                        info.timeouts += 1
            event_extra = {"addr": session.get("addr")}
        if info:
            try:
                info.sock.close()
            except Exception:
                pass
        self.log_line(f"{username} reconnect window expired")
        self._network_event("timeout", f"{username} reconnect window expired", username=username, extra=event_extra)
        self._broadcast_lobby()

    def _trim_times(self, items: List[float], window: float, now: float):
        while items and now - items[0] > window:
            items.pop(0)

    def _rate_limited(self, username: str, bucket: str, limit: int, window: float) -> bool:
        now = time.time()
        with self.lock:
            info = self.clients.get(username)
            if not info:
                return True
            items = info.chat_times if bucket == "chat" else info.move_times
            self._trim_times(items, window, now)
            if len(items) >= limit:
                return True
            items.append(now)
        return False

    def _validate_message(self, username: str, msg: dict) -> bool:
        if not isinstance(msg, dict):
            self._send_to(username, {"type": "error", "msg": "Invalid message format"})
            return False
        mtype = msg.get("type")
        if not isinstance(mtype, str) or mtype not in self.handlers:
            self._send_to(username, {"type": "error", "msg": "Unknown message type"})
            return False
        return True

    def _monitor_clients(self):
        while self.running:
            time.sleep(1.0)
            stale = []
            expired_sessions = []
            now = time.time()
            with self.lock:
                for name, info in self.clients.items():
                    if now - info.last_seen > HEARTBEAT_TIMEOUT:
                        stale.append(name)
                for name, session in self.disconnected_sessions.items():
                    if now >= session.get("expires_at", 0):
                        expired_sessions.append(name)
            for name in stale:
                self.log_line(f"{name} timed out after missing heartbeat")
                self._disconnect(name, reason="timeout")
            for name in expired_sessions:
                self._expire_disconnected_session(name)

    def _console_loop(self):
        if not sys.stdin or not sys.stdin.isatty():
            return
        while self.running:
            line = sys.stdin.readline()
            if not line:
                return
            cmd = line.strip()
            if cmd == "/list":
                with self.lock:
                    snapshot = []
                    for name, info in self.clients.items():
                        snapshot.append(f"{name}:{info.role}@{info.addr} ping={info.ping_ms:.1f}ms")
                    for name, session in self.disconnected_sessions.items():
                        snapshot.append(f"{name}:reconnecting@{session.get('addr','?')} expires={max(0, int(session.get('expires_at', 0) - time.time()))}s")
                self.log_line("clients => " + (", ".join(snapshot) if snapshot else "none"))
            elif cmd == "/stats":
                self.log_line(self._stats_summary())
            elif cmd.startswith("/kick "):
                target = cmd.split(" ", 1)[1].strip()
                if target:
                    self.log_line(f"kick requested for {target}")
                    self._disconnect(target, reason="kicked", graceful=True)
            elif cmd.startswith("/broadcast "):
                text = cmd.split(" ", 1)[1].strip()
                if text:
                    self.broadcast_system(f"[SERVER] {text}")
                    self._network_event("broadcast", text, extra={"scope": "all"})
            elif cmd == "/help":
                self.log_line("commands: /list /stats /kick <user> /broadcast <message> /shutdown")
            elif cmd == "/shutdown":
                self.log_line("shutdown requested from console")
                self.running = False
                try:
                    self.server.close()
                except Exception:
                    pass
                with self.lock:
                    names = list(self.clients)
                for name in names:
                    self._disconnect(name, reason="shutdown")
                return

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.server.bind(("", self.port))
        self.server.listen(20)
        self.log_line(f"Pithon Arena listening on port {self.port}")
        threading.Thread(target=self._monitor_clients, daemon=True).start()
        threading.Thread(target=self._console_loop, daemon=True).start()
        while self.running:
            try:
                conn, addr = self.server.accept()
            except OSError:
                break
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def _handle_client(self, sock: socket.socket, addr):
        hello = recv_msg(sock)
        if not hello or hello.get("type") != "hello":
            send_msg(sock, {"type": "error", "msg": "Expected hello"})
            sock.close()
            return
        username = hello.get("username", "").strip()
        if not username or username.upper() == "BOT":
            send_msg(sock, {"type": "error", "msg": "Invalid username"})
            sock.close()
            return
        addr_text = f"{addr[0]}:{addr[1]}"
        reconnect_snapshot = None
        with self.lock:
            reconnect_snapshot = self.disconnected_sessions.get(username)
            if reconnect_snapshot and time.time() > reconnect_snapshot.get("expires_at", 0):
                self.disconnected_sessions.pop(username, None)
                reconnect_snapshot = None
            if len(self.clients) >= CONNECTION_LIMIT:
                send_msg(sock, {"type": "error", "msg": "Server full"})
                sock.close()
                return
            if username in self.clients:
                if not reconnect_snapshot:
                    send_msg(sock, {"type": "error", "msg": "Username taken"})
                    sock.close()
                    return
            info = ClientInfo(
                username=username,
                sock=sock,
                addr=addr_text,
                style=hello.get("style", "Emerald"),
                controls=hello.get("controls", "Arrows"),
                level_pref=hello.get("level_pref", hello.get("map_pref", "Easy")),
                eye_style=hello.get("eye_style", "Normal") if hello.get("eye_style", "Normal") in EYE_STYLES else "Normal",
                body_style=hello.get("body_style", "Rounded") if hello.get("body_style", "Rounded") in BODY_STYLES else "Rounded",
                trail_style=hello.get("trail_style", "None") if hello.get("trail_style", "None") in TRAIL_STYLES else "None",
                skin_theme=hello.get("skin_theme", "Default") if hello.get("skin_theme", "Default") in SKIN_THEMES else "Default",
                head_style=hello.get("head_style", "Classic") if hello.get("head_style", "Classic") in HEAD_STYLES else "Classic",
            )
            if reconnect_snapshot:
                old_info: ClientInfo = reconnect_snapshot["info"]
                info.role = old_info.role
                info.style = old_info.style
                info.controls = old_info.controls
                info.level_pref = old_info.level_pref
                info.eye_style = old_info.eye_style
                info.body_style = old_info.body_style
                info.trail_style = old_info.trail_style
                info.skin_theme = old_info.skin_theme
                info.head_style = old_info.head_style
                info.chat_times = list(old_info.chat_times)
                info.move_times = list(old_info.move_times)
                info.ping_ms = old_info.ping_ms
                info.ping_samples = list(old_info.ping_samples)
                info.disconnects = old_info.disconnects
                info.timeouts = old_info.timeouts
                info.reconnects = old_info.reconnects + 1
                info.chat_throttle_hits = old_info.chat_throttle_hits
                info.move_throttle_hits = old_info.move_throttle_hits
                info.last_seen = time.time()
            elif username in self.clients:
                send_msg(sock, {"type": "error", "msg": "Username taken"})
                sock.close()
                return
            self.clients[username] = info
            self.disconnected_sessions.pop(username, None)
        self.scoreboard.record_user(username)
        send_msg(sock, {"type": "hello_ok", "username": username})
        self.log_line(f"{username} connected from {info.addr} via handshake")
        if reconnect_snapshot:
            self.log_line(f"{username} reconnected from {info.addr}")
            self._network_event("reconnect", f"{username} reconnected", username=username, extra={"addr": info.addr})
            self._send_to(username, {"type": "banner", "text": "Reconnected successfully"})
        else:
            self.broadcast_system(f"[SERVER] {username} joined the lobby")
            self._network_event("connect", f"{username} joined", username=username, extra={"addr": info.addr})
        self._send_lobby(username)
        self._broadcast_lobby()
        if reconnect_snapshot and self.game_state and not self.game_state.finished and username in self.game_players:
            state = self.game_state.serialize(sum(1 for c in self.clients.values() if c.role == "viewer"), FPS, typing_users=[name for name, ci in self.clients.items() if ci.typing_until > time.time() and ci.role in ("player", "viewer")])
            if username in state["stats"]:
                state["your_ping"] = round(info.ping_ms, 1)
            self._send_to(username, state)
        try:
            while True:
                msg = recv_msg(sock)
                if not msg:
                    break
                with self.lock:
                    if username in self.clients:
                        self.clients[username].last_seen = time.time()
                if self._process_message(username, msg) is False:
                    break
        finally:
            self._disconnect(username, reason="socket_closed")

    def _disconnect(self, username: str, reason: str = "disconnect", graceful: bool = False, allow_reconnect: Optional[bool] = None):
        if allow_reconnect is None:
            allow_reconnect = reason in ("disconnect", "socket_closed", "timeout")
        disconnect_banner = None
        with self.lock:
            info = self.clients.pop(username, None)
            self.pending_challenges.pop(username, None)
            self.pending_rematch.pop(username, None)
            for k, v in list(self.pending_challenges.items()):
                if v == username:
                    self.pending_challenges.pop(k, None)
            active_game = info and username in self.game_players and self.game_state and not self.game_state.finished
            session = None
            if info and allow_reconnect and not graceful and reason not in ("kicked", "shutdown"):
                session = self._store_disconnected_session(username, info, reason, allow_reconnect=True)
                info.disconnects += 1
            elif info and reason == "timeout":
                info.timeouts += 1
            if info and active_game and not session:
                other = next((p for p in self.game_players if p != username), None)
                if other:
                    self.game_state.finished = True
                    self.game_state.winner = other
                    disconnect_banner = (other, {"type": "banner", "text": f"{username} disconnected"})
            stats = get_socket_stats(info.sock) if info else None
            if info:
                try:
                    info.sock.close()
                except Exception:
                    pass
        if info:
            self.log_line(f"{username} disconnected ({reason})")
            if stats:
                self.log_line(
                    f"{username} traffic sent={stats.get('bytes_sent',0)}B recv={stats.get('bytes_received',0)}B "
                    f"msgs_out={stats.get('messages_sent',0)} msgs_in={stats.get('messages_received',0)} "
                    f"throughput_out={stats.get('throughput_sent_bps',0):.1f}B/s throughput_in={stats.get('throughput_received_bps',0):.1f}B/s"
                )
            if session:
                self._network_event("disconnect", f"{username} disconnected ({reason})", username=username, extra={"addr": info.addr, "reconnect_window": self.reconnect_window})
            else:
                self.broadcast_system(f"[SERVER] {username} left the lobby")
                self._network_event("disconnect", f"{username} disconnected ({reason})", username=username, extra={"addr": info.addr})
        if disconnect_banner:
            self._send_to(*disconnect_banner)
        self._broadcast_lobby()

    def _send_lobby(self, username: str):
        with self.lock:
            me = self.clients.get(username)
            if not me:
                return
            online = []
            for name, info in self.clients.items():
                if name == username or info.role != "lobby":
                    continue
                sb = self.scoreboard.data.get(name, {})
                online.append({
                    "name": name,
                    "wins": sb.get("wins", 0),
                    "style": info.style,
                    "head_style": info.head_style,
                    "skin_theme": info.skin_theme,
                    "role": info.role,
                    "ping_ms": round(info.ping_ms, 1),
                    "presence": "typing" if info.typing_until > time.time() else "online",
                })
            online.append({"name": "BOT", "wins": 999, "style": "Violet", "head_style": "Robot", "skin_theme": "Cyber", "role": "bot", "ping_ms": 0.0, "presence": "ready"})
            game_active = self.game_state is not None and not self.game_state.finished
            typing = [name for name, info in self.clients.items() if info.typing_until > time.time() and name != username]
            msg = {
                "type": "lobby",
                "online": online,
                "game_active": game_active,
                "players_in_game": self.game_players,
                "chat_history": self.chat_history[-25:],
                "scoreboard": self.scoreboard.top(),
                "levels": list(LEVELS.keys()),
                "typing": typing[:3],
                "network_events": self.network_events[-12:],
            }
        send_msg(me.sock, msg)

    def _broadcast_lobby(self):
        with self.lock:
            names = list(self.clients)
        for n in names:
            self._send_lobby(n)

    def _broadcast(self, msg: dict, roles: Optional[List[str]] = None):
        with self.lock:
            infos = list(self.clients.values())
        for info in infos:
            if roles and info.role not in roles:
                continue
            send_msg(info.sock, msg)

    def _send_to(self, username: str, msg: dict):
        with self.lock:
            info = self.clients.get(username)
        if info:
            send_msg(info.sock, msg)

    def _stats_summary(self) -> str:
        with self.lock:
            infos = list(self.clients.values())
            active_clients = len(infos)
            roles = [info.role for info in infos]
            reconnecting = len(self.disconnected_sessions)
        total_sent = total_recv = total_out = total_in = 0
        total_tp_out = total_tp_in = 0.0
        total_ping = 0.0
        ping_count = 0
        for info in infos:
            stats = get_socket_stats(info.sock)
            total_sent += stats.get("bytes_sent", 0)
            total_recv += stats.get("bytes_received", 0)
            total_out += stats.get("messages_sent", 0)
            total_in += stats.get("messages_received", 0)
            total_tp_out += stats.get("throughput_sent_bps", 0.0)
            total_tp_in += stats.get("throughput_received_bps", 0.0)
            if info.ping_ms:
                total_ping += info.ping_ms
                ping_count += 1
        avg_ping = total_ping / ping_count if ping_count else 0.0
        return (
            f"clients={active_clients} players={roles.count('player')} viewers={roles.count('viewer')} "
            f"lobby={roles.count('lobby')} bytes_sent={total_sent} bytes_recv={total_recv} "
            f"msg_out={total_out} msg_in={total_in} avg_ping={avg_ping:.1f}ms reconnecting={reconnecting} tick={FPS} "
            f"throughput_out={total_tp_out:.1f}B/s throughput_in={total_tp_in:.1f}B/s"
        )

    def _player_network_snapshot(self, username: str) -> dict:
        with self.lock:
            info = self.clients.get(username)
            session = self.disconnected_sessions.get(username)
            if info:
                sock_stats = get_socket_stats(info.sock)
                ping_samples = list(info.ping_samples)
                avg_ping = sum(ping_samples) / len(ping_samples) if ping_samples else info.ping_ms
                return {
                    "username": username,
                    "addr": info.addr,
                    "role": info.role,
                    "avg_ping_ms": round(avg_ping, 1) if avg_ping else 0.0,
                    "messages_sent": sock_stats.get("messages_sent", 0),
                    "messages_received": sock_stats.get("messages_received", 0),
                    "bytes_sent": sock_stats.get("bytes_sent", 0),
                    "bytes_received": sock_stats.get("bytes_received", 0),
                    "throughput_sent_bps": round(sock_stats.get("throughput_sent_bps", 0), 1),
                    "throughput_received_bps": round(sock_stats.get("throughput_received_bps", 0), 1),
                    "acks_sent": sock_stats.get("acks_sent", 0),
                    "acks_received": sock_stats.get("acks_received", 0),
                    "disconnects": info.disconnects,
                    "timeouts": info.timeouts,
                    "reconnects": info.reconnects,
                    "chat_throttle_hits": info.chat_throttle_hits,
                    "move_throttle_hits": info.move_throttle_hits,
                }
            if session:
                sock_stats = session.get("sock_stats", {})
                ping_samples = list(session.get("ping_samples", []))
                avg_ping = sum(ping_samples) / len(ping_samples) if ping_samples else sock_stats.get("avg_ping_ms", 0.0)
                return {
                    "username": username,
                    "addr": session.get("addr", ""),
                    "role": session.get("last_role", "lobby"),
                    "avg_ping_ms": round(avg_ping, 1) if avg_ping else 0.0,
                    "messages_sent": sock_stats.get("messages_sent", 0),
                    "messages_received": sock_stats.get("messages_received", 0),
                    "bytes_sent": sock_stats.get("bytes_sent", 0),
                    "bytes_received": sock_stats.get("bytes_received", 0),
                    "throughput_sent_bps": round(sock_stats.get("throughput_sent_bps", 0), 1),
                    "throughput_received_bps": round(sock_stats.get("throughput_received_bps", 0), 1),
                    "acks_sent": sock_stats.get("acks_sent", 0),
                    "acks_received": sock_stats.get("acks_received", 0),
                    "disconnects": session.get("disconnects", 0),
                    "timeouts": session.get("timeouts", 0),
                    "reconnects": session.get("reconnects", 0),
                    "chat_throttle_hits": session.get("chat_throttle_hits", 0),
                    "move_throttle_hits": session.get("move_throttle_hits", 0),
                }
        return {
            "username": username,
            "addr": "",
            "role": "unknown",
            "avg_ping_ms": 0.0,
            "messages_sent": 0,
            "messages_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "throughput_sent_bps": 0.0,
            "throughput_received_bps": 0.0,
            "acks_sent": 0,
            "acks_received": 0,
            "disconnects": 0,
            "timeouts": 0,
            "reconnects": 0,
            "chat_throttle_hits": 0,
            "move_throttle_hits": 0,
        }

    def _record_chat(self, sender: str, text: str, private_to: Optional[str] = None, style: str = "Normal"):
        entry = {
            "type": "chat",
            "id": self.next_chat_id,
            "sender": sender,
            "text": text,
            "ts": time.time(),
            "private_to": private_to,
            "style": style if style in CHAT_STYLES else "Normal",
            "reactions": {},
        }
        self.next_chat_id += 1
        self.chat_history.append(entry)
        self.chat_history = self.chat_history[-200:]
        return entry

    def _process_message(self, username: str, msg: dict):
        if not self._validate_message(username, msg):
            return True
        t = msg["type"]
        if t == "chat" and self._rate_limited(username, "chat", CHAT_LIMIT, CHAT_WINDOW_SEC):
            with self.lock:
                if username in self.clients:
                    self.clients[username].chat_throttle_hits += 1
            self._warn(username, "Chat rate limit exceeded", kind="chat_rate_limit")
            self.log_line(f"rate limit chat blocked for {username}")
            return True
        if t == "move" and self._rate_limited(username, "move", MOVE_LIMIT, MOVE_WINDOW_SEC):
            with self.lock:
                if username in self.clients:
                    self.clients[username].move_throttle_hits += 1
            self._warn(username, "Movement packets throttled", kind="move_throttle")
            return True
        handler = self.handlers.get(t)
        if handler:
            return handler(username, msg)
        return True

    def _handle_get_lobby_msg(self, username: str, msg: dict):
        self._send_lobby(username)
        return True

    def _handle_challenge_msg(self, username: str, msg: dict):
        target = msg.get("target")
        if not isinstance(target, str):
            self._send_to(username, {"type": "error", "msg": "Invalid challenge target"})
            return True
        self.log_line(f"{username} challenged {target}")
        self._handle_challenge(username, target, msg.get("level_name", msg.get("map_name")))
        return True

    def _handle_challenge_accept_msg(self, username: str, msg: dict):
        challenger = self.pending_challenges.pop(username, None)
        if challenger and challenger in self.clients:
            self._start_game(challenger, username, self.clients[challenger].level_pref)
        return True

    def _handle_challenge_decline_msg(self, username: str, msg: dict):
        challenger = self.pending_challenges.pop(username, None)
        if challenger:
            self._send_to(challenger, {"type": "challenge_declined", "opponent": username})
        return True

    def _handle_watch_msg(self, username: str, msg: dict):
        with self.lock:
            if username in self.clients:
                self.clients[username].role = "viewer"
        self._send_to(username, {"type": "watch_ok"})
        return True

    def _handle_move_msg(self, username: str, msg: dict):
        if self.game_state and not self.game_state.finished:
            d = DIRS.get(msg.get("dir"))
            if d and username in self.game_players:
                self.game_state.set_direction(username, d)
        return True

    def _handle_chat_msg(self, username: str, msg: dict):
        self._handle_chat(username, msg.get("text", ""), msg.get("style", "Normal"))
        return True

    def _handle_chat_reaction_msg(self, username: str, msg: dict):
        self._handle_chat_reaction(username, msg.get("message_id"), msg.get("emoji", ""))
        return True

    def _handle_cheer_msg(self, username: str, msg: dict):
        self._broadcast({"type": "cheer", "from": username, "target": msg.get("target", "")}, roles=["player", "viewer"])
        return True

    def _handle_rematch_request_msg(self, username: str, msg: dict):
        if username in self.game_players:
            other = next((p for p in self.game_players if p != username), None)
            if other:
                self.pending_rematch[other] = username
                self._send_to(other, {"type": "rematch_request", "from": username})
        return True

    def _handle_rematch_accept_msg(self, username: str, msg: dict):
        requester = self.pending_rematch.pop(username, None)
        if requester and requester in self.clients:
            self._start_game(requester, username, self.clients[requester].level_pref)
        return True

    def _handle_rematch_decline_msg(self, username: str, msg: dict):
        requester = self.pending_rematch.pop(username, None)
        if requester:
            self._send_to(requester, {"type": "rematch_declined"})
        return True

    def _handle_ping_msg(self, username: str, msg: dict):
        self._send_to(username, {"type": "pong", "client_ts": msg.get("client_ts", time.time())})
        return True

    def _handle_ping_sample_msg(self, username: str, msg: dict):
        with self.lock:
            if username in self.clients:
                value = float(msg.get("ping_ms", 0))
                self.clients[username].ping_ms = value
                self.clients[username].ping_samples.append(value)
                self.clients[username].ping_samples = self.clients[username].ping_samples[-40:]
        return True

    def _handle_cosmetic_update_msg(self, username: str, msg: dict):
        with self.lock:
            info = self.clients.get(username)
            if info:
                style = msg.get("style", info.style)
                info.style = style if style in STYLES else info.style
                eye_style = msg.get("eye_style", info.eye_style)
                info.eye_style = eye_style if eye_style in EYE_STYLES else info.eye_style
                body_style = msg.get("body_style", info.body_style)
                info.body_style = body_style if body_style in BODY_STYLES else info.body_style
                trail_style = msg.get("trail_style", info.trail_style)
                info.trail_style = trail_style if trail_style in TRAIL_STYLES else info.trail_style
                skin_theme = msg.get("skin_theme", info.skin_theme)
                info.skin_theme = skin_theme if skin_theme in SKIN_THEMES else info.skin_theme
                head_style = msg.get("head_style", info.head_style)
                info.head_style = head_style if head_style in HEAD_STYLES else info.head_style
        self._broadcast_lobby()
        return True

    def _handle_typing_msg(self, username: str, msg: dict):
        with self.lock:
            if username in self.clients:
                self.clients[username].typing_until = time.time() + 1.8
        self._broadcast_lobby()
        return True

    def _handle_heartbeat_msg(self, username: str, msg: dict):
        return True

    def _handle_disconnect_msg(self, username: str, msg: dict):
        self._disconnect(username, reason="graceful")
        return False

    def _handle_chat(self, username: str, text: str, style: str = "Normal"):
        text = text.strip()
        if not text:
            return
        if style not in CHAT_STYLES:
            style = "Normal"
        banned = ("idiot", "stupid")
        for word in banned:
            text = text.replace(word, "*" * len(word)).replace(word.title(), "*" * len(word)).replace(word.upper(), "*" * len(word))
        if text.startswith("/w "):
            parts = text.split(" ", 2)
            if len(parts) >= 3:
                target, body = parts[1], parts[2]
                entry = self._record_chat(username, body, private_to=target, style=style)
                self._send_to(username, entry)
                self._send_to(target, entry)
            return
        entry = self._record_chat(username, text, style=style)
        self._broadcast(entry)

    def _broadcast_auto_messages(self, messages: List[dict]):
        for msg in messages:
            entry = self._record_chat(msg["sender"], msg["text"], style=msg.get("style", "Normal"))
            self._broadcast(entry)

    def _handle_chat_reaction(self, username: str, message_id, emoji: str):
        if emoji not in CHAT_REACTIONS:
            return
        try:
            message_id = int(message_id)
        except (TypeError, ValueError):
            return

        target = None
        with self.lock:
            for entry in self.chat_history:
                if entry.get("id") == message_id:
                    target = entry
                    break
            if not target:
                return
            reactions = target.setdefault("reactions", {})
            users = reactions.setdefault(emoji, [])
            if username in users:
                users.remove(username)
                if not users:
                    reactions.pop(emoji, None)
            else:
                users.append(username)
            update = {"type": "chat_reaction", "message": target}

        if target.get("private_to"):
            self._send_to(target["sender"], update)
            self._send_to(target["private_to"], update)
        else:
            self._broadcast(update)

    def _handle_challenge(self, challenger: str, target: str, level_name: Optional[str]):
        with self.lock:
            if challenger in self.clients and level_name in LEVELS:
                self.clients[challenger].level_pref = level_name
            busy = self.game_state is not None and not self.game_state.finished
        if busy:
            self._send_to(challenger, {"type": "error", "msg": "A match is already running"})
            return
        if target == "BOT":
            self._network_event("challenge", f"{challenger} challenged BOT", username=challenger, extra={"target": target, "level": level_name or "Easy"})
            self._start_game(challenger, "BOT", level_name or "Easy", bot_player="BOT")
            return
        with self.lock:
            if target not in self.clients or self.clients[target].role != "lobby":
                self._send_to(challenger, {"type": "error", "msg": "Target unavailable"})
                return
            self.pending_challenges[target] = challenger
        self._network_event("challenge", f"{challenger} challenged {target}", username=challenger, extra={"target": target, "level": level_name or "Easy"})
        self._send_to(target, {"type": "challenge_request", "from": challenger, "level_name": level_name or "Easy"})
        self._send_to(challenger, {"type": "banner", "text": f"Challenge sent to {target}"})

    def _start_game(self, p1: str, p2: str, level_name: str, bot_player: Optional[str] = None):
        with self.lock:
            styles = {
                p1: self.clients[p1].style if p1 in self.clients else "Emerald",
                p2: self.clients[p2].style if p2 in self.clients else "Violet",
            }
            cosmetics = {
                p1: {
                    "eye_style": self.clients[p1].eye_style if p1 in self.clients else "Normal",
                    "body_style": self.clients[p1].body_style if p1 in self.clients else "Rounded",
                    "trail_style": self.clients[p1].trail_style if p1 in self.clients else "None",
                    "skin_theme": self.clients[p1].skin_theme if p1 in self.clients else "Default",
                    "head_style": self.clients[p1].head_style if p1 in self.clients else "Classic",
                },
                p2: {
                    "eye_style": self.clients[p2].eye_style if p2 in self.clients else "Robot",
                    "body_style": self.clients[p2].body_style if p2 in self.clients else "Segmented",
                    "trail_style": self.clients[p2].trail_style if p2 in self.clients else "Neon",
                    "skin_theme": self.clients[p2].skin_theme if p2 in self.clients else "Cyber",
                    "head_style": self.clients[p2].head_style if p2 in self.clients else "Robot",
                },
            }
            self.game_players = [p1, p2]
            self.game_state = GameState(p1, p2, styles, cosmetics, level_name, bot_player=bot_player)
            for name, info in self.clients.items():
                if name in self.game_players:
                    info.role = "player"
                elif info.role != "viewer":
                    info.role = "lobby"
        self.log_line(f"match start {p1} vs {p2} level={level_name}")
        self._network_event("match_started", f"Match started: {p1} vs {p2}", extra={"p1": p1, "p2": p2, "level": level_name})
        for name in [p1, p2]:
            if name != "BOT":
                self._send_to(name, {
                    "type": "game_start",
                    "you": name,
                    "opponent": p2 if name == p1 else p1,
                    "board_w": BOARD_W,
                    "board_h": BOARD_H,
                    "cell": CELL,
                    "level_name": level_name,
                    "map_name": level_name,
                })
        self._broadcast({"type": "game_started", "p1": p1, "p2": p2, "level_name": level_name, "map_name": level_name}, roles=["viewer"])
        self._broadcast_lobby()
        threading.Thread(target=self._game_loop, daemon=True).start()

    def _finish_game(self):
        gs = self.game_state
        if not gs:
            return
        duration = (time.time() - gs.start_time) if gs.start_time else 0.0
        winner = gs.winner
        loser = None
        if winner and winner != "Draw":
            loser = gs.p2 if winner == gs.p1 else gs.p1
            if loser == "BOT":
                loser = None
        stats = {k: v for k, v in gs.stats.items() if k != "BOT"}
        if winner == "BOT":
            winner = None
        # Update scoreboard BEFORE sending result to clients so lobby refresh shows new scores.
        self.scoreboard.record_game(winner or "Draw", loser, stats)
        player_network = {
            gs.p1: self._player_network_snapshot(gs.p1),
            gs.p2: self._player_network_snapshot(gs.p2),
        }
        self.append_jsonl(MATCH_HISTORY_FILE, {
            "ts": time.time(),
            "players": [gs.p1, gs.p2],
            "level": gs.level_name,
            "winner": gs.winner,
            "loser": loser,
            "duration_sec": round(duration, 2),
            "stats": stats,
            "network": player_network,
        })
        self.append_jsonl(REPLAY_FILE, {
            "ts": time.time(),
            "players": [gs.p1, gs.p2],
            "level": gs.level_name,
            "winner": gs.winner,
            "events": gs.replay_events,
            "frames": gs.replay_frames[-900:],
        })

        # Step 1: send a dedicated match_result packet so clients always know the
        # canonical winner even if the last game_state was missed or stale.
        match_result_packet = {
            "type": "match_result",
            "winner": gs.winner,
            "p1": gs.p1,
            "p2": gs.p2,
            "level_name": gs.level_name,
            "duration_sec": round(duration, 2),
            "stats": gs.stats,
            "health": gs.health,
            "scoreboard": self.scoreboard.top(),
        }

        # Step 2: send one final authoritative game_state snapshot before changing roles.
        final_state = gs.serialize(0, FPS, typing_users=[])
        final_state["snapshot_seq"] = gs.tick

        with self.lock:
            recipients = [c for c in self.clients.values() if c.role in ("player", "viewer")]

        for info in recipients:
            try:
                send_msg(info.sock, final_state)
            except Exception:
                pass
            try:
                send_msg(info.sock, match_result_packet)
            except Exception:
                pass

        self.log_line(f"winner = {gs.winner} level={gs.level_name} duration={duration:.1f}s")
        self._network_event("match_ended", f"Match ended: {gs.winner}", extra={"winner": gs.winner, "level": gs.level_name, "duration_sec": round(duration, 2)})

        # Step 3: reset player roles and refresh lobby AFTER clients received result.
        with self.lock:
            for name, info in self.clients.items():
                if info.role == "player":
                    info.role = "lobby"
        self._broadcast_lobby()

    def _game_loop(self):
        last = time.time()
        while True:
            time.sleep(1 / FPS)
            gs = self.game_state
            if not gs:
                return
            now = time.time()
            dt = now - last
            last = now
            gs.tick_game(dt)
            self._broadcast_auto_messages(gs.drain_auto_messages())
            with self.lock:
                spectators = sum(1 for c in self.clients.values() if c.role == "viewer")
                players = list(self.game_players)
                recipients = [c for c in self.clients.values() if c.role in ("player", "viewer")]
                typing_users = [c.username for c in self.clients.values() if c.typing_until > time.time() and c.role in ("player", "viewer")]
            state = gs.serialize(spectators, FPS, typing_users=typing_users)
            state["snapshot_seq"] = gs.tick
            state["replication_mode"] = "full_snapshot"
            if gs.tick % 2 == 0:
                gs.replay_frames.append(gs.replay_frame(spectators, FPS))
                gs.replay_frames = gs.replay_frames[-900:]
            for info in recipients:
                if info.username in state["stats"]:
                    state["your_ping"] = round(info.ping_ms, 1)
                send_msg(info.sock, state)
            if gs.finished:
                self._finish_game()
                return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ultimate Pithon Arena Server")
    parser.add_argument("port", type=int)
    args = parser.parse_args()
    PithonServer(args.port).start()
