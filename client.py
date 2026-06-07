"""Ultimate Python Arena client with richer UI, sounds, particles,
scoreboard, level selection, ping display, bot mode, chat whispers,
and enhanced result screen.
"""

from __future__ import annotations

import json
import math
import os
import random
import socket
import sys
import threading
import time
from array import array
from typing import Dict, List, Optional, Tuple

import pygame

from network import get_protocol_log, get_socket_stats, recv_msg, send_msg

WINDOW_W = 1472
WINDOW_H = 1032
FPS = 60
CELL = 20
REPLAY_FILE = os.path.join(os.path.dirname(__file__), "replay_log.jsonl")
ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
CONNECT_BG = os.path.join(ASSET_DIR, "python_arena_connect_bg.png")
GAME_BG = os.path.join(ASSET_DIR, "python_arena_game_bg.png")
LOBBY_BG = os.path.join(ASSET_DIR, "python_arena_lobby_bg.png")
SPLASH_IMAGE = os.path.join(os.path.dirname(__file__), "splash_clean.png")
# Button bounds in the source splash artwork, stored as x, y, w, h ratios.
SPLASH_START_BUTTON = (0.374, 0.850, 0.252, 0.118)
USE_IMAGE_TEMPLATE_UI = False
_SURFACE_CACHE: Dict[tuple, pygame.Surface] = {}
_IMAGE_CACHE: Dict[str, pygame.Surface] = {}
_COVER_CACHE: Dict[tuple, Tuple[pygame.Surface, pygame.Rect]] = {}
CONNECT_OPTION_W = 148
CONNECT_OPTION_H = 42
CONNECT_OPTION_GAP = 14
CONNECT_LAYOUT = {
    "controls_label_y": 536,
    "controls_row_y": 560,
    "style_label_y": 622,
    "style_row_y": 646,
    "map_label_y": 708,
    "map_row_y": 732,
    "connect_y": 832,
    "error_y": 900,
}

BLACK = (3, 7, 22)
DARK = (8, 13, 35)
PANEL = (15, 26, 55)
PANEL2 = (10, 18, 42)
HEADER = (32, 22, 78)
FIELD = (9, 20, 47)
WOOD_DARK = (91, 50, 20)
WOOD = (149, 86, 31)
WOOD_LIGHT = (228, 155, 58)
BAMBOO = (214, 145, 48)
BAMBOO_DARK = (88, 48, 16)
LEAF = (38, 154, 75)
LEAF_DARK = (10, 82, 50)
HIBISCUS = (245, 78, 145)
SAND = (113, 73, 43)
WHITE = (232, 239, 255)
GRAY = (136, 148, 182)
GOLD = (255, 211, 23)
RED = (255, 82, 94)
GREEN = (91, 246, 123)
BLUE = (80, 177, 255)
CYAN = (67, 238, 230)
MAGENTA = (246, 65, 205)
PURPLE = (174, 76, 255)
VIOLET = PURPLE
VIOLET_DARK = (25, 15, 61)
PANEL_BORDER = (132, 70, 235)
SOFT_BORDER = (45, 70, 115)
MUTED = (147, 158, 190)
ICE = (166, 218, 255)
CHAT_REACTIONS = ["🔥", "😄", "💀", "👀"]
QUICK_CHAT_OPTIONS = ["GG!", "Nice move!", "Help!", "Watch out!"]
CHAT_STYLE_OPTIONS = ["Normal", "Angry", "Troll", "Robot"]
EYE_OPTIONS = ["Normal", "Sunglasses", "Glowing", "Robot"]
BODY_OPTIONS = ["Rounded", "Square", "Spiky", "Segmented"]
TRAIL_OPTIONS = ["None", "Sparkle", "Smoke", "Neon", "Rainbow"]
THEME_OPTIONS = ["Default", "Inferno", "Ice", "Galaxy", "Cyber"]
HEAD_OPTIONS = ["Classic", "Dragon", "Skull", "Cat", "Pixel", "Robot"]

STYLE_COLORS = {
    "Emerald": ((90, 230, 140), (40, 165, 90)),
    "Sapphire": ((90, 150, 255), (48, 92, 205)),
    "Violet": ((205, 125, 255), (140, 80, 220)),
}
LEVELS = ["Easy", "Medium", "Hard", "Impossible"]
CONTROLS = ["Arrows", "WASD", "IJKL"]

pygame.init()
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=1)
    SOUND_OK = True
except Exception:
    SOUND_OK = False


def load_fonts(scale=1.0):
    title_size = max(20, int(62 * scale))
    big_size = max(13, int(30 * scale))
    med_size = max(10, int(20 * scale))
    small_size = max(9, int(15 * scale))
    robot_size = max(9, int(16 * scale))
    try:
        title_face = "arialrounded" if sys.platform == "darwin" else "arial"
        body_face = "arial" if sys.platform == "darwin" else "dejavusans"
        return (
            pygame.font.SysFont(title_face, title_size, bold=True),
            pygame.font.SysFont(title_face, big_size, bold=True),
            pygame.font.SysFont(body_face, med_size, bold=True),
            pygame.font.SysFont(body_face, small_size),
            pygame.font.SysFont("couriernew", robot_size, bold=True),
        )
    except Exception:
        return (
            pygame.font.Font(None, max(36, title_size + 4)),
            pygame.font.Font(None, max(24, big_size + 4)),
            pygame.font.Font(None, max(18, med_size + 4)),
            pygame.font.Font(None, max(14, small_size + 3)),
            pygame.font.Font(None, max(14, robot_size + 3)),
        )


def draw_center(surface, text, font, color, x, y):
    img = font.render(str(text), True, color)
    surface.blit(img, img.get_rect(center=(x, y)))


def draw_alpha_rect(surface, color, rect, alpha=180, radius=8):
    s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(s, (*color, alpha), (0, 0, rect[2], rect[3]), border_radius=radius)
    surface.blit(s, (rect[0], rect[1]))


def draw_shadow(surface, rect, radius=16, strength=90, offset=(0, 8)):
    r = pygame.Rect(rect).move(offset)
    key = ("shadow", r.w, r.h, radius, strength)
    cached = _SURFACE_CACHE.get(key)
    if cached is None:
        pad = 18
        cached = pygame.Surface((r.w + pad * 2, r.h + pad * 2), pygame.SRCALPHA)
        for grow, alpha in ((18, strength // 4), (10, strength // 3), (4, strength // 2)):
            pygame.draw.rect(cached, (0, 0, 0, alpha), (pad - grow, pad - grow, r.w + grow * 2, r.h + grow * 2), border_radius=radius + grow)
        if len(_SURFACE_CACHE) < 700:
            _SURFACE_CACHE[key] = cached
    surface.blit(cached, (r.x - 18, r.y - 18))


def _gradient_surface(w, h, top_color, bottom_color, alpha=255, radius=0):
    key = ("grad", w, h, top_color, bottom_color, alpha, radius)
    cached = _SURFACE_CACHE.get(key)
    if cached is not None:
        return cached
    grad = pygame.Surface((w, h), pygame.SRCALPHA)
    for yy in range(h):
        t = yy / max(1, h - 1)
        col = mix_color(top_color, bottom_color, t)
        pygame.draw.line(grad, (*col, alpha), (0, yy), (w, yy))
    if radius:
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=radius)
        grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    if len(_SURFACE_CACHE) < 700:
        _SURFACE_CACHE[key] = grad
    return grad


def draw_vertical_gradient(surface, rect, top_color, bottom_color, alpha=255, radius=0):
    r = pygame.Rect(rect)
    if r.w <= 0 or r.h <= 0:
        return
    surface.blit(_gradient_surface(r.w, r.h, top_color, bottom_color, alpha, radius), r.topleft)


def draw_shadow_uncached(surface, rect, radius=16, strength=90, offset=(0, 8)):
    r = pygame.Rect(rect).move(offset)
    for grow, alpha in ((18, strength // 4), (10, strength // 3), (4, strength // 2)):
        s = pygame.Surface((r.w + grow * 2, r.h + grow * 2), pygame.SRCALPHA)
        pygame.draw.rect(s, (0, 0, 0, alpha), (0, 0, s.get_width(), s.get_height()), border_radius=radius + grow)
        surface.blit(s, (r.x - grow, r.y - grow))


def draw_text(surface, text, font, color, x, y):
    img = font.render(str(text), True, color)
    surface.blit(img, (x, y))


def fit_text(text, font, max_width):
    text = str(text)
    if font.render(text, True, WHITE).get_width() <= max_width:
        return text
    ellipsis = "..."
    while text and font.render(text + ellipsis, True, WHITE).get_width() > max_width:
        text = text[:-1]
    return (text + ellipsis) if text else ellipsis


def rect_pct(base, x, y, w, h) -> pygame.Rect:
    if isinstance(base, pygame.Surface):
        base = base.get_rect()
    base = pygame.Rect(base)
    return pygame.Rect(
        int(base.x + base.w * x),
        int(base.y + base.h * y),
        max(1, int(base.w * w)),
        max(1, int(base.h * h)),
    )


def create_hitbox_map(base_rect: pygame.Rect, zones: dict) -> dict:
    return {name: rect_pct(base_rect, *values) for name, values in zones.items()}


def load_asset(path: str) -> Optional[pygame.Surface]:
    cached = _IMAGE_CACHE.get(path)
    if cached is not None:
        return cached
    try:
        image = pygame.image.load(path).convert()
    except (FileNotFoundError, pygame.error):
        return None
    _IMAGE_CACHE[path] = image
    return image


def cover_rect_for_size(image_size: Tuple[int, int], bounds: pygame.Rect) -> pygame.Rect:
    src_w, src_h = image_size
    scale = max(bounds.w / src_w, bounds.h / src_h)
    new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    rect = pygame.Rect(0, 0, *new_size)
    rect.center = bounds.center
    return rect


def draw_scaled_bg_cover(surface: pygame.Surface, image_path: str) -> Optional[pygame.Rect]:
    image = load_asset(image_path)
    if image is None:
        return None
    bounds = surface.get_rect()
    key = (image_path, bounds.size)
    cached = _COVER_CACHE.get(key)
    if cached is None:
        rect = cover_rect_for_size(image.get_size(), bounds)
        scaled = pygame.transform.smoothscale(image, rect.size)
        cached = (scaled, rect)
        if len(_COVER_CACHE) < 48:
            _COVER_CACHE[key] = cached
    scaled, rect = cached
    surface.blit(scaled, rect)
    return rect


def draw_text_shadow(surface, text, font, color, x, y, center=False, shadow=(0, 0, 0), max_width=None):
    text = fit_text(text, font, max_width) if max_width else str(text)
    img = font.render(text, True, color)
    shadow_img = font.render(text, True, shadow)
    shadow_img.set_alpha(190)
    rect = img.get_rect(center=(x, y)) if center else img.get_rect(topleft=(x, y))
    surface.blit(shadow_img, rect.move(2, 2))
    surface.blit(img, rect)
    return rect


def draw_text_fit(surface, text, *args, center=True, shadow=True, align=None):
    if len(args) < 3:
        raise TypeError("draw_text_fit needs rect/font/color arguments")
    if hasattr(args[0], "render"):
        font, color, rect = args[:3]
        align = align or ("center" if center else "left")
    else:
        rect, font, color = args[:3]
        align = align or ("center" if center else "left")
    rect = pygame.Rect(rect)
    text = str(text)
    max_width = max(1, rect.w - 10)
    max_height = max(1, rect.h - 4)
    render_font = font
    img = render_font.render(text, True, color)
    size = max(9, min(font.get_height(), rect.h + 4))
    while (img.get_width() > max_width or img.get_height() > max_height) and size > 9:
        size -= 1
        try:
            render_font = pygame.font.Font(None, size)
            img = render_font.render(text, True, color)
        except Exception:
            break
    if img.get_width() > max_width:
        text = fit_text(text, render_font, max_width)
        img = render_font.render(text, True, color)
    if align == "left":
        img_rect = img.get_rect(midleft=(rect.x + 8, rect.centery))
    elif align == "right":
        img_rect = img.get_rect(midright=(rect.right - 8, rect.centery))
    else:
        img_rect = img.get_rect(center=rect.center)
    if shadow:
        shadow_img = render_font.render(str(text), True, BLACK)
        shadow_img.set_alpha(190)
        surface.blit(shadow_img, img_rect.move(2, 2))
    surface.blit(img, img_rect)
    return img_rect


def draw_clean_text_area(surface, rect, alpha=130, radius=None):
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    alpha = max(0, min(255, int(alpha)))
    if alpha <= 0:
        return
    draw_alpha_rect(surface, BLACK, rect, alpha, radius=radius if radius is not None else max(6, rect.h // 4))


def draw_dynamic_value(surface, text, rect, font, color=WHITE, alpha=150, center=True):
    draw_clean_text_area(surface, rect, alpha=alpha)
    return draw_text_fit(surface, text, rect, font, color, center=center)


def draw_glow_outline(surface, rect, color, radius=10, width=2, alpha=150):
    rect = pygame.Rect(rect)
    for grow, glow_alpha in ((8, alpha // 4), (4, alpha // 2)):
        glow = pygame.Surface((rect.w + grow * 2, rect.h + grow * 2), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*color, glow_alpha), glow.get_rect(), width, border_radius=radius + grow)
        surface.blit(glow, (rect.x - grow, rect.y - grow))
    pygame.draw.rect(surface, color, rect, width, border_radius=radius)


def get_template_zones(screen, screen_name):
    bounds = screen.get_rect() if isinstance(screen, pygame.Surface) else pygame.Rect(screen)
    image_path = {
        "connect": CONNECT_BG,
        "lobby": LOBBY_BG,
        "game": GAME_BG,
    }.get(screen_name)
    bg = bounds
    if image_path:
        image = load_asset(image_path)
        if image is not None:
            bg = cover_rect_for_size(image.get_size(), bounds)
    if screen_name == "connect":
        return create_hitbox_map(bg, {
            "ip": (0.275, 0.345, 0.455, 0.048),
            "port": (0.275, 0.402, 0.455, 0.048),
            "user": (0.275, 0.459, 0.455, 0.048),
            "arrows": (0.276, 0.539, 0.141, 0.047),
            "wasd": (0.427, 0.539, 0.145, 0.047),
            "ijkl": (0.582, 0.539, 0.144, 0.047),
            "emerald": (0.274, 0.626, 0.140, 0.047),
            "sapphire": (0.423, 0.626, 0.146, 0.047),
            "violet": (0.586, 0.626, 0.141, 0.047),
            "easy": (0.250, 0.712, 0.114, 0.048),
            "medium": (0.380, 0.712, 0.114, 0.048),
            "hard": (0.508, 0.712, 0.114, 0.048),
            "insane": (0.636, 0.712, 0.114, 0.048),
            "tcp": (0.250, 0.776, 0.148, 0.048),
            "lan": (0.411, 0.776, 0.158, 0.048),
            "replay": (0.579, 0.776, 0.171, 0.048),
            "connect": (0.357, 0.850, 0.292, 0.087),
        }) | {"bg": bg}
    if screen_name == "lobby":
        return {
            "bg": bg,
            "left_name": rect_pct(bg, 0.175, 0.681, 0.165, 0.070),
            "center_name": rect_pct(bg, 0.405, 0.681, 0.200, 0.070),
            "right_name": rect_pct(bg, 0.675, 0.681, 0.165, 0.070),
            "start": rect_pct(bg, 0.365, 0.865, 0.270, 0.105),
            "tutorial": rect_pct(bg, 0.055, 0.825, 0.105, 0.135),
            "settings": rect_pct(bg, 0.775, 0.825, 0.105, 0.135),
            "leaderboard": rect_pct(bg, 0.875, 0.825, 0.105, 0.135),
        }
    if screen_name == "game":
        return {
            "bg": bg,
            "header": rect_pct(bg, 0.02, 0.03, 0.96, 0.14),
            "level_stats": rect_pct(bg, 0.046, 0.045, 0.120, 0.080),
            "timer": rect_pct(bg, 0.456, 0.207, 0.088, 0.058),
            "board": rect_pct(bg, 0.262, 0.255, 0.438, 0.555),
            "p1_card": rect_pct(bg, 0.038, 0.175, 0.185, 0.255),
            "p2_card": rect_pct(bg, 0.038, 0.465, 0.185, 0.255),
            "event_log": rect_pct(bg, 0.043, 0.754, 0.170, 0.075),
            "spectators": rect_pct(bg, 0.856, 0.137, 0.100, 0.035),
            "net_panel": rect_pct(bg, 0.758, 0.214, 0.210, 0.205),
            "chat_style_buttons": rect_pct(bg, 0.755, 0.420, 0.225, 0.055),
            "chat_panel": rect_pct(bg, 0.758, 0.492, 0.210, 0.300),
            "chat_input": rect_pct(bg, 0.205, 0.892, 0.345, 0.060),
            "send": rect_pct(bg, 0.565, 0.892, 0.070, 0.060),
            "player_name_bottom": rect_pct(bg, 0.675, 0.900, 0.080, 0.040),
        }
    return {"bg": bg}


def shift_color(color, amount):
    return tuple(max(0, min(255, c + amount)) for c in color)


def mix_color(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def draw_neon_rect(surface, rect, fill=PANEL2, border=PANEL_BORDER, radius=8, alpha=220, glow=True):
    r = pygame.Rect(rect)
    if glow:
        for grow, glow_alpha in ((10, 30), (5, 45)):
            glow_surf = pygame.Surface((r.w + grow * 2, r.h + grow * 2), pygame.SRCALPHA)
            pygame.draw.rect(
                glow_surf,
                (*border, glow_alpha),
                (0, 0, r.w + grow * 2, r.h + grow * 2),
                border_radius=radius + grow,
            )
            surface.blit(glow_surf, (r.x - grow, r.y - grow))
    draw_vertical_gradient(surface, r, mix_color(fill, WHITE, 0.05), mix_color(fill, BLACK, 0.18), alpha, radius)
    pygame.draw.rect(surface, border, r, 2, border_radius=radius)
    pygame.draw.line(surface, mix_color(border, WHITE, 0.35), (r.x + 12, r.y + 1), (r.right - 12, r.y + 1), 1)


def draw_wood_plank(surface, rect, radius=10, alpha=245):
    r = pygame.Rect(rect)
    radius = max(0, min(radius, r.w // 2, r.h // 2))
    draw_shadow(surface, r, radius=radius, strength=70, offset=(0, 5))
    key = ("wood", r.w, r.h, radius, alpha)
    body = _SURFACE_CACHE.get(key)
    if body is None:
        body = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        body.blit(_gradient_surface(r.w, r.h, mix_color(WOOD_LIGHT, WOOD, 0.25), mix_color(WOOD_DARK, WOOD, 0.35), alpha, radius), (0, 0))
        for i in range(4):
            y = int((i + 1) * r.h / 5)
            pygame.draw.line(body, (*mix_color(WOOD_DARK, WOOD_LIGHT, 0.22), 95), (16, y), (r.w - 16, y + int(math.sin(i * 1.7) * 2)), 1)
        for x in range(24, r.w, 92):
            pygame.draw.circle(body, (*WOOD_DARK, 120), (x, r.h // 2), max(2, min(4, r.h // 11)), 1)
        pygame.draw.rect(body, BAMBOO_DARK, (0, 0, r.w, r.h), 4, border_radius=radius)
        inner = pygame.Rect(0, 0, r.w, r.h).inflate(-6, -6)
        if inner.w >= 8 and inner.h >= 8:
            pygame.draw.rect(body, WOOD_LIGHT, inner, 2, border_radius=max(0, min(radius - 3, inner.w // 2, inner.h // 2)))
        if len(_SURFACE_CACHE) < 700:
            _SURFACE_CACHE[key] = body
    surface.blit(body, r.topleft)


def draw_bamboo_frame(surface, rect, radius=12, thickness=12):
    r = pygame.Rect(rect)
    draw_neon_rect(surface, r, FIELD, BAMBOO, radius=radius, alpha=198, glow=True)
    for side in ("top", "bottom"):
        y = r.y if side == "top" else r.bottom - thickness
        rail = pygame.Rect(r.x, y, r.w, thickness)
        draw_wood_plank(surface, rail, radius=thickness // 2, alpha=255)
        for x in range(r.x + 34, r.right - 12, 82):
            pygame.draw.line(surface, BAMBOO_DARK, (x, y + 2), (x + 5, y + thickness - 2), 2)
    for side in ("left", "right"):
        x = r.x if side == "left" else r.right - thickness
        rail = pygame.Rect(x, r.y, thickness, r.h)
        draw_wood_plank(surface, rail, radius=thickness // 2, alpha=255)
        for y in range(r.y + 34, r.bottom - 12, 82):
            pygame.draw.line(surface, BAMBOO_DARK, (x + 2, y), (x + thickness - 2, y + 5), 2)


def draw_flower(surface, x, y, scale=1.0, color=HIBISCUS):
    petal = max(4, int(9 * scale))
    center = max(3, int(4 * scale))
    for a in range(5):
        ang = a * math.tau / 5
        px = int(x + math.cos(ang) * petal)
        py = int(y + math.sin(ang) * petal)
        pygame.draw.ellipse(surface, color, (px - petal, py - petal // 2, petal * 2, petal), 0)
    pygame.draw.circle(surface, GOLD, (int(x), int(y)), center)


def draw_leaf_cluster(surface, x, y, scale=1.0, mirror=False):
    for i in range(7):
        ang = (-1.0 + i * 0.32) * (-1 if mirror else 1)
        length = int((34 + i % 3 * 8) * scale)
        end = (int(x + math.cos(ang) * length), int(y + math.sin(ang) * length))
        color = LEAF if i % 2 else LEAF_DARK
        pygame.draw.line(surface, color, (x, y), end, max(3, int(5 * scale)))
        pygame.draw.ellipse(surface, color, (min(x, end[0]) - int(7 * scale), min(y, end[1]) - int(5 * scale), abs(end[0] - x) + int(14 * scale), abs(end[1] - y) + int(10 * scale)), 1)


def draw_wood_title(surface, rect, lines, fonts, colors):
    r = pygame.Rect(rect)
    draw_wood_plank(surface, r, radius=18, alpha=252)
    draw_leaf_cluster(surface, r.x + 34, r.y + 22, 0.82)
    draw_leaf_cluster(surface, r.right - 34, r.y + 22, 0.82, mirror=True)
    draw_flower(surface, r.x + 54, r.y + 26, 0.9, (255, 190, 61))
    draw_flower(surface, r.right - 56, r.bottom - 26, 0.9, HIBISCUS)
    if len(lines) == 1:
        draw_glow_text(surface, lines[0], fonts[0], colors[0], r.center, WOOD_DARK)
    else:
        total_h = sum(font.get_height() for font in fonts[:len(lines)]) - int(fonts[0].get_height() * 0.18)
        y = r.centery - total_h // 2
        for text, font, color in zip(lines, fonts, colors):
            draw_glow_text(surface, text, font, color, (r.centerx, y + font.get_height() // 2), WOOD_DARK)
            y += int(font.get_height() * 0.82)


def draw_panel(surface, rect, title=None, font=None, icon=None, header_h=58):
    r = pygame.Rect(rect)
    draw_bamboo_frame(surface, r, radius=12, thickness=max(9, min(14, r.w // 34)))
    if title:
        header_w = min(r.w - 16, max(170, int(r.w * 0.72)))
        header = pygame.Rect(r.x + 16, r.y - max(10, header_h // 5), header_w, header_h)
        draw_wood_plank(surface, header, radius=12, alpha=252)
        draw_flower(surface, header.right - 16, header.y + 12, 0.62, HIBISCUS)
        tx = r.x + 70 if icon else r.x + 28
        if font:
            title_text = fit_text(title.upper(), font, max(40, header.right - tx - 18))
            draw_text(surface, title_text, font, WHITE, tx, header.y + max(8, (header_h - font.get_height()) // 2 - 2))
        if icon == "players":
            draw_people_icon(surface, r.x + 39, header.centery, WHITE)
        elif icon == "trophy":
            draw_trophy_icon(surface, r.x + 39, header.centery, WHITE)
        elif icon == "chat":
            draw_chat_icon(surface, r.x + 39, header.centery, WHITE)
        elif icon == "palette":
            draw_palette_icon(surface, r.x + 39, header.centery, WHITE)
    return r


def draw_glow_text(surface, text, font, color, center, glow_color=None):
    glow_color = glow_color or color
    for dx, dy, alpha in ((0, 0, 90), (2, 2, 55), (-2, -2, 55), (0, 3, 45)):
        img = font.render(str(text), True, glow_color)
        img.set_alpha(alpha)
        surface.blit(img, img.get_rect(center=(center[0] + dx, center[1] + dy)))
    img = font.render(str(text), True, color)
    surface.blit(img, img.get_rect(center=center))


def draw_logo(surface, font, x, y):
    gap_y = max(24, int(font.get_height() * 0.70))
    draw_glow_text(surface, "PYTHON", font, GOLD, (x, y), GREEN)
    draw_glow_text(surface, "ARENA", font, MAGENTA, (x, y + gap_y), MAGENTA)


def draw_top_icon(surface, center, label, color, badge=None):
    x, y = center
    pygame.draw.circle(surface, WOOD_DARK, (x, y), 31)
    pygame.draw.circle(surface, BAMBOO, (x, y), 29, 5)
    pygame.draw.circle(surface, (28, 73, 47), (x, y), 21)
    draw_center(surface, label, pygame.font.Font(None, 31), color, x, y + 1)
    if badge:
        pygame.draw.circle(surface, RED, (x + 20, y - 20), 13)
        draw_center(surface, badge, pygame.font.Font(None, 22), WHITE, x + 20, y - 20)


def draw_string_lights(surface, y, width, t):
    start_x = int(width * 0.06)
    end_x = int(width * 0.94)
    last = None
    bulbs = 16
    for i in range(bulbs):
        x = start_x + int((end_x - start_x) * i / (bulbs - 1))
        drop = int(18 * math.sin(i * 0.7 + t * 0.4))
        point = (x, y + drop)
        if last:
            pygame.draw.line(surface, (55, 31, 26), last, point, 3)
        last = point
        glow = pygame.Surface((34, 34), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 198, 73, 70), (17, 17), 15)
        surface.blit(glow, (x - 17, y + drop - 2))
        pygame.draw.circle(surface, (255, 220, 101), (x, y + drop + 9), 5)
        pygame.draw.line(surface, (55, 31, 26), (x, y + drop), (x, y + drop + 6), 2)


def draw_tropical_snake(surface, x, y, scale=1.0, color=(63, 214, 122), accent=(255, 218, 80)):
    pts = []
    for i in range(34):
        a = i / 33 * math.tau * 1.35
        rx = 74 * scale - i * 0.72 * scale
        ry = 98 * scale - i * 0.48 * scale
        pts.append((int(x + math.cos(a) * rx + i * 2.2 * scale), int(y + math.sin(a) * ry)))
    for i in range(len(pts) - 1, 0, -1):
        width = max(8, int((20 + i * 0.25) * scale))
        pygame.draw.line(surface, LEAF_DARK, pts[i], pts[i - 1], width + 4)
        pygame.draw.line(surface, color, pts[i], pts[i - 1], width)
        if i % 4 == 0:
            pygame.draw.circle(surface, accent, pts[i], max(2, int(4 * scale)))
    hx, hy = pts[0]
    head = pygame.Rect(hx - int(40 * scale), hy - int(28 * scale), int(78 * scale), int(56 * scale))
    pygame.draw.ellipse(surface, LEAF_DARK, head.inflate(8, 8))
    pygame.draw.ellipse(surface, color, head)
    pygame.draw.circle(surface, WHITE, (hx + int(15 * scale), hy - int(7 * scale)), int(11 * scale))
    pygame.draw.circle(surface, (11, 33, 35), (hx + int(18 * scale), hy - int(6 * scale)), int(5 * scale))
    pygame.draw.circle(surface, WHITE, (hx - int(13 * scale), hy - int(9 * scale)), int(10 * scale))
    pygame.draw.circle(surface, (11, 33, 35), (hx - int(10 * scale), hy - int(8 * scale)), int(5 * scale))
    pygame.draw.arc(surface, WOOD_DARK, (hx - int(18 * scale), hy + int(2 * scale), int(36 * scale), int(18 * scale)), 0.1, math.pi - 0.1, 2)
    draw_flower(surface, hx - int(32 * scale), hy - int(27 * scale), 0.75 * scale, HIBISCUS)
    draw_flower(surface, hx + int(3 * scale), hy - int(34 * scale), 0.65 * scale, (255, 190, 61))


def draw_robot_icon(surface, x, y, size=28, color=GREEN):
    half = size // 2
    head = pygame.Rect(x - half, y - half + 3, size, size - 4)
    pygame.draw.rect(surface, color, head, 2, border_radius=6)
    pygame.draw.circle(surface, color, (x - half - 5, y + 2), 4, 2)
    pygame.draw.circle(surface, color, (x + half + 5, y + 2), 4, 2)
    pygame.draw.line(surface, color, (x, y - half + 3), (x, y - half - 8), 2)
    pygame.draw.circle(surface, color, (x, y - half - 10), 3)
    pygame.draw.circle(surface, color, (x - 7, y), 3)
    pygame.draw.circle(surface, color, (x + 7, y), 3)
    pygame.draw.line(surface, color, (x - 8, y + 9), (x + 8, y + 9), 2)


def draw_people_icon(surface, x, y, color):
    pygame.draw.circle(surface, color, (x - 8, y - 8), 5)
    pygame.draw.circle(surface, color, (x + 7, y - 9), 5)
    pygame.draw.rect(surface, color, (x - 17, y, 14, 11), border_radius=5)
    pygame.draw.rect(surface, color, (x + 1, y, 14, 11), border_radius=5)
    pygame.draw.rect(surface, color, (x - 7, y + 4, 14, 9), border_radius=5)


def draw_trophy_icon(surface, x, y, color):
    cup = pygame.Rect(x - 10, y - 14, 20, 17)
    pygame.draw.rect(surface, color, cup, 2, border_radius=4)
    pygame.draw.arc(surface, color, (x - 24, y - 12, 16, 18), math.pi * 1.5, math.pi * 2.2, 2)
    pygame.draw.arc(surface, color, (x + 8, y - 12, 16, 18), math.pi * 0.8, math.pi * 1.5, 2)
    pygame.draw.line(surface, color, (x, y + 3), (x, y + 13), 3)
    pygame.draw.line(surface, color, (x - 10, y + 14), (x + 10, y + 14), 3)


def draw_chat_icon(surface, x, y, color):
    bubble = pygame.Rect(x - 14, y - 12, 28, 22)
    pygame.draw.rect(surface, color, bubble, 2, border_radius=5)
    pygame.draw.polygon(surface, color, [(x - 3, y + 10), (x + 2, y + 17), (x + 6, y + 10)])
    for dot_x in (x - 7, x, x + 7):
        pygame.draw.circle(surface, color, (dot_x, y - 1), 2)


def draw_palette_icon(surface, x, y, color):
    pygame.draw.circle(surface, color, (x, y), 14, 2)
    pygame.draw.circle(surface, color, (x - 5, y - 5), 2)
    pygame.draw.circle(surface, color, (x + 3, y - 7), 2)
    pygame.draw.circle(surface, color, (x + 7, y + 1), 2)
    pygame.draw.circle(surface, PANEL2, (x - 1, y + 7), 4)


def draw_crown(surface, x, y):
    pts = [(x - 14, y + 8), (x - 14, y - 3), (x - 8, y + 2), (x - 2, y - 10), (x + 5, y + 2), (x + 13, y - 3), (x + 13, y + 8)]
    pygame.draw.polygon(surface, GOLD, pts)
    pygame.draw.line(surface, shift_color(GOLD, -60), (x - 13, y + 8), (x + 13, y + 8), 2)


def draw_dice_icon(surface, x, y, size=24, color=BLACK):
    r = pygame.Rect(x - size // 2, y - size // 2, size, size)
    pygame.draw.rect(surface, color, r, 2, border_radius=4)
    pip = max(2, size // 9)
    for px, py in ((-5, -5), (0, 0), (5, 5), (5, -5), (-5, 5)):
        pygame.draw.circle(surface, color, (x + px, y + py), pip)


def draw_face_icon(surface, x, y, color, mood="easy"):
    pygame.draw.circle(surface, color, (x, y), 11)
    eye_color = BLACK if mood != "insane" else WHITE
    pygame.draw.circle(surface, eye_color, (x - 4, y - 3), 2)
    pygame.draw.circle(surface, eye_color, (x + 4, y - 3), 2)
    if mood == "easy":
        pygame.draw.arc(surface, eye_color, (x - 6, y - 1, 12, 10), 0.15, math.pi - 0.15, 2)
    elif mood == "medium":
        pygame.draw.line(surface, eye_color, (x - 5, y + 5), (x + 5, y + 5), 2)
    elif mood == "hard":
        pygame.draw.line(surface, eye_color, (x - 6, y - 8), (x - 1, y - 4), 2)
        pygame.draw.line(surface, eye_color, (x + 6, y - 8), (x + 1, y - 4), 2)
        pygame.draw.arc(surface, eye_color, (x - 6, y + 1, 12, 8), math.pi + 0.15, math.pi * 2 - 0.15, 2)
    else:
        pygame.draw.circle(surface, eye_color, (x - 4, y + 5), 2)
        pygame.draw.circle(surface, eye_color, (x + 4, y + 5), 2)


def level_display(level):
    return "Insane" if level == "Impossible" else level


def level_color(level):
    return {
        "Easy": GREEN,
        "Medium": GOLD,
        "Hard": RED,
        "Impossible": PURPLE,
    }.get(level, BLUE)


def ping_color(ping_ms: float):
    if ping_ms < 60:
        return GREEN
    if ping_ms < 120:
        return GOLD
    return RED


def ping_label(ping_ms: float) -> str:
    return f"Ping: {ping_ms:.0f} ms"


def style_button_color(style_name: str):
    return {
        "Normal": GREEN,
        "Angry": RED,
        "Troll": (180, 120, 255),
        "Robot": BLUE,
    }.get(style_name, GREEN)


def format_chat_text(text: str, style_name: str) -> str:
    if style_name == "Troll":
        return "".join(ch.upper() if i % 2 == 0 else ch.lower() for i, ch in enumerate(text))
    if style_name == "Robot":
        return text.upper()
    return text


def chat_text_color(base_color, style_name: str):
    if style_name == "Angry":
        return RED
    if style_name == "Troll":
        return (210, 140, 255)
    if style_name == "Robot":
        return (180, 220, 255)
    return base_color


def theme_tint(theme_name: str):
    return {
        "Inferno": (255, 120, 70),
        "Ice": (120, 220, 255),
        "Galaxy": (185, 120, 255),
        "Cyber": (100, 255, 220),
        "Default": None,
    }.get(theme_name)


def next_option(options: List[str], current: str) -> str:
    if current not in options:
        return options[0]
    return options[(options.index(current) + 1) % len(options)]


def make_tone(freq=440, duration=0.1, volume=0.25):
    if not SOUND_OK:
        return None
    sample_rate = 22050
    n = int(sample_rate * duration)
    buf = array('h')
    amp = int(32767 * volume)
    for i in range(n):
        t = i / sample_rate
        buf.append(int(amp * math.sin(2 * math.pi * freq * t)))
    return pygame.mixer.Sound(buffer=buf.tobytes())


SOUNDS = {
    "eat": make_tone(660, 0.08, 0.18),
    "power": make_tone(900, 0.12, 0.2),
    "damage": make_tone(180, 0.14, 0.25),
    "win": make_tone(520, 0.25, 0.25),
    "count": make_tone(330, 0.08, 0.12),
    "chat": make_tone(520, 0.05, 0.14),
    "whisper": make_tone(420, 0.06, 0.10),
    "mention": make_tone(840, 0.08, 0.18),
}


def play(name: str):
    snd = SOUNDS.get(name)
    if snd:
        try:
            snd.play()
        except Exception:
            pass


def fit_surface_to_rect(surface: pygame.Surface, bounds: pygame.Rect) -> Tuple[pygame.Surface, pygame.Rect, float]:
    src_w, src_h = surface.get_size()
    scale = min(bounds.w / src_w, bounds.h / src_h)
    new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    scaled = pygame.transform.smoothscale(surface, new_size)
    rect = scaled.get_rect(center=bounds.center)
    return scaled, rect, scale


def splash_button_rect(image_rect: pygame.Rect) -> pygame.Rect:
    x, y, w, h = SPLASH_START_BUTTON
    return pygame.Rect(
        image_rect.x + int(image_rect.w * x),
        image_rect.y + int(image_rect.h * y),
        max(1, int(image_rect.w * w)),
        max(1, int(image_rect.h * h)),
    )


def cover_splash_unwanted_buttons(screen: pygame.Surface, image_rect: pygame.Rect):
    """Hide Tutorial/Settings/Leaderboard tabs from the splash art."""
    covers = [
        (0.030, 0.884, 0.120, 0.112),  # tutorial button
        (0.772, 0.884, 0.110, 0.112),  # settings button
        (0.868, 0.884, 0.120, 0.112),  # leaderboard button
    ]
    for rx, ry, rw, rh in covers:
        r = pygame.Rect(
            image_rect.x + int(image_rect.w * rx),
            image_rect.y + int(image_rect.h * ry),
            max(1, int(image_rect.w * rw)),
            max(1, int(image_rect.h * rh)),
        )
        patch = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(patch, (43, 28, 17, 238), patch.get_rect(), border_radius=max(10, r.h // 5))
        pygame.draw.rect(patch, (156, 96, 31, 185), patch.get_rect(), max(2, r.h // 18), border_radius=max(10, r.h // 5))
        screen.blit(patch, r)


def show_splash_screen(screen: pygame.Surface, clock: pygame.time.Clock, image_path: str = SPLASH_IMAGE) -> Tuple[pygame.Surface, bool]:
    """Display the splash art until START GAME is clicked.

    Returns the possibly resized display surface and whether the game should
    continue. Keep SPLASH_START_BUTTON updated if the artwork changes.
    """
    try:
        source_image = pygame.image.load(image_path).convert()
    except pygame.error:
        return screen, True

    font = pygame.font.SysFont("arialrounded" if sys.platform == "darwin" else "arial", 30, bold=True)
    cached_key = None
    scaled_image = source_image
    image_rect = source_image.get_rect()
    start_rect = pygame.Rect(0, 0, 1, 1)
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return screen, False
            if event.type == pygame.VIDEORESIZE:
                new_w = max(560, event.w)
                new_h = max(430, event.h)
                screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
                cached_key = None
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return screen, True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and start_rect.collidepoint(event.pos):
                return screen, True

        window_rect = screen.get_rect()
        if cached_key != window_rect.size:
            cached_key = window_rect.size
            scaled_image, image_rect, _ = fit_surface_to_rect(source_image, window_rect)
            start_rect = splash_button_rect(image_rect)

        mouse_pos = pygame.mouse.get_pos()
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if start_rect.collidepoint(mouse_pos) else pygame.SYSTEM_CURSOR_ARROW)
        screen.fill(BLACK)
        screen.blit(scaled_image, image_rect)
        # Cleaned splash image has unwanted buttons removed; no runtime sticker overlays.
        if start_rect.collidepoint(mouse_pos):
            hover = pygame.Surface(start_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(hover, (255, 255, 255, 34), hover.get_rect(), border_radius=max(8, start_rect.h // 5))
            pygame.draw.rect(hover, (255, 240, 120, 160), hover.get_rect(), 3, border_radius=max(8, start_rect.h // 5))
            screen.blit(hover, start_rect)

        if window_rect.w < 720 or window_rect.h < 480:
            hint = font.render("Press Enter to start", True, WHITE)
            hint_bg = pygame.Rect(0, 0, hint.get_width() + 30, hint.get_height() + 16)
            hint_bg.center = (window_rect.centerx, min(window_rect.bottom - 34, image_rect.bottom - 28))
            draw_alpha_rect(screen, BLACK, hint_bg, 150, radius=8)
            screen.blit(hint, hint.get_rect(center=hint_bg.center))

        pygame.display.flip()
        clock.tick(FPS)

    return screen, True


class InputBox:
    def __init__(self, x, y, w, h, placeholder=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = ""
        self.placeholder = placeholder
        self.active = False

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_TAB):
                return True
            elif len(self.text) < 80:
                self.text += event.unicode
        return False

    def draw(self, surface, font):
        border = CYAN if self.active else (124, 106, 178)
        draw_shadow(surface, self.rect, radius=12, strength=45, offset=(0, 4))
        draw_neon_rect(surface, self.rect, (4, 17, 39), border, radius=10, alpha=242, glow=self.active)
        txt = self.text if self.text else self.placeholder
        color = WHITE if self.text else MUTED
        img = font.render(txt, True, color)
        max_w = self.rect.w - 24
        if img.get_width() > max_w:
            img = font.render(txt[-max(1, max_w // 9):], True, color)
        surface.blit(img, (self.rect.x + 16, self.rect.y + (self.rect.h - img.get_height()) // 2))


class Button:
    def __init__(self, x, y, w, h, label, color=GREEN, text_color=BLACK):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.color = color
        self.text_color = text_color
        self.hover = False

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        return event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos)

    def draw(self, surface, font, active=False):
        border = self.color
        fill = mix_color(self.color, FIELD, 0.28) if (self.hover or active) else (6, 18, 42)
        text = WHITE if (self.hover or active) else mix_color(self.color, WHITE, 0.18)
        draw_neon_rect(surface, self.rect, fill, border, radius=10, alpha=230, glow=self.hover or active)
        draw_center(surface, self.label.upper(), font, text, self.rect.centerx, self.rect.centery)


class ClientApp:
    def __init__(self):
        display_info = pygame.display.Info()
        avail_w = max(560, (display_info.current_w - 80) if display_info.current_w else WINDOW_W)
        avail_h = max(430, (display_info.current_h - 100) if display_info.current_h else WINDOW_H)
        start_w = min(WINDOW_W, avail_w)
        start_h = min(WINDOW_H, avail_h)
        self.screen = pygame.display.set_mode((start_w, start_h), pygame.RESIZABLE)
        pygame.display.set_caption("Python Arena")
        self.clock = pygame.time.Clock()
        self.ui_scale = 1.0
        self.window_w, self.window_h = self.screen.get_size()
        self.safe_margin = 16
        self.gap = 12
        self.header_h = 64
        self.bottom_h = 52
        self.chat_row_h = 61
        self.panel_pad = 16
        self.layout = {}
        self.font_key = None
        self.title_font, self.big_font, self.med_font, self.small_font, self.robot_font = load_fonts()
        self.running = True
        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.username = ""
        self.screen_name = "connect"

        self.ip_box = InputBox(WINDOW_W//2 - 230, 290, 460, 52, "Server IP")
        self.ip_box.text = "127.0.0.1"
        self.port_box = InputBox(WINDOW_W//2 - 230, 356, 460, 52, "Port")
        self.port_box.text = "5000"
        self.user_box = InputBox(WINDOW_W//2 - 230, 422, 460, 52, "Username")
        self.connect_btn = Button(WINDOW_W//2 - 150, CONNECT_LAYOUT["connect_y"], 300, 52, "CONNECT", GREEN)
        self.selected_control = "Arrows"
        self.selected_style = "Emerald"
        self.selected_level = "Easy"
        self.connect_error = ""
        self.connecting = False
        self.connect_menu_rects: List[dict] = []
        self.connect_option_rects: List[dict] = []

        self.online_players: List[dict] = []
        self.scoreboard: List[dict] = []
        self.chat: List[dict] = []
        self.network_events: List[dict] = []
        self.chat_message_rects: List[dict] = []
        self.chat_reaction_rects: List[dict] = []
        self.chat_style_rects: List[dict] = []
        self.cosmetic_rects: List[dict] = []
        self.network_tab_rects: List[dict] = []
        self.lobby_action_rects: List[dict] = []
        self.player_rects: List[dict] = []
        self.difficulty_rects: List[dict] = []
        self.selected_chat_id: Optional[int] = None
        self.selected_chat_style = "Normal"
        self.network_tab = "diag"
        self.quick_chat_open = False
        self.quick_chat_rects: List[dict] = []
        self.selected_eye_style = "Robot"
        self.selected_body_style = "Segmented"
        self.selected_trail_style = "None"
        self.selected_skin_theme = "Ice"
        self.selected_head_style = "Robot"
        self.challenge_pending: Optional[dict] = None
        self.selected_opponent: Optional[str] = None
        self.lobby_note = ""
        self.game_active = False
        self.players_in_game = []
        self.warning_text = ""
        self.warning_until = 0.0
        self.server_messages: List[dict] = []
        self.throttle_counts = {"chat": 0, "move": 0}

        self.game_state: Optional[dict] = None
        self.board_offset = (336, 175)
        self.cell = CELL
        self.particles: List[dict] = []
        self.last_snapshot: Optional[dict] = None
        self.my_ping_ms = 0.0
        self.last_ping_sent = 0.0
        self.last_heartbeat_sent = 0.0
        self.banner = ""
        self.banner_until = 0.0
        self.chat_box = InputBox(26, WINDOW_H - 82, 610, 52, "Type your message...")
        self.send_btn = Button(655, WINDOW_H - 82, 130, 52, "SEND", CYAN, BLACK)
        self.sound_enabled = True
        self.last_countdown_seen = None
        self.result_sent = False
        self.result_buttons: List[dict] = []  # [{\"action\": str, \"rect\": Rect}]
        self.typing_users: List[str] = []
        self.last_typing_sent = 0.0
        self.replay_data: Optional[dict] = None
        self.replay_started_at = 0.0
        self.replay_frame_index = 0
        self.replay_frames: List[dict] = []
        self.info_mode = "tcp"
        self.info_message = ""
        self.info_until = 0.0
        self.info_back_rect = pygame.Rect(0, 0, 0, 0)

        self.stars = [(random.randint(0, WINDOW_W), random.randint(0, WINDOW_H), random.random()*1.6+0.2) for _ in range(230)]
        self.refresh_ui_metrics(force=True)

    def set_banner(self, text, duration=2.5):
        self.banner = text
        self.banner_until = time.time() + duration

    def set_warning(self, text, duration=3.0):
        self.warning_text = text
        self.warning_until = time.time() + duration

    def push_network_event(self, msg: dict):
        item = {
            "kind": msg.get("kind", "event"),
            "text": msg.get("text", ""),
            "username": msg.get("username"),
            "ts": msg.get("ts", time.time()),
        }
        for existing in self.network_events[-20:]:
            if existing.get("kind") == item["kind"] and existing.get("text") == item["text"] and abs(existing.get("ts", 0.0) - item["ts"]) < 0.001:
                return
        self.network_events.append(item)
        self.network_events = self.network_events[-48:]

    def load_last_replay(self) -> bool:
        try:
            with open(REPLAY_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            if not lines:
                return False
            self.replay_data = json.loads(lines[-1])
            self.replay_started_at = time.time()
            self.replay_frame_index = 0
            self.replay_frames = list(self.replay_data.get("frames", []))
            return True
        except Exception:
            self.replay_data = None
            self.replay_frames = []
            return False

    def open_replay_viewer(self):
        if self.load_last_replay():
            self.screen_name = "replay"
            self.set_banner("Viewing last replay")
        else:
            self.set_warning("No replay log found")

    def open_info_screen(self, mode: str):
        self.info_mode = mode
        self.screen_name = "info"
        self.info_message = ""
        self.info_until = 0.0

    def network_stats_snapshot(self) -> dict:
        if not self.sock:
            return {}
        try:
            return get_socket_stats(self.sock)
        except Exception:
            return {}

    def protocol_log_snapshot(self, limit: int = 8) -> List[dict]:
        if not self.sock:
            return []
        try:
            return list(get_protocol_log(self.sock, limit=limit))
        except Exception:
            return []

    def format_throughput(self, value: float) -> str:
        return f"{self.format_bytes(int(value or 0))}/s"

    def format_bytes(self, value: int) -> str:
        value = int(value or 0)
        units = ["B", "KB", "MB", "GB"]
        amt = float(value)
        for unit in units:
            if amt < 1024 or unit == units[-1]:
                return f"{amt:.0f}{unit}" if unit == "B" else f"{amt:.1f}{unit}"
            amt /= 1024.0

    def asset_cover_rect(self, image_path: str) -> pygame.Rect:
        image = load_asset(image_path)
        if image is None:
            return self.screen.get_rect()
        return cover_rect_for_size(image.get_size(), self.screen.get_rect())

    def asset_rect_pct(self, image_path: str, x, y, w, h) -> pygame.Rect:
        return rect_pct(self.asset_cover_rect(image_path), x, y, w, h)

    def clean_template_zone(self, rect: pygame.Rect, alpha: int = 175, radius: Optional[int] = None, inset: int = 0):
        r = pygame.Rect(rect)
        if inset:
            r = r.inflate(-inset * 2, -inset * 2)
        if r.w <= 0 or r.h <= 0:
            return
        alpha = max(0, min(255, alpha))
        if alpha <= 0:
            return
        draw_alpha_rect(self.screen, BLACK, r, alpha, radius=radius if radius is not None else max(8, r.h // 4))

    def draw_template_input(self, box: InputBox, font, show_placeholder: bool = True, clean_alpha: int = 185):
        r = pygame.Rect(box.rect)
        color = CYAN if box.active else (232, 209, 162)
        self.clean_template_zone(r.inflate(-max(12, r.w // 18), -max(6, r.h // 4)), clean_alpha, radius=max(8, r.h // 4))
        draw_glow_outline(self.screen, r, color, radius=max(8, r.h // 4), width=2, alpha=160 if box.active else 90)
        text = box.text if box.text else (box.placeholder if show_placeholder else "")
        if text:
            draw_text_fit(self.screen, text, font, WHITE if box.text else (205, 192, 166), r.inflate(-36, -4), align="left")
        if box.active and int(time.time() * 2) % 2 == 0:
            cursor_x = r.x + 20
            if text:
                cursor_x += min(font.render(text, True, WHITE).get_width(), r.w - 44)
            pygame.draw.line(self.screen, WHITE, (cursor_x, r.y + r.h * 0.28), (cursor_x, r.y + r.h * 0.72), 2)

    def draw_template_button_state(self, rect: pygame.Rect, active=False, color=GOLD):
        if active:
            draw_glow_outline(self.screen, rect, color, radius=max(9, rect.h // 4), width=3, alpha=210)
        elif rect.collidepoint(pygame.mouse.get_pos()):
            draw_glow_outline(self.screen, rect, WHITE, radius=max(9, rect.h // 4), width=2, alpha=110)

    def start_selected_match(self):
        if not self.sock:
            self.set_warning("Connect before starting a match")
            return
        names = [p.get("name") for p in self.online_players]
        target = self.selected_opponent
        if not target or target == self.username:
            target = "BOT" if "BOT" in names else next((name for name in names if name and name != self.username), None)
        if not target:
            self.set_warning("Waiting for another player")
            return
        self.selected_opponent = target
        send_msg(self.sock, {"type": "challenge", "target": target, "level_name": self.selected_level})
        self.set_banner(f"Challenge sent to {target}")

    def load_info_text(self) -> List[str]:
        if self.info_mode == "tcp":
            return [
                "TCP keeps every packet reliable and ordered.",
                "That makes chat, ACKs, and state updates easier to trust.",
                "UDP can be faster, but it can drop packets or reorder them.",
                "For this demo, the game stays on TCP to emphasize correctness.",
            ]
        if self.info_mode == "lan":
            return [
                "Server port: 5000",
                "Same laptop: 127.0.0.1",
                "Same WiFi: use the server's IPv4 address",
                "Different WiFi: port forwarding or a VPN is usually needed",
                "Allow Python through the firewall so peers can connect",
            ]
        return [
            "Diagnostics show socket traffic, live throughput, and ACK counts.",
            "Protocol view shows HELLO, CHAT, MOVE, GAME_STATE, PING/PONG, and ACK.",
            "Event feed is broadcast by the server for connects, disconnects, timeouts, and matches.",
        ]

    def scale_dim(self, value: int, minimum: int = 0) -> int:
        return max(minimum, int(round(value * self.ui_scale)))

    def refresh_ui_metrics(self, force: bool = False):
        self.window_w, self.window_h = self.screen.get_size()
        self.ui_scale = max(0.40, min(self.window_w / WINDOW_W, self.window_h / WINDOW_H))
        font_key = (
            max(20, int(62 * self.ui_scale)),
            max(13, int(30 * self.ui_scale)),
            max(10, int(20 * self.ui_scale)),
            max(9, int(15 * self.ui_scale)),
            max(9, int(16 * self.ui_scale)),
        )
        if force or font_key != self.font_key:
            self.font_key = font_key
            self.title_font, self.big_font, self.med_font, self.small_font, self.robot_font = load_fonts(self.ui_scale)
        self.safe_margin = max(12, int(min(self.window_w, self.window_h) * 0.018))
        self.gap = max(8, int(min(self.window_w, self.window_h) * 0.012))
        self.header_h = max(self.scale_dim(86, 60), int(self.window_h * 0.082))
        self.bottom_h = max(self.scale_dim(58, 48), int(self.window_h * 0.056))
        self.chat_row_h = max(self.scale_dim(61, 48), 48)
        self.panel_pad = max(self.scale_dim(18, 10), 10)
        self.layout = {
            "connect": self.compute_connect_layout(),
            "lobby": self.compute_lobby_layout(),
            "game": self.compute_game_layout(),
        }
        self.apply_input_layout()

    def compute_safe_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.safe_margin,
            self.safe_margin,
            max(1, self.window_w - self.safe_margin * 2),
            max(1, self.window_h - self.safe_margin * 2),
        )

    def compute_connect_layout(self) -> dict:
        safe = self.compute_safe_rect()
        # Keep the title compact so the form and CONNECT button fit on every laptop screen.
        title_h = max(self.scale_dim(92, 62), int(safe.h * 0.105))
        title_w = min(safe.w - self.gap * 2, self.scale_dim(620, 420))
        panel_w = min(max(self.scale_dim(790, 540), int(safe.w * 0.64)), safe.w - self.gap * 2)
        panel_y = safe.y + title_h + self.gap
        panel_h = safe.bottom - panel_y - self.gap
        panel_h = max(self.scale_dim(590, 455), panel_h)
        if panel_h > safe.h - title_h - self.gap:
            panel_h = safe.h - title_h - self.gap
        panel = pygame.Rect(safe.centerx - panel_w // 2, panel_y, panel_w, panel_h)
        if panel.bottom > safe.bottom:
            panel.bottom = safe.bottom
        return {"safe": safe, "title": pygame.Rect(safe.centerx - title_w // 2, safe.y, title_w, title_h), "panel": panel}
    def compute_lobby_layout(self) -> dict:
        """Dashboard lobby inspired by the reference image, but drawn with real UI.
        No full screenshot/photo is used as a background here.
        """
        safe = self.compute_safe_rect()
        top_h = max(self.scale_dim(78, 58), int(safe.h * 0.10))
        bottom_h = max(self.scale_dim(58, 48), int(safe.h * 0.065))
        body_y = safe.y + top_h + self.gap
        body_h = safe.h - top_h - bottom_h - self.gap * 2
        left_w = max(self.scale_dim(250, 185), int(safe.w * 0.25))
        right_w = max(self.scale_dim(310, 230), int(safe.w * 0.34))
        center_w = safe.w - left_w - right_w - self.gap * 2
        if center_w < self.scale_dim(390, 300):
            left_w = max(self.scale_dim(210, 165), int(safe.w * 0.22))
            right_w = max(self.scale_dim(270, 210), int(safe.w * 0.30))
            center_w = safe.w - left_w - right_w - self.gap * 2
        left = pygame.Rect(safe.x, body_y, left_w, body_h)
        center = pygame.Rect(left.right + self.gap, body_y, center_w, body_h)
        right = pygame.Rect(center.right + self.gap, body_y, right_w, body_h)
        left_help_h = max(self.scale_dim(96, 76), int(body_h * 0.22))
        score_h = max(self.scale_dim(210, 160), int(body_h * 0.38))
        mode_h = max(self.scale_dim(76, 58), int(body_h * 0.12))
        custom_y = center.y + score_h + self.gap + mode_h + self.gap
        custom_h = max(self.scale_dim(230, 175), center.bottom - custom_y)
        chat_h = max(self.scale_dim(310, 230), int(body_h * 0.67))
        return {
            "safe": safe,
            "header": pygame.Rect(safe.x, safe.y, safe.w, top_h),
            "left_players": pygame.Rect(left.x, left.y, left.w, max(110, left.h - left_help_h - self.gap)),
            "left_help": pygame.Rect(left.x, left.bottom - left_help_h, left.w, left_help_h),
            "center_score": pygame.Rect(center.x, center.y, center.w, score_h),
            "center_mode": pygame.Rect(center.x, center.y + score_h + self.gap, center.w, mode_h),
            "center_custom": pygame.Rect(center.x, custom_y, center.w, custom_h),
            "right_chat": pygame.Rect(right.x, right.y, right.w, chat_h),
            "right_net": pygame.Rect(right.x, right.y + chat_h + self.gap, right.w, max(90, right.bottom - (right.y + chat_h + self.gap))),
            "bottom": pygame.Rect(safe.x, safe.bottom - bottom_h, safe.w, bottom_h),
            "quick_center": (safe.centerx, safe.centery),
        }
    def compute_game_layout(self) -> dict:
        safe = self.compute_safe_rect()
        top_h = max(self.scale_dim(92, 62), int(safe.h * 0.11))
        bottom_h = max(self.scale_dim(64, 52), int(safe.h * 0.075))
        body_y = safe.y + top_h + self.gap
        body_h = safe.h - top_h - bottom_h - self.gap * 2
        left_w = max(self.scale_dim(250, 190), int(safe.w * 0.21))
        right_w = max(self.scale_dim(310, 230), int(safe.w * 0.24))
        center_w = safe.w - left_w - right_w - self.gap * 2
        if center_w < self.scale_dim(420, 300):
            left_w = max(self.scale_dim(210, 160), int(safe.w * 0.18))
            right_w = max(self.scale_dim(260, 200), int(safe.w * 0.21))
            center_w = safe.w - left_w - right_w - self.gap * 2
        left = pygame.Rect(safe.x, body_y, left_w, body_h)
        center = pygame.Rect(left.right + self.gap, body_y, center_w, body_h)
        right = pygame.Rect(center.right + self.gap, body_y, right_w, body_h)
        bottom = pygame.Rect(center.x, safe.bottom - bottom_h, safe.right - center.x, bottom_h)
        card_h = max(150, (left.h - self.gap * 2 - self.scale_dim(96, 72)) // 2)
        return {
            "safe": safe,
            "header": pygame.Rect(safe.x, safe.y, safe.w, top_h),
            "bottom": bottom,
            "left": left,
            "center": center,
            "right": right,
            "board": pygame.Rect(center.x + self.gap, center.y + self.gap, center.w - self.gap * 2, center.h - self.gap * 2),
            "player_cards": [pygame.Rect(left.x, left.y, left.w, card_h), pygame.Rect(left.x, left.y + card_h + self.gap, left.w, card_h)],
            "level_stats": pygame.Rect(left.x, safe.y, min(left.w, self.scale_dim(210, 150)), min(top_h, self.scale_dim(78, 54))),
            "timer": pygame.Rect(center.centerx - self.scale_dim(72, 50), safe.y + max(4, (top_h - self.scale_dim(48, 34)) // 2), self.scale_dim(144, 100), self.scale_dim(48, 34)),
            "event_log": pygame.Rect(left.x, left.bottom - self.scale_dim(92, 66), left.w, self.scale_dim(92, 66)),
            "spectators": pygame.Rect(right.x, safe.y + max(4, (top_h - self.scale_dim(34, 24)) // 2), right.w, self.scale_dim(34, 24)),
            "net_panel": pygame.Rect(right.x, right.y, right.w, max(self.scale_dim(188, 145), int(right.h * 0.32))),
            "chat_style_buttons": pygame.Rect(right.x, right.y + max(self.scale_dim(188, 145), int(right.h * 0.32)) + self.gap, right.w, self.scale_dim(68, 50)),
            "chat_panel": pygame.Rect(right.x, right.y + max(self.scale_dim(188, 145), int(right.h * 0.32)) + self.gap + self.scale_dim(68, 50) + self.gap, right.w, right.bottom - (right.y + max(self.scale_dim(188, 145), int(right.h * 0.32)) + self.gap + self.scale_dim(68, 50) + self.gap)),
            "chat_input": pygame.Rect(bottom.x, bottom.y, max(120, int(bottom.w * 0.55)), bottom.h),
            "send": pygame.Rect(bottom.x + max(120, int(bottom.w * 0.55)) + self.gap, bottom.y, self.scale_dim(110, 82), bottom.h),
            "ability_bar": pygame.Rect(bottom.x + max(120, int(bottom.w * 0.55)) + self.gap + self.scale_dim(110, 82) + self.gap, bottom.y, max(1, bottom.right - (bottom.x + max(120, int(bottom.w * 0.55)) + self.gap + self.scale_dim(110, 82) + self.gap)), bottom.h),
            "player_name_bottom": pygame.Rect(bottom.x + max(120, int(bottom.w * 0.55)) + self.gap + self.scale_dim(110, 82) + self.gap, bottom.y, max(120, int(bottom.w * 0.18)), bottom.h),
        }
    def apply_input_layout(self):
        connect = self.layout.get("connect", {})
        panel = connect.get("panel", pygame.Rect(0, 0, self.window_w, self.window_h))
        field_w = max(240, panel.w - self.scale_dim(70, 44))
        field_h = max(38, self.scale_dim(52, 38))
        field_x = panel.centerx - field_w // 2
        top = panel.y + self.scale_dim(92, 66)
        gap_y = max(10, self.scale_dim(14, 10))
        self.ip_box.rect = pygame.Rect(field_x, top, field_w, field_h)
        self.port_box.rect = pygame.Rect(field_x, self.ip_box.rect.bottom + gap_y, field_w, field_h)
        self.user_box.rect = pygame.Rect(field_x, self.port_box.rect.bottom + gap_y, field_w, field_h)
        button_w = min(max(180, self.scale_dim(300, 180)), field_w)
        self.connect_btn.rect = pygame.Rect(panel.centerx - button_w // 2, panel.bottom - self.scale_dim(82, 62), button_w, field_h)

        lobby = self.layout.get("lobby", {})
        bottom = lobby.get("bottom", pygame.Rect(self.safe_margin, self.window_h - self.bottom_h - self.safe_margin, self.window_w - self.safe_margin * 2, self.bottom_h))
        send_w = min(max(80, self.scale_dim(130, 80)), max(80, int(bottom.w * 0.16)))
        input_gap = max(10, self.scale_dim(18, 8))
        action_reserve = max(120, int(bottom.w * 0.28))
        input_w = max(120, bottom.w - send_w - input_gap - action_reserve)
        self.chat_box.rect = pygame.Rect(bottom.x, bottom.y, input_w, bottom.h)
        self.send_btn.rect = pygame.Rect(self.chat_box.rect.right + input_gap, bottom.y, send_w, bottom.h)

    def apply_lobby_input_layout(self):
        self.apply_input_layout()

    def connect_option_rect(self, index: int, y: int, count: int, width: int = CONNECT_OPTION_W, height: int = CONNECT_OPTION_H) -> pygame.Rect:
        gap = max(6, self.scale_dim(CONNECT_OPTION_GAP, 6))
        total_width = count * width + (count - 1) * gap
        start_x = (self.window_w - total_width) // 2
        return pygame.Rect(start_x + index * (width + gap), y, width, height)

    def normalize_chat_message(self, msg: dict) -> dict:
        item = dict(msg)
        item.setdefault("reactions", {})
        item.setdefault("style", "Normal")
        item.setdefault("arrived_at", time.time())
        return item

    def upsert_chat_message(self, msg: dict):
        item = self.normalize_chat_message(msg)
        msg_id = item.get("id")
        if msg_id is None:
            self.chat.append(item)
        else:
            for i, current in enumerate(self.chat):
                if current.get("id") == msg_id:
                    self.chat[i] = item
                    break
            else:
                self.chat.append(item)
        self.chat = self.chat[-120:]

    def send_chat_reaction(self, message_id: int, emoji: str):
        if self.sock and message_id is not None:
            send_msg(self.sock, {"type": "chat_reaction", "message_id": message_id, "emoji": emoji})

    def send_quick_chat(self, text: str):
        if self.sock:
            send_msg(self.sock, {"type": "chat", "text": text, "style": self.selected_chat_style})
            self.quick_chat_open = False

    def send_chat_text(self, text: str):
        if self.sock:
            send_msg(self.sock, {"type": "chat", "text": text, "style": self.selected_chat_style})

    def submit_chat_box(self) -> bool:
        text = self.chat_box.text.strip()
        if text:
            self.send_chat_text(text)
            self.chat_box.text = ""
            return True
        return False

    def send_typing_ping(self):
        if self.sock and time.time() - self.last_typing_sent > 0.8:
            self.last_typing_sent = time.time()
            send_msg(self.sock, {"type": "typing"})

    def send_cosmetic_update(self):
        if self.sock:
            send_msg(self.sock, {
                "type": "cosmetic_update",
                "style": self.selected_style,
                "eye_style": self.selected_eye_style,
                "body_style": self.selected_body_style,
                "trail_style": self.selected_trail_style,
                "skin_theme": self.selected_skin_theme,
                "head_style": self.selected_head_style,
            })

    def handle_quick_chat_click(self, pos) -> bool:
        if not self.quick_chat_open:
            return False
        for item in self.quick_chat_rects:
            if item["rect"].collidepoint(pos):
                self.send_quick_chat(item["text"])
                return True
        self.quick_chat_open = False
        return False

    def handle_chat_style_click(self, pos) -> bool:
        for item in self.chat_style_rects:
            if item["rect"].collidepoint(pos):
                self.selected_chat_style = item["style"]
                return True
        return False

    def handle_cosmetic_click(self, pos) -> bool:
        for item in self.cosmetic_rects:
            if item["rect"].collidepoint(pos):
                key = item["key"]
                if key == "surprise":
                    self.selected_style = random.choice(list(STYLE_COLORS))
                    self.selected_eye_style = random.choice(EYE_OPTIONS)
                    self.selected_body_style = random.choice(BODY_OPTIONS)
                    self.selected_trail_style = random.choice(TRAIL_OPTIONS)
                    self.selected_skin_theme = random.choice(THEME_OPTIONS)
                    self.selected_head_style = random.choice(HEAD_OPTIONS)
                elif key == "style":
                    self.selected_style = next_option(list(STYLE_COLORS), self.selected_style)
                elif key == "eyes":
                    self.selected_eye_style = next_option(EYE_OPTIONS, self.selected_eye_style)
                elif key == "body":
                    self.selected_body_style = next_option(BODY_OPTIONS, self.selected_body_style)
                elif key == "trail":
                    self.selected_trail_style = next_option(TRAIL_OPTIONS, self.selected_trail_style)
                elif key == "theme":
                    self.selected_skin_theme = next_option(THEME_OPTIONS, self.selected_skin_theme)
                elif key == "head":
                    self.selected_head_style = next_option(HEAD_OPTIONS, self.selected_head_style)
                self.send_cosmetic_update()
                return True
        return False

    def handle_chat_click(self, pos) -> bool:
        for item in self.chat_reaction_rects:
            if item["rect"].collidepoint(pos):
                self.selected_chat_id = item["message_id"]
                self.send_chat_reaction(item["message_id"], item["emoji"])
                return True
        for item in self.chat_message_rects:
            if item["rect"].collidepoint(pos):
                self.selected_chat_id = None if self.selected_chat_id == item["message_id"] else item["message_id"]
                return True
        self.selected_chat_id = None
        return False

    def format_reactions(self, msg: dict) -> str:
        parts = []
        reactions = msg.get("reactions", {})
        for emoji in CHAT_REACTIONS:
            users = reactions.get(emoji, [])
            if users:
                parts.append(f"{emoji} {len(users)}")
        return "  ".join(parts) if parts else "Click a message to react"

    def draw_chat_style_picker(self, x: int, y: int, width: int, template: bool = False):
        self.chat_style_rects = []
        if not template:
            draw_text(self.screen, "VOICE STYLE", self.small_font, MUTED, x, y)
        gap = max(6, self.scale_dim(12, 6)) if width >= self.scale_dim(340, 240) else 6
        btn_w = max(52, (width - gap * (len(CHAT_STYLE_OPTIONS) - 1)) // len(CHAT_STYLE_OPTIONS))
        total = len(CHAT_STYLE_OPTIONS) * btn_w + (len(CHAT_STYLE_OPTIONS) - 1) * gap
        start_x = x + max(0, (width - total) // 2)
        for i, style_name in enumerate(CHAT_STYLE_OPTIONS):
            rect = pygame.Rect(start_x + i * (btn_w + gap), y + self.scale_dim(28, 20), btn_w, self.scale_dim(34, 26))
            active = style_name == self.selected_chat_style
            color = style_button_color(style_name)
            fill = mix_color(color, FIELD, 0.35) if active else FIELD
            if template:
                self.draw_template_button_state(rect, active=active, color=color)
            else:
                draw_neon_rect(self.screen, rect, fill, color, radius=8, alpha=230, glow=active)
                draw_center(self.screen, style_name.upper(), self.small_font, WHITE if active else color, rect.centerx, rect.centery)
            self.chat_style_rects.append({"style": style_name, "rect": rect})

    def draw_network_monitor_panel(self, x: int, y: int, w: int, h: int, template: bool = False):
        self.network_tab_rects = []
        if w <= 0 or h <= 0:
            return
        if template:
            draw_alpha_rect(self.screen, BLACK, (x, y, w, h), 18, radius=10)
        else:
            draw_neon_rect(self.screen, (x, y, w, h), PANEL2, SOFT_BORDER, radius=10, alpha=220, glow=False)
        tabs = [("diag", "DIAG"), ("proto", "PROTO"), ("feed", "FEED")]
        gap = max(4, self.scale_dim(8, 4))
        tab_w = max(52, (w - gap * (len(tabs) - 1) - self.panel_pad) // len(tabs))
        tab_h = max(22, self.scale_dim(26, 18))
        tab_y = y + max(6, self.scale_dim(8, 6))
        start_x = x + max(6, self.panel_pad // 2)
        for i, (key, label) in enumerate(tabs):
            rect = pygame.Rect(start_x + i * (tab_w + gap), tab_y, tab_w, tab_h)
            active = self.network_tab == key
            fill = mix_color(GREEN if key == "diag" else BLUE if key == "proto" else MAGENTA, FIELD, 0.5) if active else FIELD
            border = GREEN if key == "diag" else BLUE if key == "proto" else MAGENTA
            if template:
                self.draw_template_button_state(rect, active=active, color=border)
            else:
                draw_neon_rect(self.screen, rect, fill, border, radius=8, alpha=230, glow=active)
                draw_center(self.screen, label, self.small_font, WHITE if active else border, rect.centerx, rect.centery)
            self.network_tab_rects.append({"tab": key, "rect": rect})

        body_y = y + tab_h + max(16, self.scale_dim(18, 14))
        body = pygame.Rect(x + self.panel_pad // 2, body_y, w - self.panel_pad, max(1, h - (body_y - y) - self.panel_pad // 2))
        if template:
            self.clean_template_zone(body.inflate(self.scale_dim(8, 5), self.scale_dim(8, 5)), alpha=182, radius=8)
        stats = self.network_stats_snapshot()
        def draw_stat_line(text, color, xx, yy, max_width):
            if template:
                draw_text_shadow(self.screen, fit_text(text, self.small_font, max_width), self.small_font, color, xx, yy)
            else:
                draw_text(self.screen, fit_text(text, self.small_font, max_width), self.small_font, color, xx, yy)

        if not self.connected and not stats:
            draw_stat_line("Disconnected", MUTED, body.x, body.y, body.w)
            draw_stat_line("Socket stats appear after a TCP connection starts.", GRAY, body.x, body.y + self.scale_dim(24, 16), body.w)
            return

        if self.network_tab == "diag":
            ping = self.my_ping_ms
            if self.game_state:
                ping = self.game_state.get("your_ping", ping)
            lines = [
                f"Status: {'Connected' if self.connected else 'Offline'}",
                f"Ping: {ping:.1f} ms",
                f"Tick: {self.game_state.get('tickrate', 10) if self.game_state else 10} Hz",
                f"Msgs: {stats.get('messages_sent', 0)} out / {stats.get('messages_received', 0)} in",
                f"Bytes: {self.format_bytes(stats.get('bytes_sent', 0))} out / {self.format_bytes(stats.get('bytes_received', 0))} in",
                f"Throughput: {self.format_throughput(stats.get('throughput_sent_bps', 0))} out / {self.format_throughput(stats.get('throughput_received_bps', 0))} in",
                f"Msg/s: {stats.get('messages_sent_per_sec', 0):.1f} out / {stats.get('messages_received_per_sec', 0):.1f} in",
                "Protocol: TCP",
                f"ACKs: {stats.get('acks_sent', 0)} out / {stats.get('acks_received', 0)} in",
                f"Packet loss: N/A",
                f"Throttle: chat {getattr(self, 'throttle_counts', {}).get('chat', 0)} | move {getattr(self, 'throttle_counts', {}).get('move', 0)}",
                f"Latest: {self.network_events[-1]['text']}" if self.network_events else "Latest: waiting for server events",
            ]
            for i, line in enumerate(lines):
                color = WHITE if i < 2 else ICE
                y_pos = body.y + i * max(15, self.scale_dim(18, 13) if template else self.scale_dim(20, 14))
                if y_pos > body.bottom - self.small_font.get_height():
                    break
                if template:
                    draw_text_shadow(self.screen, line, self.small_font, color, body.x, y_pos, max_width=body.w)
                else:
                    draw_text(self.screen, fit_text(line, self.small_font, body.w), self.small_font, color, body.x, y_pos)
            return

        if self.network_tab == "proto":
            if template:
                rows = self.protocol_log_snapshot(max(3, body.h // max(16, self.scale_dim(18, 13))))
                if not rows:
                    draw_stat_line("Protocol frames: N/A", MUTED, body.x, body.y, body.w)
                    return
                line_h = max(15, self.scale_dim(18, 13))
                for i, item in enumerate(rows):
                    row_y = body.y + i * line_h
                    if row_y > body.bottom - self.small_font.get_height():
                        break
                    kind = str(item.get("type", "?")).upper()
                    direction = item.get("dir", "?")
                    seq = item.get("seq")
                    stamp = time.strftime("%H:%M:%S", time.localtime(item.get("ts", time.time())))
                    color = GREEN if direction == "OUT" else CYAN
                    draw_stat_line(f"{direction} {kind} #{seq if seq is not None else '-'} {stamp}", color, body.x, row_y, body.w)
                return
            features = [
                "TCP socket transport",
                "4-byte length-prefixed frames",
                "JSON application packets",
                "Sequence IDs + ACK control frames",
                "SHA checksum validation",
                "Duplicate packet detection",
                "Ping/pong heartbeat health",
                "Rate limiting + replay log",
            ]
            line_h = max(15, self.scale_dim(18, 13))
            max_features = max(3, min(len(features), body.h // line_h - 2))
            for i, line in enumerate(features[:max_features]):
                if template:
                    draw_text_shadow(self.screen, line, self.small_font, ICE, body.x, body.y + i * line_h, max_width=body.w)
                else:
                    draw_text(self.screen, fit_text(line, self.small_font, body.w), self.small_font, ICE, body.x, body.y + i * line_h)
            rows = self.protocol_log_snapshot(3)
            log_y = body.y + max_features * line_h + self.scale_dim(8, 5)
            if rows and log_y < body.bottom - line_h:
                draw_stat_line("RECENT FRAMES", GOLD, body.x, log_y, body.w)
                log_y += line_h
            for i, item in enumerate(rows[: max(0, (body.bottom - log_y) // line_h)]):
                kind = str(item.get("type", "?")).upper()
                direction = item.get("dir", "?")
                seq = item.get("seq")
                ts = time.strftime("%H:%M:%S", time.localtime(item.get("ts", time.time())))
                label = fit_text(f"{direction}  {kind}  #{seq if seq is not None else '-'}  {ts}", self.small_font, body.w)
                color = GREEN if direction == "OUT" else CYAN
                if kind in ("ACK",):
                    color = GOLD
                elif kind in ("GAME_STATE",):
                    color = BLUE
                elif kind in ("PING", "PONG"):
                    color = MAGENTA
                draw_stat_line(label, color, body.x, log_y + i * line_h, body.w)
            return

        rows = self.network_events[-5:]
        if not rows:
            draw_stat_line("Waiting for server events...", MUTED, body.x, body.y, body.w)
            return
        for i, item in enumerate(rows):
            kind = str(item.get("kind", "event")).upper()
            text = fit_text(item.get("text", ""), self.small_font, body.w - self.scale_dim(14, 8))
            color = {
                "CONNECT": GREEN,
                "DISCONNECT": RED,
                "TIMEOUT": RED,
                "RECONNECT": CYAN,
                "CHALLENGE": GOLD,
                "MATCH_STARTED": BLUE,
                "MATCH_ENDED": MAGENTA,
                "BROADCAST": ICE,
            }.get(kind, WHITE)
            stamp = time.strftime("%H:%M:%S", time.localtime(item.get("ts", time.time())))
            row_y = body.y + i * max(16, self.scale_dim(20, 14))
            draw_stat_line(f"{stamp} {kind.lower()}", color, body.x, row_y, body.w)
            draw_stat_line(text, GRAY, body.x + self.scale_dim(118, 86), row_y, body.w - self.scale_dim(118, 86))

    def draw_avatar(self, x: int, y: int, msg: dict):
        sender = msg.get("sender")
        style = self.selected_style if sender == self.username else None
        head_style = self.selected_head_style if sender == self.username else "Classic"
        theme = self.selected_skin_theme if sender == self.username else "Default"
        for p in self.online_players:
            if p.get("name") == sender:
                style = p.get("style", style or "Emerald")
                head_style = p.get("head_style", head_style)
                theme = p.get("skin_theme", theme)
                break
        head_color, _ = STYLE_COLORS.get(style or "Emerald", STYLE_COLORS["Emerald"])
        tint = theme_tint(theme)
        if tint:
            head_color = tuple(min(255, (head_color[i] + tint[i]) // 2) for i in range(3))
        radius = self.scale_dim(10, 8)
        pygame.draw.circle(self.screen, head_color, (x, y), radius)
        pygame.draw.circle(self.screen, WHITE, (x, y), radius, 1)
        icon = {"Dragon": "D", "Skull": "S", "Cat": "C", "Pixel": "P", "Robot": "R"}.get(head_style, "")
        if icon:
            draw_center(self.screen, icon, self.small_font, BLACK, x, y)

    def draw_cosmetic_panel(self, x: int, y: int, w: int, h: int):
        self.cosmetic_rects = []
        draw_panel(self.screen, (x, y, w, h), "Customize Your Character", self.med_font, icon="palette", header_h=max(42, self.scale_dim(58, 42)))

        def selector_row(key, label, value, yy, icon_color):
            row = pygame.Rect(x + self.panel_pad, yy, w - self.panel_pad * 2, self.scale_dim(42, 32))
            draw_neon_rect(self.screen, row, FIELD, SOFT_BORDER, radius=10, alpha=214, glow=False)
            icon_size = self.scale_dim(18, 14)
            pygame.draw.rect(self.screen, icon_color, (row.x + self.scale_dim(14, 10), row.y + (row.h - icon_size) // 2, icon_size, icon_size), border_radius=5)
            draw_text(self.screen, label.upper(), self.small_font, ICE, row.x + self.scale_dim(52, 38), row.y + max(7, self.scale_dim(12, 7)))
            split = min(self.scale_dim(178, 116), int(row.w * 0.46))
            value_rect = pygame.Rect(row.x + split, row.y + 4, row.w - split - 12, row.h - 8)
            draw_neon_rect(self.screen, value_rect, (8, 18, 43), SOFT_BORDER, radius=9, alpha=230, glow=False)
            draw_text(self.screen, value.upper(), self.small_font, WHITE, value_rect.x + self.scale_dim(12, 8), value_rect.y + max(5, self.scale_dim(9, 5)))
            pygame.draw.line(
                self.screen,
                SOFT_BORDER,
                (value_rect.right - self.scale_dim(26, 18), value_rect.centery - self.scale_dim(4, 3)),
                (value_rect.right - self.scale_dim(18, 12), value_rect.centery + self.scale_dim(4, 3)),
                2,
            )
            pygame.draw.line(
                self.screen,
                SOFT_BORDER,
                (value_rect.right - self.scale_dim(10, 8), value_rect.centery - self.scale_dim(4, 3)),
                (value_rect.right - self.scale_dim(18, 12), value_rect.centery + self.scale_dim(4, 3)),
                2,
            )
            self.cosmetic_rects.append({"key": key, "rect": row})

        yy = y + max(54, self.scale_dim(66, 54))
        selector_row("style", "Color", self.selected_style, yy, GREEN)
        yy += self.scale_dim(52, 40)
        selector_row("eyes", "Eyes", self.selected_eye_style, yy, ICE)
        yy += self.scale_dim(52, 40)
        selector_row("body", "Body", self.selected_body_style, yy, CYAN)
        yy += self.scale_dim(58, 44)

        surprise = pygame.Rect(x + self.panel_pad, yy, w - self.panel_pad * 2, self.scale_dim(50, 38))
        draw_neon_rect(self.screen, surprise, GOLD, GOLD, radius=10, alpha=245, glow=True)
        draw_center(self.screen, "SURPRISE ME", self.med_font, BLACK, surprise.centerx + self.scale_dim(18, 12), surprise.centery)
        draw_dice_icon(self.screen, surprise.x + min(self.scale_dim(152, 108), surprise.w // 3), surprise.centery, self.scale_dim(24, 18), BLACK)
        self.cosmetic_rects.append({"key": "surprise", "rect": surprise})
        yy += self.scale_dim(66, 50)

        selector_row("theme", "Theme", self.selected_skin_theme, yy, ICE)
        yy += self.scale_dim(58, 44)

        preview = pygame.Rect(x + self.panel_pad, yy, w - self.panel_pad * 2, max(self.scale_dim(62, 48), y + h - yy - self.panel_pad))
        draw_neon_rect(self.screen, preview, FIELD, SOFT_BORDER, radius=9, alpha=218, glow=False)
        draw_text(self.screen, "HEAD PREVIEW", self.small_font, ICE, preview.x + self.scale_dim(14, 10), preview.y + self.scale_dim(21, 15))
        colors = [GREEN, CYAN, mix_color(GREEN, CYAN, 0.5), CYAN]
        head_size = self.scale_dim(28, 20)
        head_gap = self.scale_dim(42, 28)
        head_start = preview.x + min(self.scale_dim(165, 112), max(self.scale_dim(120, 88), preview.w - head_gap * len(colors) - self.scale_dim(28, 20)))
        for i, color in enumerate(colors):
            hx = head_start + i * head_gap
            head = pygame.Rect(hx, preview.y + self.scale_dim(18, 12), head_size, head_size)
            pygame.draw.rect(self.screen, color, head, border_radius=7)
            pygame.draw.circle(self.screen, BLACK, (head.x + self.scale_dim(9, 6), head.y + self.scale_dim(11, 8)), 2)
            pygame.draw.circle(self.screen, BLACK, (head.right - self.scale_dim(9, 6), head.y + self.scale_dim(11, 8)), 2)
            pygame.draw.line(self.screen, BLACK, (head.x + self.scale_dim(8, 6), head.y + self.scale_dim(20, 14)), (head.right - self.scale_dim(8, 6), head.y + self.scale_dim(20, 14)), 2)
            pygame.draw.line(self.screen, color, (head.centerx, head.y - self.scale_dim(2, 1)), (head.centerx, head.y - self.scale_dim(9, 6)), 2)
        self.cosmetic_rects.append({"key": "head", "rect": preview})

    def draw_snake_preview(self, x: int, y: int, w: int, h: int):
        draw_alpha_rect(self.screen, PANEL, (x, y, w, h), 170)
        draw_center(self.screen, "Preview", self.small_font, WHITE, x + w // 2, y + 16)
        segments = [(x + 52 + i * 24, y + h // 2 + int(math.sin(time.time() * 3 + i * 0.5) * 4)) for i in range(5)]
        cosmetics = {
            "eye_style": self.selected_eye_style,
            "body_style": self.selected_body_style,
            "trail_style": self.selected_trail_style,
            "skin_theme": self.selected_skin_theme,
            "head_style": self.selected_head_style,
        }
        self.draw_trail_effect(segments, cosmetics)
        self.draw_snake_segments(segments, self.selected_style, cosmetics, preview=True)

    def draw_trail_effect(self, segments, cosmetics):
        trail = cosmetics.get("trail_style", "None")
        if trail == "None":
            return
        for i, (x, y) in enumerate(segments[1:]):
            if trail == "Sparkle":
                pygame.draw.circle(self.screen, GOLD, (x - 12, y), max(1, 4 - i))
            elif trail == "Smoke":
                pygame.draw.circle(self.screen, GRAY, (x - 10, y), max(2, 6 - i))
            elif trail == "Neon":
                glow = pygame.Surface((26, 26), pygame.SRCALPHA)
                pygame.draw.circle(glow, (80, 255, 220, 55), (13, 13), 11 - i)
                self.screen.blit(glow, (x - 13, y - 13))
            elif trail == "Rainbow":
                cols = [RED, GOLD, GREEN, BLUE, (185, 120, 255)]
                pygame.draw.circle(self.screen, cols[i % len(cols)], (x - 10, y), max(2, 5 - i))

    def draw_snake_segments(self, segments, style_name: str, cosmetics: dict, preview: bool = False):
        head_color, body_color = STYLE_COLORS.get(style_name, STYLE_COLORS["Emerald"])
        tint = theme_tint(cosmetics.get("skin_theme", "Default"))
        if tint:
            head_color = tuple(min(255, (head_color[i] + tint[i]) // 2) for i in range(3))
            body_color = tuple(min(255, (body_color[i] + tint[i]) // 2) for i in range(3))
        body_style = cosmetics.get("body_style", "Rounded")
        for i, (sx, sy) in enumerate(segments):
            col = head_color if i == 0 else body_color
            if not preview and body_style != "Rainbow":
                pass
            if preview:
                rect = pygame.Rect(sx - 9, sy - 9, 18, 18)
            else:
                rect = pygame.Rect(sx, sy, self.cell - 4, self.cell - 4)
            if body_style == "Square":
                pygame.draw.rect(self.screen, col, rect)
            elif body_style == "Spiky":
                pts = [(rect.centerx, rect.y), (rect.right, rect.centery), (rect.centerx, rect.bottom), (rect.x, rect.centery)]
                pygame.draw.polygon(self.screen, col, pts)
            elif body_style == "Segmented":
                pygame.draw.rect(self.screen, col, rect, border_radius=2)
                pygame.draw.line(self.screen, BLACK, (rect.x + 3, rect.centery), (rect.right - 3, rect.centery), 1)
            else:
                pygame.draw.rect(self.screen, col, rect, border_radius=5)
            if i == 0:
                self.draw_head_details(rect, cosmetics, col)

    def draw_head_details(self, rect: pygame.Rect, cosmetics: dict, color):
        eye_style = cosmetics.get("eye_style", "Normal")
        head_style = cosmetics.get("head_style", "Classic")
        if head_style == "Dragon":
            pygame.draw.polygon(self.screen, GOLD, [(rect.x + 2, rect.y + 4), (rect.x + 6, rect.y + 1), (rect.x + 8, rect.y + 6)])
        elif head_style == "Skull":
            pygame.draw.circle(self.screen, WHITE, (rect.centerx, rect.centery + 1), max(3, rect.w // 4), 1)
        elif head_style == "Cat":
            pygame.draw.polygon(self.screen, WHITE, [(rect.x + 3, rect.y + 4), (rect.x + 6, rect.y), (rect.x + 8, rect.y + 5)])
            pygame.draw.polygon(self.screen, WHITE, [(rect.right - 3, rect.y + 4), (rect.right - 6, rect.y), (rect.right - 8, rect.y + 5)])
        elif head_style == "Pixel":
            pygame.draw.rect(self.screen, BLACK, (rect.x + 3, rect.y + 3, 3, 3))
            pygame.draw.rect(self.screen, BLACK, (rect.right - 6, rect.y + 3, 3, 3))
        elif head_style == "Robot":
            pygame.draw.rect(self.screen, GRAY, rect, 1)
        left_eye = (rect.x + 6, rect.y + 7)
        right_eye = (rect.right - 6, rect.y + 7)
        if eye_style == "Sunglasses":
            pygame.draw.line(self.screen, BLACK, (rect.x + 4, rect.y + 7), (rect.right - 4, rect.y + 7), 3)
        elif eye_style == "Glowing":
            pygame.draw.circle(self.screen, GOLD, left_eye, 3)
            pygame.draw.circle(self.screen, GOLD, right_eye, 3)
        elif eye_style == "Robot":
            pygame.draw.rect(self.screen, BLUE, (rect.x + 4, rect.y + 5, rect.w - 8, 4))
        else:
            pygame.draw.circle(self.screen, BLACK, left_eye, 2)
            pygame.draw.circle(self.screen, BLACK, right_eye, 2)

    def draw_chat_list(self, x: int, y: int, width: int, height: int, visible_count: int):
        """Draw chat without overlapping the sender and message text."""
        self.chat_message_rects = []
        self.chat_reaction_rects = []
        row_h = self.chat_row_h
        bottom = y + height
        visible = self.chat[-visible_count:]
        start_y = max(y, bottom - len(visible) * row_h)
        for i, msg in enumerate(visible):
            top = start_y + i * row_h
            age = min(1.0, time.time() - msg.get("arrived_at", time.time()))
            slide = int((1.0 - min(1.0, age * 5)) * max(8, self.scale_dim(16, 8)))
            bubble = pygame.Rect(x + slide, top, width - slide, row_h - 8)
            active = msg.get("id") is not None and msg.get("id") == self.selected_chat_id
            border = GREEN if active else SOFT_BORDER
            fill = (19, 33, 64) if active else (14, 27, 58)
            draw_neon_rect(self.screen, bubble, fill, border, radius=9, alpha=220, glow=active)

            avatar_x = bubble.x + max(18, self.scale_dim(22, 18))
            self.draw_avatar(avatar_x, bubble.y + row_h // 3, msg)
            sender = str(msg.get("sender", "?")).upper()
            style_name = msg.get("style", "Normal")
            raw_text = str(msg.get("text", ""))
            text = format_chat_text(raw_text, style_name)
            base_color = GOLD if msg.get("private_to") else (GREEN if msg.get("sender") == self.username else (BLUE if sender == "BOT" else ICE))
            color = chat_text_color(base_color, style_name)
            font = self.robot_font if style_name == "Robot" else self.small_font

            left = bubble.x + max(42, self.scale_dim(48, 42))
            top_text = bubble.y + max(6, self.scale_dim(8, 6))
            max_line_w = max(40, bubble.right - left - self.scale_dim(12, 8))
            sender_label = fit_text(sender, self.small_font, max(46, min(self.scale_dim(128, 82), max_line_w // 2)))
            sender_surf = self.small_font.render(sender_label + ":", True, color)
            self.screen.blit(sender_surf, (left, top_text))
            msg_x = left + sender_surf.get_width() + self.scale_dim(8, 5)
            msg_w = max(20, bubble.right - msg_x - self.scale_dim(12, 8))
            message_label = fit_text(text.upper(), font, msg_w)
            if style_name != "Normal":
                glow = font.render(message_label, True, color)
                glow.set_alpha(90)
                self.screen.blit(glow, (msg_x + 1, top_text + 1))
            self.screen.blit(font.render(message_label, True, color), (msg_x, top_text))

            summary = self.format_reactions(msg)
            sub_rect = pygame.Rect(left, bubble.y + self.scale_dim(31, 24), max_line_w, max(14, row_h//3))
            draw_text_fit(self.screen, summary[:44] if summary else "Click a message to react", self.small_font, BLUE if msg.get("reactions") else MUTED, sub_rect)
            self.chat_message_rects.append({"message_id": msg.get("id"), "rect": bubble})

            if active and msg.get("id") is not None:
                for idx, emoji in enumerate(CHAT_REACTIONS):
                    btn = pygame.Rect(bubble.right - self.scale_dim(128, 100) + idx * self.scale_dim(30, 24), bubble.y + self.scale_dim(28, 20), self.scale_dim(25, 20), self.scale_dim(20, 16))
                    users = msg.get("reactions", {}).get(emoji, [])
                    pygame.draw.rect(self.screen, (30, 45, 85), btn, border_radius=6)
                    pygame.draw.rect(self.screen, GOLD if users else SOFT_BORDER, btn, 1, border_radius=6)
                    draw_center(self.screen, emoji, self.small_font, WHITE, btn.centerx, btn.centery)
                    self.chat_reaction_rects.append({"message_id": msg.get("id"), "emoji": emoji, "rect": btn})

    def draw_template_chat_list(self, rect: pygame.Rect, visible_count: int):
        self.chat_message_rects = []
        self.chat_reaction_rects = []
        rect = pygame.Rect(rect)
        if rect.w <= 0 or rect.h <= 0:
            return
        visible = self.chat[-visible_count:]
        if not visible:
            return
        line_h = max(16, min(self.scale_dim(25, 17), rect.h // max(1, visible_count)))
        start_y = max(rect.y, rect.bottom - len(visible) * line_h)
        for i, msg in enumerate(visible):
            row = pygame.Rect(rect.x, start_y + i * line_h, rect.w, line_h)
            sender = str(msg.get("sender", "?")).upper()
            style_name = msg.get("style", "Normal")
            text = format_chat_text(str(msg.get("text", "")), style_name)
            base_color = GOLD if msg.get("private_to") else (GREEN if msg.get("sender") == self.username else (BLUE if sender == "BOT" else ICE))
            color = chat_text_color(base_color, style_name)
            stamp = time.strftime("%H:%M:%S", time.localtime(msg.get("ts", time.time())))
            label = fit_text(f"{sender[:8]}  >  {text}", self.small_font, max(20, row.w - self.scale_dim(72, 48)))
            draw_text_shadow(self.screen, label, self.small_font, color, row.x + self.scale_dim(8, 5), row.y + max(1, (row.h - self.small_font.get_height()) // 2), max_width=row.w - self.scale_dim(72, 48))
            draw_text_shadow(self.screen, stamp, self.small_font, MUTED, row.right - self.scale_dim(66, 46), row.y + max(1, (row.h - self.small_font.get_height()) // 2), max_width=self.scale_dim(62, 42))
            self.chat_message_rects.append({"message_id": msg.get("id"), "rect": row})

    def draw_quick_chat_wheel(self, center_x: int, center_y: int):
        if not self.quick_chat_open:
            self.quick_chat_rects = []
            return
        self.quick_chat_rects = []
        wheel_w = self.scale_dim(300, 220)
        wheel_h = self.scale_dim(260, 200)
        center_x = max(self.safe_margin + wheel_w // 2, min(self.window_w - self.safe_margin - wheel_w // 2, center_x))
        center_y = max(self.safe_margin + wheel_h // 2, min(self.window_h - self.safe_margin - wheel_h // 2, center_y))
        draw_alpha_rect(self.screen, PANEL2, (center_x - wheel_w // 2, center_y - wheel_h // 2, wheel_w, wheel_h), 230, radius=max(12, self.scale_dim(18, 12)))
        draw_center(self.screen, "Quick Chat", self.med_font, WHITE, center_x, center_y - self.scale_dim(96, 72))
        draw_center(self.screen, "Press Q to close", self.small_font, GRAY, center_x, center_y - self.scale_dim(72, 54))

        positions = [
            (center_x, center_y - self.scale_dim(26, 22)),
            (center_x + self.scale_dim(88, 70), center_y + self.scale_dim(34, 28)),
            (center_x, center_y + self.scale_dim(94, 74)),
            (center_x - self.scale_dim(88, 70), center_y + self.scale_dim(34, 28)),
        ]
        colors = [GREEN, BLUE, RED, GOLD]
        for i, text in enumerate(QUICK_CHAT_OPTIONS):
            rect = pygame.Rect(0, 0, self.scale_dim(108, 88), self.scale_dim(42, 34))
            rect.center = positions[i]
            pygame.draw.rect(self.screen, tuple(max(0, c - 25) for c in colors[i]), rect, border_radius=14)
            pygame.draw.rect(self.screen, colors[i], rect, 2, border_radius=14)
            draw_center(self.screen, text, self.small_font, WHITE, rect.centerx, rect.centery)
            self.quick_chat_rects.append({"text": text, "rect": rect})

        inner_y = center_y + self.scale_dim(34, 28)
        pygame.draw.circle(self.screen, PANEL, (center_x, inner_y), self.scale_dim(26, 20))
        pygame.draw.circle(self.screen, GRAY, (center_x, inner_y), 2, self.scale_dim(26, 20))
        draw_center(self.screen, "Q", self.med_font, WHITE, center_x, inner_y)

    def run(self):
        # Show the title poster first; clicking START GAME continues to the real setup.
        self.screen, keep_running = show_splash_screen(self.screen, self.clock, SPLASH_IMAGE)
        self.running = self.running and keep_running
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        self.screen_name = "connect"
        self.refresh_ui_metrics(force=True)
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.refresh_ui_metrics()
            if self.connected and time.time() - self.last_ping_sent > 1.0:
                self.last_ping_sent = time.time()
                send_msg(self.sock, {"type": "ping", "client_ts": self.last_ping_sent})
            if self.connected and time.time() - self.last_heartbeat_sent > 2.5:
                self.last_heartbeat_sent = time.time()
                send_msg(self.sock, {"type": "heartbeat"})
            self.update_particles(dt)
            self.draw()
            pygame.display.flip()
        self.send_disconnect()
        pygame.quit()

    def send_disconnect(self):
        if self.sock and self.connected:
            try:
                send_msg(self.sock, {"type": "disconnect"})
            except Exception:
                pass
            self.connected = False

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.send_disconnect()
                self.running = False
                return
            if event.type == pygame.VIDEORESIZE:
                new_w = max(560, event.w)
                new_h = max(430, event.h)
                self.screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
                self.refresh_ui_metrics(force=True)
                continue
            if self.screen_name == "connect":
                self.handle_connect(event)
            elif self.screen_name == "info":
                self.handle_info(event)
            elif self.screen_name == "replay":
                self.handle_replay(event)
            elif self.screen_name == "lobby":
                self.handle_lobby(event)
            elif self.screen_name == "game":
                self.handle_game(event)
            elif self.screen_name == "result":
                self.handle_result(event)

    def connect(self):
        if self.connecting:
            return
        ip = self.ip_box.text.strip() or "127.0.0.1"
        try:
            port = int(self.port_box.text.strip() or "5000")
        except ValueError:
            self.connect_error = "Port must be a number"
            return
        username = self.user_box.text.strip()
        if not username:
            self.connect_error = "Please enter a username"
            return
        self.connecting = True
        self.connect_error = "Connecting..."
        threading.Thread(target=self._connect_worker, args=(ip, port, username), daemon=True).start()

    def _connect_worker(self, ip: str, port: int, username: str):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(2.5)
            sock.connect((ip, port))
            self.sock = sock
            send_msg(sock, {
                "type": "hello",
                "username": username,
                "controls": self.selected_control,
                "style": self.selected_style,
                "level_pref": self.selected_level,
                "eye_style": self.selected_eye_style,
                "body_style": self.selected_body_style,
                "trail_style": self.selected_trail_style,
                "skin_theme": self.selected_skin_theme,
                "head_style": self.selected_head_style,
            })
            reply = recv_msg(sock)
            if not reply or reply.get("type") != "hello_ok":
                self.connect_error = reply.get("msg", "Connection failed") if reply else "No server response"
                try:
                    sock.close()
                except Exception:
                    pass
                self.sock = None
                return
            sock.settimeout(None)
            self.username = username
            self.connected = True
            self.connect_error = ""
            self.screen_name = "lobby"
            threading.Thread(target=self.recv_loop, daemon=True).start()
        except Exception as e:
            self.connect_error = f"Connection failed: {e}"
            try:
                if self.sock:
                    self.sock.close()
            except Exception:
                pass
            self.sock = None
        finally:
            self.connecting = False

    def recv_loop(self):
        while self.running and self.sock:
            msg = recv_msg(self.sock)
            if not msg:
                self.set_banner("Disconnected from server", 4)
                self.connected = False
                self.screen_name = "connect"
                if self.username:
                    self.user_box.text = self.username
                self.sock = None
                return
            self.handle_server(msg)

    def handle_server(self, msg: dict):
        t = msg.get("type")
        if t == "lobby":
            self.online_players = msg.get("online", [])
            self.scoreboard = msg.get("scoreboard", [])
            self.players_in_game = msg.get("players_in_game", [])
            self.game_active = msg.get("game_active", False)
            self.chat = [self.normalize_chat_message(item) for item in msg.get("chat_history", self.chat)]
            self.typing_users = msg.get("typing", [])
            for item in msg.get("network_events", []):
                self.push_network_event(item)
            names = [p.get("name") for p in self.online_players]
            if self.selected_opponent not in names:
                self.selected_opponent = "BOT" if "BOT" in names else None
            # Stay on result screen — don't auto-jump back to lobby.
            # The player must press "Back to Lobby" explicitly.
            if self.screen_name not in ("result", "game"):
                self.screen_name = "lobby"
        elif t == "match_result":
            # Authoritative end-of-match packet sent by server after _finish_game().
            # Merge winner/stats into game_state and switch to result screen.
            if self.game_state is None:
                self.game_state = {}
            self.game_state["finished"] = True
            self.game_state["winner"] = msg.get("winner", self.game_state.get("winner", "?"))
            self.game_state["p1"] = msg.get("p1", self.game_state.get("p1", ""))
            self.game_state["p2"] = msg.get("p2", self.game_state.get("p2", ""))
            self.game_state["stats"] = msg.get("stats", self.game_state.get("stats", {}))
            self.game_state["health"] = msg.get("health", self.game_state.get("health", {}))
            self.game_state["level_name"] = msg.get("level_name", self.game_state.get("level_name", ""))
            # Refresh scoreboard from the result packet (freshly persisted by server).
            if msg.get("scoreboard"):
                self.scoreboard = msg["scoreboard"]
            if not self.result_sent:
                self.result_sent = True
                self.screen_name = "result"
                play("win")
        elif t == "network_event":
            self.push_network_event(msg)
            if msg.get("kind") in ("reconnect", "match_started", "match_ended"):
                self.set_banner(msg.get("text", ""), 2.0)
        elif t == "warning":
            kind = str(msg.get("kind", "")).lower()
            if "chat" in kind:
                self.throttle_counts["chat"] += 1
            if "move" in kind:
                self.throttle_counts["move"] += 1
            self.set_warning(msg.get("msg", "Warning"))
            self.set_banner(msg.get("msg", "Warning"), 2.0)
        elif t == "challenge_request":
            self.challenge_pending = msg
            self.set_banner(f"Challenge from {msg.get('from')}")
        elif t == "challenge_declined":
            self.set_banner(f"{msg.get('opponent')} declined your challenge")
        elif t in ("game_start", "game_started"):
            self.screen_name = "game"
            self.game_state = None
            self.last_snapshot = None
            self.result_sent = False
            self.last_countdown_seen = None
            self.set_banner(f"Level: {msg.get('level_name', self.selected_level)}")
        elif t == "game_state":
            # Only accept game_state updates when we are in the game screen.
            # Once we're on the result screen don't overwrite the final state.
            if self.screen_name == "game":
                self.process_game_state(msg)
        elif t == "chat":
            self.upsert_chat_message(msg)
            if msg.get("sender") != self.username:
                play("whisper" if msg.get("private_to") else "chat")
                if f"@{self.username}".lower() in msg.get("text", "").lower():
                    play("mention")
        elif t == "chat_reaction":
            if msg.get("message"):
                self.upsert_chat_message(msg["message"])
        elif t == "cheer":
            self.set_banner(f"{msg.get('from')} cheers for {msg.get('target')}!", 2)
        elif t == "rematch_request":
            self.challenge_pending = {"from": msg.get("from"), "rematch": True}
            self.set_banner(f"Rematch request from {msg.get('from')}")
        elif t == "rematch_declined":
            self.set_banner("Rematch declined")
        elif t == "watch_ok":
            self.screen_name = "game"
            self.set_banner("Watching current match")
        elif t == "pong":
            sent = float(msg.get("client_ts", time.time()))
            self.my_ping_ms = max(0.0, (time.time() - sent) * 1000.0)
            if self.sock:
                send_msg(self.sock, {"type": "ping_sample", "ping_ms": self.my_ping_ms})
        elif t == "banner":
            self.set_banner(msg.get("text", ""))
        elif t == "error":
            self.set_banner(msg.get("msg", "Error"), 4)
            self.connect_error = msg.get("msg", "Error")

    def process_game_state(self, msg: dict):
        prev = self.game_state
        self.game_state = msg
        self.typing_users = msg.get("typing", self.typing_users)
        if prev:
            prev_pies = {(p['x'], p['y']) for p in prev.get('pies', [])}
            now_pies = {(p['x'], p['y']) for p in msg.get('pies', [])}
            for pos in prev_pies - now_pies:
                self.spawn_particles(pos, GOLD)
                play("eat")
            prev_pow = {(p['x'], p['y']) for p in prev.get('powerups', [])}
            now_pow = {(p['x'], p['y']) for p in msg.get('powerups', [])}
            for pos in prev_pow - now_pow:
                self.spawn_particles(pos, BLUE)
                play("power")
            for name in msg.get('health', {}):
                if msg['health'][name] < prev.get('health', {}).get(name, msg['health'][name]):
                    play("damage")
        cd = math.ceil(msg.get("countdown", 0)) if not msg.get("started") else None
        if cd is not None and cd != self.last_countdown_seen and cd > 0:
            self.last_countdown_seen = cd
            play("count")
        if msg.get("finished") and not self.result_sent:
            # Fallback: if match_result packet was missed, the finished game_state
            # will still transition us to the result screen.
            self.result_sent = True
            self.screen_name = "result"
            play("win")

    def spawn_particles(self, cell_pos, color):
        x = self.board_offset[0] + cell_pos[0] * self.cell + self.cell // 2
        y = self.board_offset[1] + cell_pos[1] * self.cell + self.cell // 2
        for _ in range(14):
            ang = random.random() * math.pi * 2
            speed = random.random() * 90 + 30
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(ang) * speed,
                "vy": math.sin(ang) * speed,
                "life": 0.6,
                "color": color,
            })

    def update_particles(self, dt):
        for p in self.particles:
            p["life"] -= dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 20 * dt
        self.particles = [p for p in self.particles if p["life"] > 0]

    def handle_connect(self, event):
        self.ip_box.handle(event)
        self.port_box.handle(event)
        self.user_box.handle(event)
        for item in self.connect_menu_rects:
            if event.type == pygame.MOUSEBUTTONDOWN and item["rect"].collidepoint(event.pos):
                mode = item["mode"]
                if mode == "replay":
                    self.open_replay_viewer()
                else:
                    self.open_info_screen(mode)
                return
        if self.connect_btn.handle(event) or (event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN):
            self.connect()
        if event.type == pygame.MOUSEBUTTONDOWN:
            for item in self.connect_option_rects:
                if item["rect"].collidepoint(event.pos):
                    if item["kind"] == "control":
                        self.selected_control = item["value"]
                    elif item["kind"] == "style":
                        self.selected_style = item["value"]
                    elif item["kind"] == "level":
                        self.selected_level = item["value"]
                    return

    def handle_info(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.screen_name = "connect"
            return
        if event.type == pygame.MOUSEBUTTONDOWN and self.info_back_rect.collidepoint(event.pos):
            self.screen_name = "connect"

    def handle_replay(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.screen_name = "connect"
            elif event.key == pygame.K_r:
                self.open_replay_viewer()
        if event.type == pygame.MOUSEBUTTONDOWN and self.info_back_rect.collidepoint(event.pos):
            self.screen_name = "connect"

    def handle_lobby(self, event):
        if self.challenge_pending:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_y:
                    send_msg(self.sock, {"type": "rematch_accept" if self.challenge_pending.get("rematch") else "challenge_accept"})
                    self.challenge_pending = None
                elif event.key == pygame.K_n:
                    send_msg(self.sock, {"type": "rematch_decline" if self.challenge_pending.get("rematch") else "challenge_decline"})
                    self.challenge_pending = None
            return
        self.chat_box.handle(event)
        if self.chat_box.active and self.chat_box.text.strip():
            self.send_typing_ping()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q and not self.chat_box.active:
                self.quick_chat_open = not self.quick_chat_open
            elif event.key == pygame.K_ESCAPE and self.quick_chat_open:
                self.quick_chat_open = False
            elif event.key == pygame.K_RETURN and self.chat_box.active:
                self.submit_chat_box()
            elif event.key == pygame.K_RETURN and self.selected_opponent:
                send_msg(self.sock, {"type": "challenge", "target": self.selected_opponent, "level_name": self.selected_level})
            elif event.key == pygame.K_w and self.game_active:
                send_msg(self.sock, {"type": "watch"})
            elif event.key == pygame.K_v:
                self.open_replay_viewer()
        if event.type == pygame.MOUSEBUTTONDOWN:
            for item in self.lobby_action_rects:
                if item["rect"].collidepoint(event.pos):
                    action = item["action"]
                    if action == "start":
                        self.start_selected_match()
                    elif action == "play_bot":
                        self.selected_opponent = "BOT"
                        self.set_banner("Mode: play with BOT")
                    elif action == "play_friend":
                        friend = next((p.get("name") for p in self.online_players if p.get("name") not in (self.username, "BOT")), None)
                        if friend:
                            self.selected_opponent = friend
                            self.set_banner(f"Mode: play with {friend}")
                        else:
                            self.selected_opponent = None
                            self.set_warning("No friend online yet")
                    elif action == "tutorial":
                        self.open_info_screen("tcp")
                    elif action == "settings":
                        self.selected_style = next_option(list(STYLE_COLORS), self.selected_style)
                        self.send_cosmetic_update()
                        self.set_banner(f"Style: {self.selected_style}")
                    elif action == "leaderboard":
                        top = self.scoreboard[0]["name"] if self.scoreboard else "No scores yet"
                        self.set_banner(f"Leaderboard: {top}")
                    return
            if self.send_btn.handle(event):
                self.submit_chat_box()
                return
            for item in self.network_tab_rects:
                if item["rect"].collidepoint(event.pos):
                    self.network_tab = item["tab"]
                    return
            if self.handle_cosmetic_click(event.pos):
                return
            if self.handle_chat_style_click(event.pos):
                return
            if self.handle_quick_chat_click(event.pos):
                return
            if self.handle_chat_click(event.pos):
                return
            for item in self.player_rects:
                if item["rect"].collidepoint(event.pos):
                    self.selected_opponent = item["name"]
                    return
            for item in self.difficulty_rects:
                if item["rect"].collidepoint(event.pos):
                    self.selected_level = item["level"]
                    return

    def movement_from_event(self, event):
        schemes = {
            "Arrows": {pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right"},
            "WASD": {pygame.K_w: "up", pygame.K_s: "down", pygame.K_a: "left", pygame.K_d: "right"},
            "IJKL": {pygame.K_i: "up", pygame.K_k: "down", pygame.K_j: "left", pygame.K_l: "right"},
        }
        return schemes.get(self.selected_control, schemes["Arrows"]).get(event.key)

    def handle_game(self, event):
        if self.challenge_pending:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_y:
                    send_msg(self.sock, {"type": "rematch_accept"})
                    self.challenge_pending = None
                elif event.key == pygame.K_n:
                    send_msg(self.sock, {"type": "rematch_decline"})
                    self.challenge_pending = None
            return
        self.chat_box.handle(event)
        if self.chat_box.active and self.chat_box.text.strip():
            self.send_typing_ping()
        if event.type == pygame.KEYDOWN:
            move = self.movement_from_event(event)
            if move:
                send_msg(self.sock, {"type": "move", "dir": move})
            elif event.key == pygame.K_q and not self.chat_box.active:
                self.quick_chat_open = not self.quick_chat_open
            elif event.key == pygame.K_ESCAPE and self.quick_chat_open:
                self.quick_chat_open = False
            elif event.key == pygame.K_RETURN and self.chat_box.active:
                self.submit_chat_box()
            elif event.key == pygame.K_1 and self.game_state:
                send_msg(self.sock, {"type": "cheer", "target": self.game_state.get("p1", "")})
            elif event.key == pygame.K_2 and self.game_state:
                send_msg(self.sock, {"type": "cheer", "target": self.game_state.get("p2", "")})
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.send_btn.handle(event):
                self.submit_chat_box()
                return
            for item in self.network_tab_rects:
                if item["rect"].collidepoint(event.pos):
                    self.network_tab = item["tab"]
                    return
            if self.handle_cosmetic_click(event.pos):
                return
            if self.handle_chat_style_click(event.pos):
                return
            if self.handle_quick_chat_click(event.pos):
                return
            self.handle_chat_click(event.pos)

    def handle_result(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                if self.sock:
                    send_msg(self.sock, {"type": "rematch_request"})
                    self.set_banner("Rematch requested")
            elif event.key == pygame.K_v:
                self.open_replay_viewer()
            elif event.key == pygame.K_ESCAPE:
                self.screen_name = "lobby"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for item in self.result_buttons:
                if item["rect"].collidepoint(event.pos):
                    action = item["action"]
                    if action == "rematch":
                        if self.sock:
                            send_msg(self.sock, {"type": "rematch_request"})
                            self.set_banner("Rematch requested")
                    elif action == "lobby":
                        self.screen_name = "lobby"
                    elif action == "exit":
                        self.send_disconnect()
                        self.running = False
                    return

    def draw_background(self):
        t = time.time()
        bg_key = ("tropical-bg", self.window_w, self.window_h, round(self.ui_scale, 3))
        bg = _SURFACE_CACHE.get(bg_key)
        if bg is None:
            bg = pygame.Surface((self.window_w, self.window_h)).convert()
            for y in range(self.window_h):
                amt = y / max(1, self.window_h)
                if amt < 0.50:
                    col = mix_color((4, 7, 35), (43, 21, 98), amt / 0.50)
                elif amt < 0.72:
                    col = mix_color((43, 21, 98), (255, 95, 67), (amt - 0.50) / 0.22)
                else:
                    col = mix_color((18, 84, 112), (7, 37, 70), (amt - 0.72) / 0.28)
                pygame.draw.line(bg, col, (0, y), (self.window_w, y))
            sun = (self.window_w // 2, int(self.window_h * 0.57))
            for rr, alpha in ((170, 18), (118, 34), (68, 58)):
                glow = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 200, 84, alpha), (rr, rr), rr)
                bg.blit(glow, (sun[0] - rr, sun[1] - rr))
            water_y = int(self.window_h * 0.58)
            draw_vertical_gradient(bg, (0, water_y, self.window_w, self.window_h - water_y), (7, 62, 98), (3, 31, 59), 255)
            pygame.draw.polygon(bg, (255, 174, 73), [(sun[0] - self.scale_dim(26, 16), water_y), (sun[0] + self.scale_dim(34, 20), water_y), (sun[0] + self.scale_dim(100, 54), int(self.window_h * 0.84)), (sun[0] - self.scale_dim(92, 50), int(self.window_h * 0.84))])
            island_y = int(self.window_h * 0.60)
            pygame.draw.polygon(bg, (11, 32, 48), [(0, island_y), (int(self.window_w * 0.15), island_y - self.scale_dim(80, 35)), (int(self.window_w * 0.33), island_y), (0, island_y)])
            pygame.draw.polygon(bg, (13, 42, 55), [(self.window_w, island_y), (int(self.window_w * 0.82), island_y - self.scale_dim(70, 32)), (int(self.window_w * 0.63), island_y), (self.window_w, island_y)])
            sand_y = int(self.window_h * 0.84)
            draw_vertical_gradient(bg, (0, sand_y, self.window_w, self.window_h - sand_y), (132, 84, 44), (88, 55, 31), 255)
            for px in (self.scale_dim(36, 18), self.window_w - self.scale_dim(38, 18)):
                lean = self.scale_dim(34, 18) if px < self.window_w // 2 else -self.scale_dim(34, 18)
                pygame.draw.line(bg, (91, 51, 24), (px, self.scale_dim(50, 32)), (px + lean, sand_y), self.scale_dim(14, 8))
                for k in range(8):
                    ang = -2.95 + k * 0.32 if px < self.window_w // 2 else -0.15 + k * 0.32
                    end = (int(px + math.cos(ang) * self.scale_dim(170, 78)), int(self.scale_dim(70, 38) + math.sin(ang) * self.scale_dim(104, 46)))
                    pygame.draw.line(bg, LEAF, (px, self.scale_dim(62, 38)), end, self.scale_dim(7, 4))
            for i, x in enumerate((self.scale_dim(58, 30), self.window_w - self.scale_dim(86, 44))):
                y = int(self.window_h * 0.46)
                pygame.draw.rect(bg, WOOD_DARK, (x - 10, y, 20, int(self.window_h * 0.30)))
                pygame.draw.polygon(bg, (255, 131, 41), [(x, y - 35), (x - 18, y + 12), (x + 18, y + 12)])
                pygame.draw.polygon(bg, (255, 223, 95), [(x, y - 22), (x - 9, y + 9), (x + 9, y + 9)])
            if len(_SURFACE_CACHE) < 700:
                _SURFACE_CACHE[bg_key] = bg
        self.screen.blit(bg, (0, 0))
        water_y = int(self.window_h * 0.58)
        water_y = int(self.window_h * 0.58)
        for i in range(20):
            y = water_y + i * max(9, self.scale_dim(16, 8))
            wave_w = max(110, self.scale_dim(210, 90))
            phase = int((t * 18 + i * 31) % wave_w)
            for x0 in range(-wave_w, self.window_w + wave_w, wave_w):
                color = (25, 171, 202) if i % 4 else (236, 172, 82)
                pygame.draw.arc(self.screen, color, (x0 + phase, y, wave_w, self.scale_dim(16, 7)), math.radians(190), math.radians(348), 1)
        draw_string_lights(self.screen, self.scale_dim(112, 70), self.window_w, t)
        for sx, sy, br in self.stars:
            twinkle = int(40 * (0.5 + 0.5 * math.sin(t * 2 + sx * 0.03)))
            color = (70 + twinkle, 90 + twinkle, min(255, int(150 + br * 45 + twinkle)))
            pygame.draw.circle(self.screen, color, (sx, sy), 1)
            if br > 1.45:
                pygame.draw.line(self.screen, color, (sx - 3, sy), (sx + 3, sy), 1)
                pygame.draw.line(self.screen, color, (sx, sy - 3), (sx, sy + 3), 1)

    def draw(self):
        if not (USE_IMAGE_TEMPLATE_UI and self.screen_name in ("connect", "lobby", "game")):
            self.draw_background()
        if self.screen_name == "connect":
            self.draw_connect()
        elif self.screen_name == "info":
            self.draw_info()
        elif self.screen_name == "replay":
            self.draw_replay()
        elif self.screen_name == "lobby":
            self.draw_lobby()
        elif self.screen_name == "game":
            self.draw_game()
        elif self.screen_name == "result":
            self.draw_result()
        else:
            # Fallback — treat any unknown screen as result if game_state exists, else lobby.
            if self.game_state and self.game_state.get("finished"):
                self.draw_result()
            else:
                self.draw_lobby()
        self.draw_banner()

    def draw_banner(self):
        if time.time() < self.warning_until and self.warning_text:
            banner_w = min(self.scale_dim(620, 320), self.window_w - self.safe_margin * 2)
            r = pygame.Rect(self.window_w // 2 - banner_w // 2, self.safe_margin, banner_w, max(34, self.scale_dim(42, 34)))
            draw_neon_rect(self.screen, r, (70, 15, 28), RED, radius=10, alpha=236, glow=True)
            draw_center(self.screen, self.warning_text, self.small_font, RED, self.window_w // 2, r.centery)
        elif time.time() < self.banner_until:
            banner_w = min(self.scale_dim(520, 260), self.window_w - self.safe_margin * 2)
            r = pygame.Rect(self.window_w // 2 - banner_w // 2, self.safe_margin, banner_w, max(34, self.scale_dim(42, 34)))
            draw_neon_rect(self.screen, r, VIOLET_DARK, GOLD, radius=10, alpha=232, glow=True)
            draw_center(self.screen, self.banner, self.small_font, GOLD, self.window_w // 2, r.centery)

    def draw_connect(self):
        # Clean procedural connect screen. The reference image is NOT used as a background,
        # so there is no fake IP/port/username text hiding behind real text.
        layout = self.layout["connect"]
        panel = layout["panel"]
        self.connect_menu_rects = []
        self.connect_option_rects = []

        draw_wood_title(self.screen, layout["title"], ["PITHON", "ARENA"], [self.title_font, self.title_font], [GOLD, MAGENTA])
        draw_panel(self.screen, panel, "ENTER THE ARENA", self.big_font, icon="players", header_h=max(44, self.scale_dim(56, 42)))

        # Inputs
        self.apply_input_layout()
        for box in (self.ip_box, self.port_box, self.user_box):
            box.draw(self.screen, self.med_font)

        # A strict vertical layout avoids the old overlap between LEVEL and TCP/LAN/REPLAY.
        inner_x = panel.x + self.panel_pad
        inner_w = panel.w - self.panel_pad * 2
        row_gap = max(10, self.scale_dim(14, 8))
        label_h = max(18, self.scale_dim(24, 18))
        btn_h = max(32, min(self.scale_dim(42, 34), int(panel.h * 0.065)))
        y = self.user_box.rect.bottom + max(20, self.scale_dim(28, 18))

        def option_row(title, opts, y):
            draw_text_fit(self.screen, title, self.small_font, GOLD, pygame.Rect(inner_x, y, inner_w, label_h))
            y += label_h + max(5, self.scale_dim(7, 4))
            gap = max(10, self.scale_dim(14, 8))
            btn_w = (inner_w - gap * (len(opts) - 1)) // len(opts)
            for i, (kind, value, color) in enumerate(opts):
                rect = pygame.Rect(inner_x + i * (btn_w + gap), y, btn_w, btn_h)
                active = (kind == "control" and value == self.selected_control) or (kind == "style" and value == self.selected_style) or (kind == "level" and value == self.selected_level)
                Button(rect.x, rect.y, rect.w, rect.h, value, color).draw(self.screen, self.small_font, active=active)
                self.connect_option_rects.append({"kind": kind, "value": value, "rect": rect})
            return y + btn_h + row_gap

        y = option_row("CHOOSE CONTROLS", [("control", "Arrows", GREEN), ("control", "WASD", CYAN), ("control", "IJKL", MAGENTA)], y)
        y = option_row("CHOOSE SNAKE STYLE", [("style", "Emerald", GREEN), ("style", "Sapphire", BLUE), ("style", "Violet", MAGENTA)], y)
        y = option_row("CHOOSE LEVEL", [("level", "Easy", GREEN), ("level", "Medium", GOLD), ("level", "Hard", RED), ("level", "Impossible", MAGENTA)], y)

        # Helper buttons are below levels, never on the same line. Hide them if the window is too short.
        connect_h = max(36, self.scale_dim(42, 34))
        helper_h = max(30, self.scale_dim(36, 28))
        helper_y = y + max(2, self.scale_dim(6, 2))
        connect_y = panel.bottom - connect_h - max(14, self.scale_dim(18, 12))
        if helper_y + helper_h + self.scale_dim(10, 6) < connect_y:
            gap = max(10, self.scale_dim(14, 8))
            menu_w = (inner_w - gap * 2) // 3
            for i, (mode, label, color) in enumerate((("tcp", "TCP / UDP", CYAN), ("lan", "LAN HELP", BLUE), ("replay", "VIEW REPLAY", MAGENTA))):
                rect = pygame.Rect(inner_x + i * (menu_w + gap), helper_y, menu_w, helper_h)
                Button(rect.x, rect.y, rect.w, rect.h, label, color).draw(self.screen, self.small_font)
                self.connect_menu_rects.append({"mode": mode, "rect": rect})

        button_w = min(max(190, self.scale_dim(300, 210)), inner_w // 2)
        self.connect_btn.rect = pygame.Rect(panel.centerx - button_w // 2, connect_y, button_w, connect_h)
        self.connect_btn.draw(self.screen, self.med_font, active=self.connecting)
        if self.connect_error:
            error_rect = pygame.Rect(inner_x, self.connect_btn.rect.y - self.scale_dim(34, 26), inner_w, self.scale_dim(28, 22))
            draw_text_fit(self.screen, self.connect_error, self.small_font, GOLD if self.connecting else RED, error_rect)
    def draw_info(self):
        safe = self.compute_safe_rect()
        panel = pygame.Rect(safe.x, safe.y + self.scale_dim(24, 18), safe.w, safe.h - self.scale_dim(48, 36))
        title = "TCP / UDP" if self.info_mode == "tcp" else "LAN HELP" if self.info_mode == "lan" else "NETWORK NOTES"
        icon = "chat" if self.info_mode == "tcp" else "players"
        draw_panel(self.screen, panel, title, self.med_font, icon=icon, header_h=max(42, self.scale_dim(58, 42)))
        lines = self.load_info_text()
        body_y = panel.y + self.scale_dim(78, 54)
        split = panel.w >= self.scale_dim(760, 520)
        if split:
            left = pygame.Rect(panel.x + self.panel_pad, body_y, max(300, panel.w // 2 - self.panel_pad * 2), panel.h - self.scale_dim(160, 120))
            right = pygame.Rect(left.right + self.gap, left.y, panel.right - self.panel_pad - (left.right + self.gap), left.h)
        else:
            left = pygame.Rect(panel.x + self.panel_pad, body_y, panel.w - self.panel_pad * 2, panel.h - self.scale_dim(240, 180))
            right = pygame.Rect(left.x, left.bottom + self.scale_dim(12, 8), panel.w - self.panel_pad * 2, self.scale_dim(164, 120))
        for i, line in enumerate(lines):
            draw_text(self.screen, f"- {line}", self.med_font if i == 0 else self.small_font, WHITE if i == 0 else ICE, left.x, left.y + i * self.scale_dim(42, 28))
        if self.info_mode == "tcp":
            table = [
                ("TCP", "Reliable, ordered, ACKed", GREEN),
                ("UDP", "Fast, but can drop or reorder", MAGENTA),
                ("Why TCP?", "Chat, ACKs, and shared game state stay consistent", CYAN),
            ]
        elif self.info_mode == "lan":
            table = [
                ("127.0.0.1", "Same machine", CYAN),
                ("Server IPv4", "Same WiFi", GREEN),
                ("Port forward", "Different WiFi / remote play", MAGENTA),
            ]
        else:
            table = [
                ("Diagnostics", "Traffic, ACKs, ping, and live throughput", CYAN),
                ("Protocol log", "HELLO, CHAT, MOVE, GAME_STATE, PING/PONG, ACK", GREEN),
                ("Events", "Broadcast from server for connect / match lifecycle", MAGENTA),
            ]
        for i, (head, body, color) in enumerate(table):
            row_y = right.y + i * self.scale_dim(74, 54) if split else right.y + i * self.scale_dim(54, 38)
            row_h = self.scale_dim(62, 44) if split else self.scale_dim(46, 34)
            row = pygame.Rect(right.x, row_y, right.w, row_h)
            draw_neon_rect(self.screen, row, FIELD, color, radius=9, alpha=220, glow=False)
            draw_text(self.screen, head, self.med_font if split else self.small_font, color, row.x + self.panel_pad, row.y + self.scale_dim(8, 6))
            draw_text(self.screen, fit_text(body, self.small_font, row.w - self.panel_pad * 2), self.small_font, WHITE, row.x + self.panel_pad, row.y + (self.scale_dim(34, 24) if split else self.scale_dim(22, 16)))
        back = pygame.Rect(panel.x + self.panel_pad, panel.bottom - self.scale_dim(60, 44), self.scale_dim(150, 104), self.scale_dim(36, 28))
        Button(back.x, back.y, back.w, back.h, "BACK", CYAN).draw(self.screen, self.small_font)
        self.info_back_rect = back

    def draw_replay(self):
        safe = self.compute_safe_rect()
        panel = pygame.Rect(safe.x, safe.y + self.scale_dim(22, 16), safe.w, safe.h - self.scale_dim(44, 32))
        draw_panel(self.screen, panel, "Last Replay", self.med_font, icon="trophy", header_h=max(42, self.scale_dim(58, 42)))
        back = pygame.Rect(panel.x + self.panel_pad, panel.bottom - self.scale_dim(60, 44), self.scale_dim(150, 104), self.scale_dim(36, 28))
        Button(back.x, back.y, back.w, back.h, "BACK", MAGENTA).draw(self.screen, self.small_font)
        draw_center(self.screen, "R = reload replay   ESC = back", self.small_font, BLUE, panel.centerx, panel.bottom - self.scale_dim(42, 30))
        self.info_back_rect = back
        if not self.replay_data:
            draw_center(self.screen, "No replay log available.", self.med_font, WHITE, panel.centerx, panel.centery)
            return
        frames = self.replay_frames or []
        if frames:
            elapsed = max(0.0, time.time() - self.replay_started_at)
            self.replay_frame_index = min(len(frames) - 1, int(elapsed * 10))
            frame = frames[self.replay_frame_index]
        else:
            frame = self.replay_data
        board_area = pygame.Rect(panel.x + self.panel_pad, panel.y + self.scale_dim(74, 52), max(320, int(panel.w * 0.62)), panel.h - self.scale_dim(144, 104))
        cell = max(10, min(board_area.w // 40, board_area.h // 30))
        board_w = cell * 40
        board_h = cell * 30
        board_x = board_area.x + max(0, (board_area.w - board_w) // 2)
        board_y = board_area.y + max(0, (board_area.h - board_h) // 2)
        self.board_offset = (board_x, board_y)
        self.cell = cell
        pygame.draw.rect(self.screen, PANEL2, (board_x - 4, board_y - 4, board_w + 8, board_h + 8), border_radius=8)
        pygame.draw.rect(self.screen, SOFT_BORDER, (board_x, board_y, board_w, board_h), 2, border_radius=8)
        for gx in range(0, board_w, cell):
            pygame.draw.line(self.screen, (24, 28, 48), (board_x + gx, board_y), (board_x + gx, board_y + board_h))
        for gy in range(0, board_h, cell):
            pygame.draw.line(self.screen, (24, 28, 48), (board_x, board_y + gy), (board_x + board_w, board_y + gy))
        for obs in frame.get("obstacles", []):
            r = pygame.Rect(board_x + obs["x"] * cell + 2, board_y + obs["y"] * cell + 2, cell - 4, cell - 4)
            pygame.draw.rect(self.screen, tuple(obs.get("color", (120, 120, 120))), r, border_radius=4)
        for pie in frame.get("pies", []):
            cx = board_x + pie["x"] * cell + cell // 2
            cy = board_y + pie["y"] * cell + cell // 2
            col = tuple(pie.get("color", (255, 208, 72)))
            pygame.draw.circle(self.screen, col, (cx, cy), max(3, cell // 2 - 2))
            pygame.draw.circle(self.screen, WHITE, (cx, cy), max(3, cell // 2 - 2), 1)
        for pu in frame.get("powerups", []):
            x = board_x + pu["x"] * cell + 3
            y = board_y + pu["y"] * cell + 3
            pygame.draw.rect(self.screen, tuple(pu.get("color", CYAN)), (x, y, cell - 6, cell - 6), border_radius=5)
        for idx, player in enumerate(frame.get("players", self.replay_data.get("players", []))[:2]):
            body = frame.get("snakes", {}).get(player, [])
            style = frame.get("styles", {}).get(player, "Emerald")
            cosmetics = frame.get("cosmetics", {}).get(player, {})
            pixel_segments = [(board_x + seg[0] * cell + 2, board_y + seg[1] * cell + 2) for seg in body]
            self.draw_snake_segments(pixel_segments, style, cosmetics)
        draw_center(self.screen, f"Level: {frame.get('level_name', self.replay_data.get('level', 'Unknown'))}", self.med_font, WHITE, panel.centerx, panel.y + self.scale_dim(54, 36))
        draw_center(self.screen, f"Winner: {frame.get('winner', self.replay_data.get('winner', '?'))}", self.small_font, GOLD, panel.centerx, panel.y + self.scale_dim(78, 52))
        stacked = panel.w < self.scale_dim(700, 480)
        if stacked:
            timeline = pygame.Rect(panel.x + self.panel_pad, board_y + board_h + self.scale_dim(18, 12), panel.w - self.panel_pad * 2, max(100, panel.bottom - (board_y + board_h) - self.scale_dim(86, 60)))
        else:
            timeline = pygame.Rect(board_area.right + self.gap, board_area.y, panel.right - self.panel_pad - (board_area.right + self.gap), board_area.h)
        draw_neon_rect(self.screen, timeline, FIELD, SOFT_BORDER, radius=9, alpha=214, glow=False)
        draw_text(self.screen, "EVENTS", self.small_font, WHITE, timeline.x + self.panel_pad, timeline.y + self.scale_dim(8, 6))
        events = frame.get("events", self.replay_data.get("events", []))[-8:]
        for i, item in enumerate(events):
            color = tuple(item.get("color", (255, 255, 255)))
            text = fit_text(item.get("text", ""), self.small_font, timeline.w - self.panel_pad * 2)
            draw_text(self.screen, text, self.small_font, color, timeline.x + self.panel_pad, timeline.y + self.scale_dim(30, 20) + i * self.scale_dim(32, 22))
        if not frames:
            draw_text(self.screen, "Legacy log: event timeline only", self.small_font, MUTED, timeline.x + self.panel_pad, timeline.bottom - self.scale_dim(26, 18))

    def selected_player_record(self):
        for player in self.online_players:
            if player.get("name") == self.selected_opponent:
                return player
        for player in self.online_players:
            if player.get("name") == self.username:
                return player
        return None

    def draw_lobby_header(self):
        header = self.layout["lobby"]["header"]
        draw_text(self.screen, "LOBBY", self.big_font, WHITE, header.x + self.panel_pad, header.y + self.scale_dim(12, 8))
        draw_face_icon(self.screen, header.x + self.scale_dim(140, 104), header.y + self.scale_dim(32, 24), GREEN, "insane")
        title_name = (self.username or "ZOMBIE").upper()
        draw_text(self.screen, title_name, self.big_font, GREEN, header.x + self.scale_dim(170, 130), header.y + self.scale_dim(12, 8))
        title_w = max(self.scale_dim(270, 180), min(self.scale_dim(450, 270), header.w - self.scale_dim(520, 190)))
        title_rect = pygame.Rect(header.centerx - title_w // 2, header.y, title_w, header.h)
        draw_wood_title(self.screen, title_rect, ["SNAKE", "ISLAND"], [self.big_font, self.big_font], [GOLD, CYAN])
        status_w = min(self.scale_dim(278, 190), header.w // 3)
        status_h = min(header.h, self.scale_dim(72, 54))
        self.draw_status_card(header.right - status_w, header.y, status_w, status_h)

    def draw_status_card(self, x, y, w, h):
        selected = self.selected_player_record() or {"name": self.username or "PLAYER", "wins": 0}
        name = str(selected.get("name", "PLAYER")).upper()
        wins = int(selected.get("wins", 0))
        draw_neon_rect(self.screen, (x, y, w, h), FIELD, SOFT_BORDER, radius=max(8, self.scale_dim(10, 8)), alpha=226, glow=False)
        draw_robot_icon(self.screen, x + self.scale_dim(38, 28), y + h // 2, self.scale_dim(28, 20), GREEN)
        label = fit_text(f"{name} ({wins}W)", self.med_font, max(40, w - self.scale_dim(160, 110)))
        draw_text(self.screen, label, self.med_font, GREEN, x + self.scale_dim(76, 56), y + self.scale_dim(24, 18))
        pill = pygame.Rect(x + w - self.scale_dim(78, 56), y + self.scale_dim(18, 12), self.scale_dim(62, 46), self.scale_dim(36, 28))
        draw_neon_rect(self.screen, pill, FIELD, GREEN, radius=8, alpha=230, glow=False)
        draw_center(self.screen, "HOST", self.small_font, GREEN, pill.centerx, pill.centery)

    def draw_player_list_panel(self):
        rect = self.layout["lobby"]["left_players"]
        x, y, w, h = rect
        draw_panel(self.screen, rect, "Online Players", self.med_font, icon="players", header_h=max(42, self.scale_dim(58, 42)))
        self.player_rects = []
        if not self.online_players:
            draw_center(self.screen, "Waiting for players...", self.small_font, MUTED, x + w // 2, y + 180)
            return
        row_h = max(self.scale_dim(48, 34), 34)
        top = y + max(50, self.scale_dim(68, 50))
        step = row_h + max(6, self.scale_dim(10, 6))
        visible_rows = max(1, min(len(self.online_players), (h - (top - y) - self.panel_pad) // step))
        for i, player in enumerate(self.online_players[:visible_rows]):
            row = pygame.Rect(x + self.panel_pad // 2, top + i * step, w - self.panel_pad, row_h)
            name = player.get("name", "?")
            active = name == self.selected_opponent
            border = GREEN if active else SOFT_BORDER
            fill = mix_color(GREEN, FIELD, 0.78) if active else FIELD
            draw_neon_rect(self.screen, row, fill, border, radius=9, alpha=226, glow=active)
            if player.get("role") == "bot" or player.get("head_style") == "Robot":
                draw_robot_icon(self.screen, row.x + self.scale_dim(31, 24), row.centery, self.scale_dim(24, 18), GREEN)
            else:
                self.draw_avatar(row.x + self.scale_dim(31, 24), row.centery, {"sender": name})
            label = fit_text(f"{str(name).upper()} ({player.get('wins', 0)}W)", self.med_font, row.w - self.scale_dim(120, 80))
            draw_text(self.screen, label, self.med_font, GREEN if active else WHITE, row.x + self.scale_dim(62, 48), row.y + max(8, self.scale_dim(14, 8)))
            if active or player.get("role") == "bot":
                draw_crown(self.screen, row.right - self.scale_dim(34, 24), row.centery)
            self.player_rects.append({"name": name, "rect": row})

    def draw_how_to_panel(self):
        x, y, w, h = self.layout["lobby"]["left_help"]
        draw_neon_rect(self.screen, (x, y, w, h), VIOLET_DARK, MAGENTA, radius=max(8, self.scale_dim(10, 8)), alpha=220, glow=True)
        draw_text(self.screen, "HOW TO PLAY", self.small_font, MAGENTA, x + 16, y + 18)
        tips = [
            "Select your level difficulty",
            "Customize your appearance",
            "Use chat to communicate",
            "Be the last survivor!",
        ]
        line_gap = max(18, self.scale_dim(26, 18))
        for i, tip in enumerate(tips):
            draw_text(self.screen, f"- {tip}", self.small_font, MUTED, x + self.panel_pad // 2, y + self.scale_dim(48, 32) + i * line_gap)
        draw_text(self.screen, "Q  Quick Chat Wheel      /w Whisper", self.small_font, (156, 118, 224), x + self.scale_dim(26, 18), y + h - self.scale_dim(28, 20))

    def draw_scoreboard_panel(self):
        """Scoreboard with safe spacing so rows never collide with difficulty buttons."""
        rect = self.layout["lobby"]["center_score"]
        x, y, w, h = rect
        draw_panel(self.screen, rect, "Scoreboard" if w > self.scale_dim(300, 200) else "Board", self.med_font, icon="trophy", header_h=max(42, self.scale_dim(58, 42)))
        self.difficulty_rects = []

        diff_h = max(self.scale_dim(82, 68), 64)
        diff_box = pygame.Rect(x + self.panel_pad // 2, y + h - diff_h - self.panel_pad // 2, w - self.panel_pad, diff_h)
        rows_top = y + max(52, self.scale_dim(70, 50))
        rows_bottom = diff_box.y - max(8, self.scale_dim(12, 8))
        available_h = max(0, rows_bottom - rows_top)
        row_gap = max(4, self.scale_dim(6, 4))
        row_h = max(24, min(max(self.scale_dim(34, 24), 24), (available_h - row_gap * 2) // 3 if available_h else 24))
        max_rows = max(0, min(len(self.scoreboard), 3, available_h // max(1, row_h + row_gap)))
        rows = self.scoreboard[:max_rows]
        if not rows:
            empty_rect = pygame.Rect(x + self.panel_pad, rows_top, w - self.panel_pad * 2, max(34, rows_bottom - rows_top))
            draw_text_fit(self.screen, "No scores yet. Play a match to update this board.", self.small_font, MUTED, empty_rect)
        for i, row_data in enumerate(rows):
            row = pygame.Rect(x + self.panel_pad // 2, rows_top + i * (row_h + row_gap), w - self.panel_pad, row_h)
            pygame.draw.rect(self.screen, (16, 31, 63), row, border_radius=8)
            rank = i + 1
            rank_color = [GOLD, ICE, (255, 139, 83), MUTED][i] if i < 4 else MUTED
            badge_x = row.x + self.scale_dim(22, 18)
            pygame.draw.circle(self.screen, rank_color, (badge_x, row.centery), max(7, self.scale_dim(12, 8)), 2)
            draw_center(self.screen, str(rank), self.small_font, rank_color, badge_x, row.centery)
            stats = f"W:{row_data.get('wins', 0)}  L:{row_data.get('losses', 0)}  G:{row_data.get('games', 0)}"
            stats_w = self.small_font.render(stats, True, ICE).get_width() + self.scale_dim(12, 8)
            name_max = max(40, row.w - stats_w - self.scale_dim(68, 48))
            name_label = fit_text(f"{rank}. {row_data.get('name', '?')}", self.small_font, name_max)
            draw_text(self.screen, name_label, self.small_font, ICE, row.x + self.scale_dim(52, 38), row.y + max(5, (row.h - self.small_font.get_height()) // 2))
            draw_text(self.screen, stats, self.small_font, ICE, row.right - stats_w, row.y + max(5, (row.h - self.small_font.get_height()) // 2))

        draw_neon_rect(self.screen, diff_box, VIOLET_DARK, SOFT_BORDER, radius=8, alpha=214, glow=False)
        draw_center(self.screen, "SELECT DIFFICULTY", self.small_font, WHITE, diff_box.centerx, diff_box.y + max(16, self.scale_dim(22, 16)))
        gap = max(6, self.scale_dim(14, 6))
        btn_h = max(32, min(self.scale_dim(48, 36), diff_box.h - self.scale_dim(38, 30)))
        btn_w = max(54, (diff_box.w - gap * (len(LEVELS) - 1) - self.scale_dim(18, 10)) // len(LEVELS))
        start_x = diff_box.x + (diff_box.w - (btn_w * len(LEVELS) + gap * (len(LEVELS) - 1))) // 2
        moods = {"Easy": "easy", "Medium": "medium", "Hard": "hard", "Impossible": "insane"}
        for i, level in enumerate(LEVELS):
            r = pygame.Rect(start_x + i * (btn_w + gap), diff_box.bottom - btn_h - self.scale_dim(8, 6), btn_w, btn_h)
            active = level == self.selected_level
            color = level_color(level)
            fill = mix_color(color, FIELD, 0.55) if active else FIELD
            draw_neon_rect(self.screen, r, fill, color, radius=9, alpha=232, glow=active)
            draw_face_icon(self.screen, r.x + self.scale_dim(29, 18), r.centery, color, moods.get(level, "easy"))
            label = level_display(level).upper() if r.w >= self.scale_dim(92, 64) else {"Easy": "EZ", "Medium": "MED", "Hard": "HRD", "Impossible": "INS"}[level]
            draw_text_fit(self.screen, label, self.small_font, color, pygame.Rect(r.x + self.scale_dim(48, 28), r.y, max(20, r.w - self.scale_dim(54, 34)), r.h))
            self.difficulty_rects.append({"level": level, "rect": r})

    def draw_chat_panel(self):
        x, y, w, h = self.layout["lobby"]["right_chat"]
        draw_panel(self.screen, (x, y, w, h), "Chat", self.med_font, icon="chat", header_h=max(42, self.scale_dim(58, 42)))
        self.draw_chat_style_picker(x + self.panel_pad, y + max(52, self.scale_dim(72, 50)), w - self.panel_pad * 2)
        chat_top = y + max(124, self.scale_dim(150, 116))
        monitor_h = max(110, self.scale_dim(146, 104))
        chat_h = max(40, h - (chat_top - y) - monitor_h - self.scale_dim(58, 44))
        visible_count = max(3, min(12, chat_h // self.chat_row_h))
        self.draw_chat_list(x + self.panel_pad, chat_top, w - self.panel_pad * 2, chat_h, visible_count)
        if self.typing_users:
            typing_text = ", ".join(self.typing_users[:2]) + ("..." if len(self.typing_users) > 2 else "")
            draw_text(self.screen, f"{typing_text} typing...", self.small_font, GOLD, x + self.panel_pad, y + h - self.scale_dim(72, 52))
        net_y = chat_top + chat_h + self.scale_dim(10, 8)
        net_h = max(96, h - (net_y - y) - self.scale_dim(18, 12))
        if net_h > 40:
            self.draw_network_monitor_panel(x + self.panel_pad // 2, net_y, w - self.panel_pad, net_h)
        draw_center(self.screen, "Q = Quick chat wheel", self.small_font, BLUE, x + w // 2, y + h - self.scale_dim(24, 16))

    def draw_bottom_action_bar(self):
        bottom = self.layout["lobby"]["bottom"]
        self.chat_box.draw(self.screen, self.small_font)
        self.send_btn.draw(self.screen, self.med_font)
        bar_x = self.send_btn.rect.right + self.gap
        bar = pygame.Rect(bar_x, bottom.y, max(100, bottom.right - bar_x), bottom.h)
        draw_neon_rect(self.screen, bar, FIELD, SOFT_BORDER, radius=10, alpha=226, glow=False)
        badge = pygame.Rect(bar.x + self.scale_dim(18, 10), bar.y + self.scale_dim(12, 8), self.scale_dim(32, 24), self.scale_dim(28, 22))
        pygame.draw.circle(self.screen, GREEN, badge.center, self.scale_dim(15, 12))
        draw_center(self.screen, "Z", self.small_font, BLACK, badge.centerx, badge.centery)
        draw_text(self.screen, (self.username or "ZOMBIE").upper()[:12], self.small_font, GREEN, bar.x + self.scale_dim(62, 42), bar.y + self.scale_dim(17, 12))
        labels = [("O", RED), ("F", BLUE), ("S", ICE), ("B", GOLD), ("K", MUTED)]
        start_x = bar.x + max(self.scale_dim(205, 118), int(bar.w * 0.42))
        gap = max(self.scale_dim(55, 28), 28)
        for i, (label, color) in enumerate(labels):
            cx = start_x + i * gap
            if cx > bar.right - self.scale_dim(20, 16):
                break
            if i == 0:
                pygame.draw.circle(self.screen, color, (cx, bar.centery), self.scale_dim(13, 9), 3)
                pygame.draw.circle(self.screen, color, (cx, bar.centery), self.scale_dim(5, 3), 2)
            else:
                draw_center(self.screen, label, self.big_font, color, cx, bar.centery)

    def draw_challenge_overlay(self):
        if not self.challenge_pending:
            return
        header = self.layout["lobby"]["header"]
        overlay_w = min(self.scale_dim(460, 240), self.window_w - self.safe_margin * 2)
        overlay_h = self.scale_dim(132, 92)
        r = pygame.Rect(self.window_w // 2 - overlay_w // 2, header.bottom + self.gap, overlay_w, overlay_h)
        draw_neon_rect(self.screen, r, VIOLET_DARK, GOLD, radius=12, alpha=242, glow=True)
        txt = "Rematch" if self.challenge_pending.get("rematch") else "Challenge"
        draw_center(self.screen, f"{txt} from {self.challenge_pending.get('from')}", self.med_font, WHITE, r.centerx, r.y + self.scale_dim(44, 30))
        draw_center(self.screen, "Press Y to accept - N to decline", self.small_font, GOLD, r.centerx, r.y + self.scale_dim(86, 62))

    def draw_play_mode_panel(self):
        rect = self.layout["lobby"].get("center_mode")
        if not rect:
            return
        draw_neon_rect(self.screen, rect, PANEL2, SOFT_BORDER, radius=12, alpha=220, glow=False)
        title_rect = pygame.Rect(rect.x + self.panel_pad, rect.y + 4, rect.w - self.panel_pad * 2, max(16, rect.h // 4))
        draw_text_fit(self.screen, "CHOOSE MODE, THEN START", self.small_font, GOLD, title_rect)
        gap = max(10, self.scale_dim(14, 8))
        btn_y = rect.y + max(24, rect.h // 4)
        btn_h = max(28, rect.h - (btn_y - rect.y) - 8)
        btn_w = max(70, (rect.w - self.panel_pad * 2 - gap * 2) // 3)
        bot_rect = pygame.Rect(rect.x + self.panel_pad, btn_y, btn_w, btn_h)
        friend_rect = pygame.Rect(bot_rect.right + gap, btn_y, btn_w, btn_h)
        start_rect = pygame.Rect(friend_rect.right + gap, btn_y, btn_w, btn_h)
        Button(bot_rect.x, bot_rect.y, bot_rect.w, bot_rect.h, "PLAY BOT", GREEN).draw(self.screen, self.small_font, active=(self.selected_opponent == "BOT"))
        Button(friend_rect.x, friend_rect.y, friend_rect.w, friend_rect.h, "PLAY FRIEND", CYAN).draw(self.screen, self.small_font, active=(self.selected_opponent and self.selected_opponent != "BOT"))
        can_start = bool(self.selected_opponent)
        Button(start_rect.x, start_rect.y, start_rect.w, start_rect.h, "START", GOLD if can_start else GRAY, BLACK).draw(self.screen, self.small_font, active=can_start)
        self.lobby_action_rects.append({"action": "play_bot", "rect": bot_rect})
        self.lobby_action_rects.append({"action": "play_friend", "rect": friend_rect})
        self.lobby_action_rects.append({"action": "start", "rect": start_rect})

    def draw_lobby(self):
        # Dashboard lobby: online players + scoreboard + snake customization + chat.
        # The three-snake splash screen was removed; this is the real multiplayer setup screen.
        self.player_rects = []
        self.difficulty_rects = []
        self.lobby_action_rects = []
        self.cosmetic_rects = []

        self.draw_lobby_header()
        self.draw_player_list_panel()
        self.draw_how_to_panel()
        self.draw_scoreboard_panel()
        self.draw_play_mode_panel()
        custom = self.layout["lobby"].get("center_custom")
        if custom:
            self.draw_cosmetic_panel(custom.x, custom.y, custom.w, custom.h)
        self.draw_chat_panel()
        net = self.layout["lobby"].get("right_net")
        if net:
            self.draw_network_monitor_panel(net.x, net.y, net.w, net.h)
        self.apply_lobby_input_layout()
        self.draw_bottom_action_bar()
        self.draw_challenge_overlay()
    def draw_health_bar(self, x, y, w, h, pct, color):
        pygame.draw.rect(self.screen, PANEL, (x, y, w, h), border_radius=5)
        fill = max(0, min(w, int(w * pct)))
        if fill:
            pygame.draw.rect(self.screen, color, (x, y, fill, h), border_radius=5)
        pygame.draw.rect(self.screen, GRAY, (x, y, w, h), 1, border_radius=5)

    def draw_template_player_card(self, rect: pygame.Rect, player, gs, idx):
        if not player:
            return
        rect = pygame.Rect(rect)
        style = gs.get('styles', {}).get(player, 'Emerald')
        cosmetics = gs.get('cosmetics', {}).get(player, {})
        head, _ = STYLE_COLORS.get(style, STYLE_COLORS['Emerald'])
        text_area = pygame.Rect(rect.x + int(rect.w * 0.38), rect.y + int(rect.h * 0.13), int(rect.w * 0.56), int(rect.h * 0.76))
        self.clean_template_zone(text_area.inflate(10, 8), alpha=188, radius=8)
        draw_text_fit(self.screen, str(player).upper(), self.big_font, head, pygame.Rect(text_area.x, text_area.y, text_area.w, max(24, int(rect.h * 0.16))))
        hp = gs.get('health', {}).get(player, 0)
        hp_rect = pygame.Rect(text_area.x, text_area.y + int(rect.h * 0.20), max(50, int(text_area.w * 0.62)), max(8, int(rect.h * 0.035)))
        self.draw_health_bar(hp_rect.x, hp_rect.y, hp_rect.w, hp_rect.h, hp / 160.0, head)
        draw_text_shadow(self.screen, f"HP {int(hp)}", self.small_font, WHITE, hp_rect.right + 4, hp_rect.y - 4, max_width=max(34, text_area.right - hp_rect.right - 4))
        effects = gs.get('effects', {}).get(player, {})
        active = [k.replace('_until', '') for k, v in effects.items() if v > time.time()]
        st = gs.get('stats', {}).get(player, {})
        lines = [
            f"Effects: {', '.join(active) if active else 'None'}",
            f"{cosmetics.get('head_style', 'Classic')}: {cosmetics.get('trail_style', 'None')}",
            f"Pies: {st.get('pies_eaten', 0)}",
            f"Powerups: {st.get('powerups_used', 0)}",
            f"Damage: {st.get('damage_taken', 0)}",
            f"Collisions: {st.get('collisions', 0)}",
        ]
        line_h = max(14, min(self.scale_dim(20, 13), (text_area.bottom - hp_rect.bottom - 8) // max(1, len(lines))))
        y = hp_rect.bottom + 8
        for i, line in enumerate(lines):
            if y > text_area.bottom - self.small_font.get_height():
                break
            draw_text_shadow(self.screen, line, self.small_font, GOLD if i == 0 else WHITE, text_area.x, y, max_width=text_area.w)
            y += line_h

    def draw_game(self):
        # Clean responsive game screen. The board is intentionally a plain ocean/grid panel; no snake image is behind gameplay.
        if not self.game_state:
            wait_rect = pygame.Rect(self.window_w // 2 - self.scale_dim(250, 170), self.window_h // 2 - self.scale_dim(28, 20), self.scale_dim(500, 340), self.scale_dim(56, 40))
            draw_alpha_rect(self.screen, BLACK, wait_rect, 170, radius=12)
            draw_text_fit(self.screen, "Waiting for game state...", self.big_font, WHITE, wait_rect)
            return
        gs = self.game_state
        current_ping = gs.get('your_ping', self.my_ping_ms)
        layout = self.layout["game"]
        header = layout["header"]
        center = layout["center"]
        right = layout["right"]
        bottom = layout["bottom"]

        # Header/logo and timer
        title_r = pygame.Rect(center.x, header.y, center.w, header.h)
        draw_glow_text(self.screen, "PITHON", self.big_font, GOLD, (title_r.centerx, title_r.y + title_r.h // 3), GREEN)
        draw_glow_text(self.screen, "ARENA", self.big_font, MAGENTA, (title_r.centerx, title_r.y + title_r.h * 2 // 3), MAGENTA)
        status = layout["level_stats"]
        draw_neon_rect(self.screen, status, FIELD, GREEN, radius=9, alpha=225, glow=False)
        line_h = max(14, status.h // 3)
        draw_text(self.screen, f"LEVEL: {gs.get('level_name', 'Easy').upper()}", self.small_font, GREEN, status.x + 8, status.y + 4)
        draw_text(self.screen, ping_label(current_ping), self.small_font, ping_color(current_ping), status.x + 8, status.y + 4 + line_h)
        draw_text(self.screen, f"Tick: {gs.get('tickrate', 10)} Hz", self.small_font, WHITE, status.x + 8, status.y + 4 + line_h * 2)
        tl = gs.get("time_left", 0)
        timer_rect = layout["timer"]
        draw_neon_rect(self.screen, timer_rect, PANEL2, GOLD, radius=10, alpha=238, glow=True)
        draw_text_fit(self.screen, f"{int(tl//60):02d}:{int(tl%60):02d}", self.big_font, RED if tl < 15 else WHITE, timer_rect)

        # Left player panel
        cards = layout.get("player_cards", [])
        if len(cards) >= 2:
            self.draw_player_card(cards[0].x, cards[0].y, gs.get("p1"), gs, 0, cards[0].w, cards[0].h)
            self.draw_player_card(cards[1].x, cards[1].y, gs.get("p2"), gs, 1, cards[1].w, cards[1].h)
        event_rect = layout["event_log"]
        draw_neon_rect(self.screen, event_rect, FIELD, GOLD, radius=9, alpha=225, glow=False)
        for i, text in enumerate(gs.get("events", [])[-3:]):
            draw_text(self.screen, fit_text(text.get("text", ""), self.small_font, event_rect.w - 16), self.small_font, tuple(text.get("color", WHITE)), event_rect.x + 8, event_rect.y + 8 + i * max(16, self.scale_dim(20, 14)))

        # Center board
        board_panel = pygame.Rect(layout["board"])
        draw_bamboo_frame(self.screen, board_panel.inflate(self.scale_dim(14, 8), self.scale_dim(14, 8)), radius=12, thickness=max(8, self.scale_dim(10, 7)))
        cell = max(7, min(board_panel.w // 40, board_panel.h // 30))
        board_w = cell * 40
        board_h = cell * 30
        ox = board_panel.x + max(0, (board_panel.w - board_w) // 2)
        oy = board_panel.y + max(0, (board_panel.h - board_h) // 2)
        self.board_offset = (ox, oy)
        self.cell = cell
        pygame.draw.rect(self.screen, (9, 34, 58), (ox, oy, board_w, board_h), border_radius=8)
        sea = pygame.Surface((board_w, board_h), pygame.SRCALPHA)
        for yy in range(board_h):
            amt = yy / max(1, board_h)
            pygame.draw.line(sea, (*mix_color((27, 75, 130), (15, 136, 155), amt), 180), (0, yy), (board_w, yy))
        self.screen.blit(sea, (ox, oy))
        grid = pygame.Surface((board_w, board_h), pygame.SRCALPHA)
        for gx in range(0, board_w + 1, cell):
            pygame.draw.line(grid, (255, 210, 120, 70), (gx, 0), (gx, board_h))
        for gy in range(0, board_h + 1, cell):
            pygame.draw.line(grid, (255, 210, 120, 70), (0, gy), (board_w, gy))
        self.screen.blit(grid, (ox, oy))

        for obs in gs.get("obstacles", []):
            r = pygame.Rect(ox + obs["x"] * cell + 2, oy + obs["y"] * cell + 2, max(2, cell - 4), max(2, cell - 4))
            pygame.draw.rect(self.screen, tuple(obs.get("color", (120, 120, 120))), r, border_radius=4)
        for pie in gs.get("pies", []):
            cx = ox + pie["x"] * cell + cell // 2
            cy = oy + pie["y"] * cell + cell // 2
            col = tuple(pie.get("color", WHITE))
            pygame.draw.circle(self.screen, col, (cx, cy), max(3, cell // 2 - 2))
            pygame.draw.circle(self.screen, WHITE, (cx, cy), max(3, cell // 2 - 2), 1)
        for pu in gs.get("powerups", []):
            x = ox + pu["x"] * cell + 3
            y = oy + pu["y"] * cell + 3
            col = tuple(pu.get("color", CYAN))
            pygame.draw.rect(self.screen, col, (x, y, max(3, cell - 6), max(3, cell - 6)), border_radius=5)
            draw_center(self.screen, pu.get("kind", "?")[0].upper(), self.small_font, BLACK, x + max(3, cell - 6) // 2, y + max(3, cell - 6) // 2)
        for player in [gs.get("p1"), gs.get("p2")]:
            body = gs.get("snakes", {}).get(player, [])
            style = gs.get("styles", {}).get(player, "Emerald")
            cosmetics = gs.get("cosmetics", {}).get(player, {})
            pixel_segments = [(ox + seg[0] * cell + 2, oy + seg[1] * cell + 2) for seg in body]
            self.draw_trail_effect([(x + cell // 2, y + cell // 2) for x, y in pixel_segments], cosmetics)
            self.draw_snake_segments(pixel_segments, style, cosmetics)
        for p in self.particles:
            pygame.draw.circle(self.screen, p["color"], (int(p["x"]), int(p["y"])), max(1, int(4 * p["life"] / 0.6)))
        if not gs.get("started"):
            c = math.ceil(gs.get("countdown", 0))
            r = pygame.Rect(center.centerx - self.scale_dim(90, 60), center.centery - self.scale_dim(42, 28), self.scale_dim(180, 120), self.scale_dim(84, 56))
            draw_neon_rect(self.screen, r, VIOLET_DARK, GOLD, radius=12, alpha=232, glow=True)
            draw_center(self.screen, c if c > 0 else "GO!", self.title_font, GOLD, center.centerx, center.centery)

        # Right panels
        spectator_rect = layout["spectators"]
        draw_neon_rect(self.screen, spectator_rect, FIELD, CYAN, radius=8, alpha=225, glow=False)
        draw_text_fit(self.screen, f"SPECTATORS {int(gs.get('spectators', 0))}", self.small_font, CYAN, spectator_rect)
        net_rect = layout["net_panel"]
        self.draw_network_monitor_panel(net_rect.x, net_rect.y, net_rect.w, net_rect.h, template=False)
        style_rect = layout["chat_style_buttons"]
        self.draw_chat_style_picker(style_rect.x, style_rect.y, style_rect.w, template=False)
        chat_rect = layout["chat_panel"]
        draw_neon_rect(self.screen, chat_rect, PANEL2, SOFT_BORDER, radius=10, alpha=225, glow=False)
        self.draw_chat_list(chat_rect.x + 8, chat_rect.y + 8, chat_rect.w - 16, chat_rect.h - 16, max(3, min(6, chat_rect.h // max(52, self.chat_row_h))))
        if self.typing_users:
            draw_text(self.screen, f"{self.typing_users[0]} typing...", self.small_font, GOLD, chat_rect.x + 8, chat_rect.bottom - 20)

        # Bottom chat and ability bar
        self.chat_box.rect = layout["chat_input"]
        self.send_btn.rect = layout["send"]
        self.chat_box.draw(self.screen, self.small_font)
        self.send_btn.draw(self.screen, self.small_font)
        ability = layout["ability_bar"]
        draw_neon_rect(self.screen, ability, FIELD, GOLD, radius=10, alpha=225, glow=False)
        name_rect = layout["player_name_bottom"]
        draw_text_fit(self.screen, (self.username or "PLAYER").upper(), self.small_font, GREEN, name_rect)
        icon_w = max(24, min(48, (ability.w - name_rect.w - self.gap) // 5)) if ability.w > name_rect.w + self.gap else 0
        if icon_w > 0:
            x0 = name_rect.right + self.gap
            for i, label in enumerate(["Z", "F", "S", "B", "K"]):
                r = pygame.Rect(x0 + i * (icon_w + self.scale_dim(8, 4)), ability.y + (ability.h - icon_w)//2, icon_w, icon_w)
                pygame.draw.circle(self.screen, [GREEN, RED, BLUE, GOLD, VIOLET][i], r.center, icon_w//2)
                draw_center(self.screen, label, self.med_font, BLACK, r.centerx, r.centery)
        self.draw_quick_chat_wheel(center.centerx, bottom.y - self.scale_dim(120, 84))

        if self.challenge_pending:
            overlay_w = min(self.scale_dim(360, 220), self.window_w - self.safe_margin * 2)
            overlay_h = self.scale_dim(120, 86)
            r = pygame.Rect(self.window_w // 2 - overlay_w // 2, header.bottom + self.gap, overlay_w, overlay_h)
            draw_neon_rect(self.screen, r, VIOLET_DARK, GOLD, radius=12, alpha=235, glow=True)
            txt = "Rematch" if self.challenge_pending.get("rematch") else "Challenge"
            draw_center(self.screen, f"{txt} from {self.challenge_pending.get('from')}", self.med_font, WHITE, r.centerx, r.y + self.scale_dim(40, 28))
            draw_center(self.screen, "Press Y / N", self.small_font, GOLD, r.centerx, r.y + self.scale_dim(78, 54))
    def draw_player_card(self, x, y, player, gs, idx, width=None, height=None):
        if not player:
            return
        style = gs.get('styles', {}).get(player, 'Emerald')
        cosmetics = gs.get('cosmetics', {}).get(player, {})
        head, body = STYLE_COLORS.get(style, STYLE_COLORS['Emerald'])
        if width is None:
            card_w = max(210, min(self.scale_dim(300, 220), max(210, self.window_w // 3 - self.scale_dim(26, 16))))
            card_h = max(150, self.scale_dim(178, 132))
            game_left = self.layout.get("game", {}).get("left")
            if game_left:
                card_w = min(card_w, max(200, game_left.w - self.panel_pad))
                card_h = min(max(card_h, self.scale_dim(170, 128)), max(130, (game_left.h - self.scale_dim(120, 84)) // 2))
        else:
            card_w = max(150, int(width))
            card_h = max(130, int(height or self.scale_dim(178, 132)))
        draw_neon_rect(self.screen, (x, y, card_w, card_h), FIELD, head, radius=10, alpha=214, glow=False)
        avatar_r = max(12, self.scale_dim(19, 12))
        avatar_x = x + self.scale_dim(32, 22)
        avatar_y = y + self.scale_dim(28, 20)
        pygame.draw.circle(self.screen, mix_color(head, WHITE, 0.14), (avatar_x, avatar_y), avatar_r)
        pygame.draw.circle(self.screen, WHITE, (avatar_x - avatar_r // 3, avatar_y - avatar_r // 4), max(3, avatar_r // 4))
        pygame.draw.circle(self.screen, WHITE, (avatar_x + avatar_r // 3, avatar_y - avatar_r // 4), max(3, avatar_r // 4))
        pygame.draw.circle(self.screen, BLACK, (avatar_x - avatar_r // 3, avatar_y - avatar_r // 4), max(1, avatar_r // 8))
        pygame.draw.circle(self.screen, BLACK, (avatar_x + avatar_r // 3, avatar_y - avatar_r // 4), max(1, avatar_r // 8))
        pygame.draw.circle(self.screen, WHITE, (avatar_x, avatar_y), avatar_r, 1)
        name_x = x + self.scale_dim(60, 44)
        draw_text(self.screen, fit_text(player, self.med_font, card_w - (name_x - x) - self.scale_dim(12, 8)), self.med_font, head, name_x, y + self.scale_dim(16, 11))
        hp = gs.get('health', {}).get(player, 0)
        hp_y = y + self.scale_dim(54, 40)
        hp_label = f"HP {int(hp)}"
        hp_label_w = self.small_font.render(hp_label, True, WHITE).get_width()
        bar_x = x + self.scale_dim(20, 14)
        bar_w = max(70, card_w - self.scale_dim(42, 28) - hp_label_w - self.scale_dim(14, 8))
        self.draw_health_bar(bar_x, hp_y, bar_w, self.scale_dim(18, 12), hp / 160.0, head)
        draw_text(self.screen, hp_label, self.small_font, WHITE, bar_x + bar_w + self.scale_dim(8, 5), hp_y - self.scale_dim(2, 1))
        effects = gs.get('effects', {}).get(player, {})
        active = [k.replace('_until','') for k, v in effects.items() if v > time.time()]
        line_x = x + self.scale_dim(20, 14)
        line_w = card_w - self.scale_dim(40, 28)
        draw_text(self.screen, fit_text(f"Effects: {', '.join(active) if active else 'None'}", self.small_font, line_w), self.small_font, GOLD, line_x, y + self.scale_dim(84, 62))
        draw_text(self.screen, fit_text(f"{cosmetics.get('head_style','Classic')} - {cosmetics.get('trail_style','None')}", self.small_font, line_w), self.small_font, BLUE, line_x, y + self.scale_dim(104, 78))
        st = gs.get('stats', {}).get(player, {})
        lines = [
            f"Pies: {st.get('pies_eaten',0)}",
            f"Powerups: {st.get('powerups_used',0)}",
            f"Damage: {st.get('damage_taken',0)}",
            f"Collisions: {st.get('collisions',0)}",
        ]
        stat_y = y + self.scale_dim(132, 96)
        col_w = max(72, (card_w - self.scale_dim(52, 36)) // 2)
        stat_gap_y = max(18, self.scale_dim(22, 16))
        for i, line in enumerate(lines):
            sx = line_x + (i % 2) * col_w
            sy = stat_y + (i // 2) * stat_gap_y
            draw_text(self.screen, fit_text(line, self.small_font, col_w - self.scale_dim(8, 4)), self.small_font, WHITE, sx, sy)

    def draw_result(self):
        gs = self.game_state or {}
        current_ping = gs.get('your_ping', self.my_ping_ms)
        safe = self.compute_safe_rect()
        title_y = safe.y + self.scale_dim(78, 52)
        draw_center(self.screen, "MATCH COMPLETE", self.title_font, GOLD, self.window_w // 2, title_y)

        winner = gs.get('winner') or '?'
        if winner == 'Draw':
            winner_text = "Winner: Draw"
            winner_color = WHITE
        elif winner == '?':
            winner_text = "Winner: Unknown"
            winner_color = MUTED
        else:
            winner_text = f"Winner: {winner}"
            winner_color = GREEN
        draw_center(self.screen, fit_text(winner_text, self.big_font, safe.w), self.big_font, winner_color, self.window_w // 2, title_y + self.scale_dim(76, 48))

        # Player stat cards
        panel_w = min(safe.w, max(self.scale_dim(720, 420), int(safe.w * 0.72)))
        panel_h = min(max(self.scale_dim(280, 200), int(safe.h * 0.30)), max(180, safe.h - self.scale_dim(320, 220)))
        panel = pygame.Rect(safe.centerx - panel_w // 2, title_y + self.scale_dim(128, 88), panel_w, panel_h)
        draw_alpha_rect(self.screen, PANEL2, panel, 200, radius=12)
        p1, p2 = gs.get('p1', ''), gs.get('p2', '')
        card_gap = self.scale_dim(22, 12)
        card_w = max(180, (panel.w - self.scale_dim(72, 44) - card_gap) // 2)
        card_h = max(self.scale_dim(198, 150), panel.h - self.scale_dim(70, 46))
        card_y = panel.y + max(self.scale_dim(50, 34), (panel.h - card_h) // 2)
        for idx, player in enumerate([p1, p2]):
            x = panel.x + self.scale_dim(36, 22) + idx * (card_w + card_gap)
            self.draw_player_card(x, card_y, player, gs, idx, card_w, card_h)

        # Action buttons: Rematch | Back to Lobby | Exit
        self.result_buttons = []
        btn_h = max(38, self.scale_dim(52, 38))
        btn_w = max(140, self.scale_dim(180, 130))
        btn_gap = max(14, self.scale_dim(22, 14))
        total_btn_w = btn_w * 3 + btn_gap * 2
        btn_y = min(safe.bottom - btn_h - self.scale_dim(28, 18), panel.bottom + self.scale_dim(26, 18))
        btn_x0 = safe.centerx - total_btn_w // 2

        rematch_rect = pygame.Rect(btn_x0, btn_y, btn_w, btn_h)
        lobby_rect = pygame.Rect(btn_x0 + btn_w + btn_gap, btn_y, btn_w, btn_h)
        exit_rect = pygame.Rect(btn_x0 + (btn_w + btn_gap) * 2, btn_y, btn_w, btn_h)

        mouse_pos = pygame.mouse.get_pos()
        for rect, label, color, action in (
            (rematch_rect, "REMATCH", GREEN, "rematch"),
            (lobby_rect, "BACK TO LOBBY", CYAN, "lobby"),
            (exit_rect, "EXIT", RED, "exit"),
        ):
            hover = rect.collidepoint(mouse_pos)
            fill = mix_color(color, FIELD, 0.30) if hover else FIELD
            draw_neon_rect(self.screen, rect, fill, color, radius=10, alpha=235, glow=hover)
            draw_center(self.screen, label, self.small_font, WHITE if hover else color, rect.centerx, rect.centery)
            self.result_buttons.append({"action": action, "rect": rect})

        # Keyboard hint
        hint_y = min(safe.bottom - self.scale_dim(22, 16), btn_y + btn_h + self.scale_dim(12, 8))
        draw_center(self.screen, "R = Rematch   ESC = Lobby   V = View Replay", self.small_font, MUTED, self.window_w // 2, hint_y)

        meta_y = min(safe.bottom - self.scale_dim(26, 18), btn_y - self.scale_dim(26, 18))
        if meta_y > title_y:
            draw_center(self.screen, ping_label(current_ping), self.small_font, ping_color(current_ping), safe.centerx - min(self.scale_dim(160, 96), safe.w // 4), meta_y)
            draw_center(self.screen, f"Spectators {gs.get('spectators', 0)} | Tick {gs.get('tickrate', 10)} Hz", self.small_font, BLUE, safe.centerx + min(self.scale_dim(160, 96), safe.w // 4), meta_y)


if __name__ == '__main__':
    ClientApp().run()
