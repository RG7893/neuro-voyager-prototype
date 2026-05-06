import pygame
import random
import math
import serial
import threading
import time
import csv
import os
from datetime import datetime

# =========================
# CONFIG
# =========================
WIDTH, HEIGHT = 1280, 720
FPS = 60

PORT = "COM11"
BAUD = 57600

CSV_FILE = "neuro_voyager_eeg_data.csv"
HIGH_SCORE_FILE = "neuro_voyager_highscore.txt"

# =========================
# COLORS
# =========================
WHITE = (240, 240, 255)
BLACK = (10, 10, 18)
RED = (255, 80, 80)
GREEN = (90, 255, 140)
BLUE = (90, 180, 255)
YELLOW = (255, 220, 70)
CYAN = (80, 255, 255)
PURPLE = (180, 100, 255)
ORANGE = (255, 150, 60)
GRAY = (130, 130, 150)
DARK_PANEL = (18, 18, 35)
NEON = (0, 255, 180)
MAGENTA = (255, 80, 180)
SKY1 = (18, 28, 52)
SKY2 = (42, 72, 120)
SUNSET = (255, 140, 90)

# =========================
# EEG DATA STORE
# =========================
eeg_data = {
    "attention": 0,
    "meditation": 0,
    "poorSignalLevel": 200,
    "raw": 0,
    "delta": 0,
    "theta": 0,
    "lowAlpha": 0,
    "highAlpha": 0,
    "lowBeta": 0,
    "highBeta": 0,
    "lowGamma": 0,
    "midGamma": 0,
    "connected": False,
    "last_packet_time": 0,
    "has_attention": False,
    "has_meditation": False,
    "has_signal": False,
    "debug_last_line": "",
    "baseline_attention": 0,
    "baseline_meditation": 0,
    "baseline_lowBeta": 0,
    "baseline_lowGamma": 0,
    "baseline_theta": 0,
    "baseline_lowAlpha": 0,
}

running_serial = True

# =========================
# HELPERS
# =========================
def clamp(val, mn, mx):
    return max(mn, min(mx, val))

def safe_clean_text(text):
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\x00", "")
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\t")
    return text[:160]

def draw_text(screen, text, x, y, font, color=WHITE, center=False):
    try:
        clean_text = safe_clean_text(text)
        surf = font.render(clean_text, True, color)
        rect = surf.get_rect()
        if center:
            rect.center = (x, y)
            screen.blit(surf, rect)
        else:
            screen.blit(surf, (x, y))
    except:
        pass

def load_high_score():
    if os.path.exists(HIGH_SCORE_FILE):
        try:
            with open(HIGH_SCORE_FILE, "r") as f:
                return int(f.read().strip())
        except:
            return 0
    return 0

def save_high_score(score):
    with open(HIGH_SCORE_FILE, "w") as f:
        f.write(str(score))

def eeg_is_ready():
    return (
        eeg_data["connected"] and
        eeg_data["poorSignalLevel"] < 100 and
        eeg_data["attention"] > 0 and
        eeg_data["meditation"] > 0
    )

def compute_focus_score():
    numerator = eeg_data["lowBeta"] + eeg_data["highBeta"] + eeg_data["lowGamma"]
    denominator = eeg_data["theta"] + eeg_data["lowAlpha"] + 1
    score = numerator / denominator if denominator > 0 else 0
    return clamp(int(score / 1000), 0, 100)

def compute_calm_score():
    numerator = eeg_data["lowAlpha"] + eeg_data["highAlpha"] + eeg_data["theta"]
    denominator = eeg_data["lowBeta"] + eeg_data["highBeta"] + 1
    score = numerator / denominator if denominator > 0 else 0
    return clamp(int(score / 1000), 0, 100)

def gamma_ready():
    threshold = max(30000, eeg_data["baseline_lowGamma"] * 1.2 if eeg_data["baseline_lowGamma"] else 30000)
    return eeg_data["lowGamma"] > threshold or eeg_data["midGamma"] > threshold

# =========================
# CSV LOGGING
# =========================
def init_csv():
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow([
                "timestamp",
                "attention", "meditation", "poorSignalLevel",
                "raw", "delta", "theta", "lowAlpha", "highAlpha",
                "lowBeta", "highBeta", "lowGamma", "midGamma"
            ])

def log_eeg_to_csv():
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            eeg_data["attention"],
            eeg_data["meditation"],
            eeg_data["poorSignalLevel"],
            eeg_data["raw"],
            eeg_data["delta"],
            eeg_data["theta"],
            eeg_data["lowAlpha"],
            eeg_data["highAlpha"],
            eeg_data["lowBeta"],
            eeg_data["highBeta"],
            eeg_data["lowGamma"],
            eeg_data["midGamma"]
        ])

# =========================
# RAW THINKGEAR EEG READER
# =========================
def eeg_reader():
    global running_serial

    try:
        print(f"Connecting to {PORT} at {BAUD}...")
        ser = serial.Serial(PORT, BAUD, timeout=1)
        eeg_data["connected"] = True
        print("EEG connected successfully (RAW THINKGEAR MODE)!")

        last_log_time = time.time()

        while running_serial:
            try:
                if ser.read(1) != b'\xAA':
                    continue
                if ser.read(1) != b'\xAA':
                    continue

                payload_length = ser.read(1)
                if not payload_length:
                    continue

                payload_length = payload_length[0]
                if payload_length > 169:
                    continue

                payload = ser.read(payload_length)
                checksum = ser.read(1)

                if len(payload) != payload_length or len(checksum) != 1:
                    continue

                generated_checksum = 255 - (sum(payload) & 0xFF)
                if checksum[0] != generated_checksum:
                    continue

                eeg_data["last_packet_time"] = time.time()
                i = 0

                while i < len(payload):
                    code = payload[i]
                    i += 1

                    while code == 0x55 and i < len(payload):
                        code = payload[i]
                        i += 1

                    if code == 0x02 and i < len(payload):
                        eeg_data["poorSignalLevel"] = payload[i]
                        eeg_data["has_signal"] = payload[i] < 100
                        i += 1

                    elif code == 0x04 and i < len(payload):
                        val = payload[i]
                        eeg_data["attention"] = val
                        eeg_data["has_attention"] = val > 0
                        i += 1

                    elif code == 0x05 and i < len(payload):
                        val = payload[i]
                        eeg_data["meditation"] = val
                        eeg_data["has_meditation"] = val > 0
                        i += 1

                    elif code >= 0x80 and i < len(payload):
                        vlen = payload[i]
                        i += 1

                        if i + vlen > len(payload):
                            break

                        value = payload[i:i+vlen]

                        if code == 0x80 and vlen == 2:
                            raw_val = int.from_bytes(value, byteorder='big', signed=True)
                            eeg_data["raw"] = raw_val

                        elif code == 0x83 and vlen == 24:
                            bands = []
                            for j in range(0, 24, 3):
                                band = (value[j] << 16) | (value[j+1] << 8) | value[j+2]
                                bands.append(band)

                            if len(bands) == 8:
                                eeg_data["delta"] = bands[0]
                                eeg_data["theta"] = bands[1]
                                eeg_data["lowAlpha"] = bands[2]
                                eeg_data["highAlpha"] = bands[3]
                                eeg_data["lowBeta"] = bands[4]
                                eeg_data["highBeta"] = bands[5]
                                eeg_data["lowGamma"] = bands[6]
                                eeg_data["midGamma"] = bands[7]

                        i += vlen

                eeg_data["debug_last_line"] = (
                    f"ATT={eeg_data['attention']} "
                    f"MED={eeg_data['meditation']} "
                    f"SIG={eeg_data['poorSignalLevel']} "
                    f"LG={eeg_data['lowGamma']} "
                    f"MG={eeg_data['midGamma']}"
                )

                print(
                    f"ATT={eeg_data['attention']} | "
                    f"MED={eeg_data['meditation']} | "
                    f"SIG={eeg_data['poorSignalLevel']} | "
                    f"LG={eeg_data['lowGamma']} | "
                    f"MG={eeg_data['midGamma']}"
                )

                if time.time() - last_log_time >= 1:
                    log_eeg_to_csv()
                    last_log_time = time.time()

            except Exception as e:
                print("EEG read error:", e)

        ser.close()

    except Exception as e:
        print("Could not connect to EEG device:", e)
        eeg_data["connected"] = False

# =========================
# PARTICLES
# =========================
class Particle:
    def __init__(self, x, y, color, size=None, life=None):
        self.x = x
        self.y = y
        self.radius = size if size else random.randint(2, 5)
        self.life = life if life else random.randint(20, 45)
        self.vx = random.uniform(-2.5, 2.5)
        self.vy = random.uniform(-2.5, 2.5)
        self.color = color

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        self.radius = max(1, self.radius - 0.04)

    def draw(self, screen):
        if self.life > 0:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), int(self.radius))

# =========================
# PLAYER SHIP
# =========================
class PlayerShip:
    def __init__(self):
        self.x = 160
        self.y = HEIGHT // 2
        self.vx = 0
        self.vy = 0
        self.w = 88
        self.h = 42
        self.base_speed = 3.2
        self.health = 3
        self.energy = 100
        self.shield_timer = 0
        self.burst_timer = 0
        self.burst_cooldown = 0
        self.trail = []

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.w//2), int(self.y - self.h//2), self.w, self.h)

    def activate_burst(self, particles):
        if self.burst_cooldown <= 0 and self.energy >= 25:
            self.burst_timer = 160
            self.burst_cooldown = 220
            self.energy -= 25
            for _ in range(24):
                particles.append(Particle(self.x, self.y, MAGENTA, size=4))

    def update(self, keys, particles):
        att = eeg_data["attention"]
        med = eeg_data["meditation"]

        move_x = 0
        move_y = 0

        if keys[pygame.K_UP] or keys[pygame.K_w]:
            move_y -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            move_y += 1
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_x -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_x += 1

        # EEG CONTROL
        if att > 45:
            move_x += 0.6
        if att > 65:
            move_x += 0.5
            move_y -= 0.2

        if med > 45:
            move_y -= 0.35
        if med > 65:
            move_y -= 0.45

        if med < 35:
            move_y += 0.25

        speed = 3.2 + (att / 100.0) * 1.6

        self.vx = move_x * speed
        self.vy = move_y * speed

        self.x += self.vx + 0.35
        self.y += self.vy

        if gamma_ready() and self.burst_cooldown <= 0:
            self.activate_burst(particles)

        if self.burst_timer > 0:
            self.burst_timer -= 1
            self.energy = clamp(self.energy - 0.04, 0, 100)
            for _ in range(2):
                particles.append(Particle(self.x - 30, self.y, MAGENTA, size=3))

        if self.shield_timer > 0:
            self.shield_timer -= 1
        if self.burst_cooldown > 0:
            self.burst_cooldown -= 1

        if med > 55:
            self.energy = clamp(self.energy + 0.08, 0, 100)

        self.x = clamp(self.x, 80, WIDTH - 160)
        self.y = clamp(self.y, 130, HEIGHT - 90)

        self.trail.append((self.x - 25, self.y))
        if len(self.trail) > 12:
            self.trail.pop(0)

    def draw(self, screen):
        for i, pos in enumerate(self.trail):
            pygame.draw.circle(screen, CYAN, (int(pos[0]), int(pos[1])), max(2, i//2 + 2), 1)

        if self.shield_timer > 0:
            pygame.draw.circle(screen, BLUE, (int(self.x), int(self.y)), 48, 3)
        if self.burst_timer > 0:
            pygame.draw.circle(screen, MAGENTA, (int(self.x), int(self.y)), 56, 3)

        pygame.draw.polygon(screen, CYAN, [
            (self.x - 36, self.y),
            (self.x + 20, self.y - 18),
            (self.x + 38, self.y),
            (self.x + 20, self.y + 18),
        ])

        pygame.draw.polygon(screen, WHITE, [
            (self.x - 10, self.y),
            (self.x + 10, self.y - 10),
            (self.x + 18, self.y),
            (self.x + 10, self.y + 10),
        ])

        pygame.draw.polygon(screen, PURPLE, [
            (self.x - 12, self.y - 6),
            (self.x - 34, self.y - 26),
            (self.x + 6, self.y - 10),
        ])
        pygame.draw.polygon(screen, PURPLE, [
            (self.x - 12, self.y + 6),
            (self.x - 34, self.y + 26),
            (self.x + 6, self.y + 10),
        ])

        pygame.draw.circle(screen, ORANGE, (int(self.x - 34), int(self.y)), 6)

# =========================
# OBSTACLES / ENEMIES
# =========================
class Barrier:
    def __init__(self, x, y, w=90, h=90, kind="meteor"):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.kind = kind
        self.angle = random.randint(0, 360)
        self.spin = random.uniform(-3, 3)

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def update(self, scroll_speed):
        self.x -= scroll_speed
        self.angle += self.spin

    def draw(self, screen):
        cx = int(self.x + self.w // 2)
        cy = int(self.y + self.h // 2)

        if self.kind == "meteor":
            pygame.draw.circle(screen, ORANGE, (cx, cy), self.w // 2)
            pygame.draw.circle(screen, RED, (cx - 10, cy - 8), self.w // 6)
            pygame.draw.circle(screen, (255, 200, 120), (cx + 12, cy + 6), self.w // 8)
            pygame.draw.circle(screen, WHITE, (cx, cy), self.w // 2, 2)

        elif self.kind == "planet":
            pygame.draw.circle(screen, PURPLE, (cx, cy), self.w // 2)
            pygame.draw.circle(screen, BLUE, (cx - 8, cy + 6), self.w // 5)
            pygame.draw.circle(screen, WHITE, (cx, cy), self.w // 2, 2)

        elif self.kind == "plasma":
            pygame.draw.circle(screen, CYAN, (cx, cy), self.w // 2)
            pygame.draw.circle(screen, WHITE, (cx, cy), self.w // 3, 2)

        elif self.kind == "debris":
            pts = [
                (cx - 24, cy),
                (cx - 10, cy - 18),
                (cx + 18, cy - 8),
                (cx + 26, cy + 10),
                (cx, cy + 24),
                (cx - 20, cy + 12)
            ]
            pygame.draw.polygon(screen, GRAY, pts)
            pygame.draw.polygon(screen, WHITE, pts, 2)

class Drone:
    def __init__(self, x, y):
        self.x = x
        self.base_y = y
        self.y = y
        self.w = 64
        self.h = 34
        self.t = random.random() * 10

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def update(self, scroll_speed):
        self.x -= scroll_speed + 0.8
        self.t += 0.05
        self.y = self.base_y + math.sin(self.t) * 18

    def draw(self, screen):
        pygame.draw.ellipse(screen, PURPLE, self.rect)
        pygame.draw.ellipse(screen, WHITE, self.rect, 2)
        pygame.draw.circle(screen, RED, (int(self.x + self.w//2), int(self.y + self.h//2)), 5)
        pygame.draw.line(screen, CYAN, (self.x + 8, self.y + self.h//2), (self.x + self.w - 8, self.y + self.h//2), 2)

class Pickup:
    def __init__(self, x, y, kind="energy"):
        self.x = x
        self.y = y
        self.kind = kind
        self.size = 28

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.size, self.size)

    def update(self, scroll_speed):
        self.x -= scroll_speed

    def draw(self, screen):
        color = BLUE if self.kind == "shield" else GREEN if self.kind == "heal" else PURPLE
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, WHITE, self.rect, 2, border_radius=8)

# =========================
# LEVEL DATA
# =========================
LEVELS = [
    {
        "name": "Mountain Outpost",
        "theme": "mountains",
        "story_before": [
            "Year 2091. The Neural Grid is collapsing.",
            "You are the only pilot linked to the experimental EEG interface.",
            "Escape the mountain sector before the first cascade begins."
        ],
        "story_mid": [
            "Hostile aerial debris has entered the corridor.",
            "Stay alive and clear the sector."
        ],
        "objective": "Survive and clear 18 obstacles.",
        "clear_target": 18
    },
    {
        "name": "Ruined City",
        "theme": "city",
        "story_before": [
            "The mountain sector is behind you.",
            "Now the city ruins are filled with rogue drones and meteor fragments."
        ],
        "story_mid": [
            "The city corridor is unstable.",
            "Clear the hostile airspace and survive."
        ],
        "objective": "Survive and clear 24 obstacles.",
        "clear_target": 24
    },
    {
        "name": "Core Reactor",
        "theme": "reactor",
        "story_before": [
            "You have reached the reactor basin.",
            "Everything is collapsing into neural fire."
        ],
        "story_mid": [
            "This is the final escape corridor.",
            "One last survival run."
        ],
        "objective": "Survive and clear 30 obstacles.",
        "clear_target": 30
    }
]

# =========================
# BACKGROUNDS
# =========================
def draw_gradient(screen, top_color, bottom_color):
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = (
            int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio),
            int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio),
            int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        )
        pygame.draw.line(screen, color, (0, y), (WIDTH, y))

def draw_stars(screen):
    random.seed(42)
    for _ in range(50):
        x = random.randint(0, WIDTH)
        y = random.randint(0, 240)
        if random.random() > 0.7:
            pygame.draw.circle(screen, WHITE, (x, y), 1)

def draw_mountains(screen, scroll):
    points = []
    for x in range(-100, WIDTH + 120, 80):
        y = 330 + int(math.sin((x + scroll*0.25) * 0.01) * 50)
        points.append((x, y))
    points += [(WIDTH, HEIGHT), (0, HEIGHT)]
    pygame.draw.polygon(screen, (38, 52, 78), points)

    points2 = []
    for x in range(-100, WIDTH + 120, 60):
        y = 430 + int(math.sin((x + scroll*0.45) * 0.015) * 70)
        points2.append((x, y))
    points2 += [(WIDTH, HEIGHT), (0, HEIGHT)]
    pygame.draw.polygon(screen, (22, 30, 50), points2)

def draw_city(screen, scroll):
    pygame.draw.rect(screen, (18, 22, 38), (0, 460, WIDTH, HEIGHT - 460))
    for i in range(18):
        x = (i * 90 - int(scroll * 0.4) % 90)
        w = random.choice([50, 60, 70])
        h = random.choice([140, 180, 220, 260])
        pygame.draw.rect(screen, (30, 38, 62), (x, 460 - h, w, h))
        for wy in range(460 - h + 10, 460, 18):
            for wx in range(x + 8, x + w - 8, 16):
                pygame.draw.rect(screen, CYAN if (wx + wy) % 2 == 0 else PURPLE, (wx, wy, 6, 8))

def draw_reactor(screen, scroll):
    pygame.draw.rect(screen, (22, 12, 18), (0, 440, WIDTH, HEIGHT - 440))
    for i in range(12):
        x = (i * 120 - int(scroll * 0.5) % 120)
        w = 80
        h = 220 + (i % 3) * 50
        pygame.draw.rect(screen, (55, 22, 30), (x, 440 - h, w, h))
        pygame.draw.line(screen, RED, (x + 10, 440 - h + 20), (x + w - 10, 440 - h + 20), 2)
        pygame.draw.line(screen, ORANGE, (x + 10, 440 - h + 50), (x + w - 10, 440 - h + 50), 2)
        pygame.draw.circle(screen, MAGENTA, (x + w//2, 440 - h + 12), 6)

def draw_ground(screen, scroll, theme):
    ground_y = HEIGHT - 70
    pygame.draw.rect(screen, (18, 18, 28), (0, ground_y, WIDTH, HEIGHT-ground_y))
    for x in range(-40, WIDTH + 40, 40):
        color = CYAN if theme != "reactor" else RED
        pygame.draw.line(screen, color,
                         (x - int(scroll) % 40, ground_y),
                         (x + 20 - int(scroll) % 40, ground_y - 14), 2)
        pygame.draw.line(screen, color,
                         (x + 20 - int(scroll) % 40, ground_y - 14),
                         (x + 40 - int(scroll) % 40, ground_y), 2)

def draw_background(screen, tick, theme, scroll):
    if theme == "mountains":
        draw_gradient(screen, SKY1, SKY2)
        pygame.draw.circle(screen, SUNSET, (980, 130), 70)
        draw_stars(screen)
        draw_mountains(screen, scroll)
    elif theme == "city":
        draw_gradient(screen, (10, 14, 28), (28, 22, 48))
        draw_stars(screen)
        draw_city(screen, scroll)
    elif theme == "reactor":
        draw_gradient(screen, (26, 8, 14), (70, 18, 24))
        draw_reactor(screen, scroll)

    for x in range(-60, WIDTH + 60, 80):
        pygame.draw.line(screen, (28, 36, 52), (x - int(scroll*0.2) % 80, 110), (x - int(scroll*0.2) % 80, HEIGHT - 70), 1)
    for y in range(110, HEIGHT - 70, 50):
        pygame.draw.line(screen, (24, 30, 44), (0, y), (WIDTH, y), 1)

    draw_ground(screen, scroll, theme)

# =========================
# UI
# =========================
def draw_bar(screen, x, y, w, h, value, max_value, color, bg=(70, 70, 90), segments=10):
    pygame.draw.rect(screen, (25, 25, 40), (x - 2, y - 2, w + 4, h + 4), border_radius=8)
    pygame.draw.rect(screen, bg, (x, y, w, h), border_radius=8)

    ratio = clamp(value / max_value if max_value > 0 else 0, 0, 1)
    fill_w = int(w * ratio)

    segment_gap = 3
    segment_w = (w - (segments - 1) * segment_gap) / segments

    for i in range(segments):
        sx = x + i * (segment_w + segment_gap)
        if sx + segment_w <= x + fill_w:
            pygame.draw.rect(screen, color, (sx, y, segment_w, h), border_radius=6)
        else:
            pygame.draw.rect(screen, (100, 100, 120), (sx, y, segment_w, h), border_radius=6)

    pygame.draw.rect(screen, (220, 220, 255), (x, y, w, h), 1, border_radius=8)

def draw_hud(screen, fonts, player, level_data, cleared_count, score):
    title_font, hud_font, small_font = fonts

    pygame.draw.rect(screen, DARK_PANEL, (0, 0, WIDTH, 95))
    pygame.draw.line(screen, (40, 60, 100), (0, 95), (WIDTH, 95), 2)

    draw_text(screen, "NEURO VOYAGER", 30, 18, title_font, CYAN)
    draw_text(screen, f"Sector: {level_data['name']}", 420, 22, hud_font, WHITE)
    draw_text(screen, f"Objective: {level_data['objective']}", 420, 55, small_font, YELLOW)
    draw_text(screen, f"Score: {score}", WIDTH - 220, 20, hud_font, YELLOW)

    panel_x = 20
    panel_y = HEIGHT - 180
    pygame.draw.rect(screen, (10, 30, 60), (panel_x - 4, panel_y - 4, 428, 158), border_radius=18)
    pygame.draw.rect(screen, (14, 16, 32), (panel_x, panel_y, 420, 150), border_radius=18)
    pygame.draw.rect(screen, (60, 120, 220), (panel_x, panel_y, 420, 150), 2, border_radius=18)
    pygame.draw.line(screen, (40, 80, 160), (panel_x + 15, panel_y + 42), (panel_x + 405, panel_y + 42), 1)

    draw_text(screen, "SHIP SYSTEMS", panel_x + 18, panel_y + 12, hud_font, CYAN)
    draw_text(screen, "Health", panel_x + 18, panel_y + 52, small_font, WHITE)
    draw_bar(screen, panel_x + 110, panel_y + 56, 220, 16, player.health, 3, RED)

    draw_text(screen, "Energy", panel_x + 18, panel_y + 82, small_font, WHITE)
    draw_bar(screen, panel_x + 110, panel_y + 86, 220, 16, player.energy, 100, PURPLE)

    draw_text(screen, "Burst", panel_x + 18, panel_y + 112, small_font, WHITE)
    draw_bar(screen, panel_x + 110, panel_y + 116, 220, 16,
             160 - player.burst_cooldown if player.burst_cooldown < 160 else 0, 160, MAGENTA)

    eeg_x = 470
    eeg_y = HEIGHT - 180
    pygame.draw.rect(screen, (10, 30, 60), (eeg_x - 4, eeg_y - 4, 798, 158), border_radius=18)
    pygame.draw.rect(screen, (14, 16, 32), (eeg_x, eeg_y, 790, 150), border_radius=18)
    pygame.draw.rect(screen, (60, 120, 220), (eeg_x, eeg_y, 790, 150), 2, border_radius=18)
    pygame.draw.line(screen, (40, 80, 160), (eeg_x + 15, eeg_y + 42), (eeg_x + 775, eeg_y + 42), 1)

    att = eeg_data["attention"]
    med = eeg_data["meditation"]
    focus = compute_focus_score()
    calm = compute_calm_score()
    signal = eeg_data["poorSignalLevel"]

    draw_text(screen, "EEG NAVIGATION SYSTEM", eeg_x + 18, eeg_y + 12, hud_font, CYAN)

    draw_text(screen, f"Attention: {att}", eeg_x + 18, eeg_y + 50, small_font, WHITE)
    draw_bar(screen, eeg_x + 140, eeg_y + 54, 180, 14, att, 100, YELLOW)

    draw_text(screen, f"Meditation: {med}", eeg_x + 18, eeg_y + 80, small_font, WHITE)
    draw_bar(screen, eeg_x + 140, eeg_y + 84, 180, 14, med, 100, GREEN)

    draw_text(screen, f"Focus: {focus}", eeg_x + 360, eeg_y + 50, small_font, WHITE)
    draw_bar(screen, eeg_x + 460, eeg_y + 54, 160, 14, focus, 100, ORANGE)

    draw_text(screen, f"Calm: {calm}", eeg_x + 360, eeg_y + 80, small_font, WHITE)
    draw_bar(screen, eeg_x + 460, eeg_y + 84, 160, 14, calm, 100, BLUE)

    draw_text(screen, f"Low Gamma: {eeg_data['lowGamma']}", eeg_x + 650, eeg_y + 50, small_font, WHITE)
    draw_text(screen, f"Signal: {signal}", eeg_x + 650, eeg_y + 80, small_font,
              GREEN if signal < 100 else RED)

    draw_text(screen, f"Cleared: {cleared_count}/{level_data['clear_target']}", eeg_x + 18, eeg_y + 116, small_font, YELLOW)
    draw_text(screen, "Survive the corridor", eeg_x + 250, eeg_y + 116, small_font, CYAN)

# =========================
# STORY / TUTORIAL
# =========================
def tutorial_screen(screen, fonts):
    title_font, hud_font, small_font = fonts
    clock = pygame.time.Clock()

    pages = [
        {
            "title": "TUTORIAL 1 / 4",
            "lines": [
                "Welcome to NEURO VOYAGER.",
                "You are piloting a neural ship using EEG signals.",
                "",
                "Keyboard fallback:",
                "W / UP = move up",
                "S / DOWN = move down",
                "A / LEFT = move left",
                "D / RIGHT = move right",
                "SPACE = Mind Burst"
            ]
        },
        {
            "title": "TUTORIAL 2 / 4",
            "lines": [
                "EEG Controls:",
                "",
                "Attention → thrust / forward momentum",
                "Meditation → stability / hover control",
                "Gamma spike → Mind Burst attack",
                "",
                "Better signal = better gameplay"
            ]
        },
        {
            "title": "TUTORIAL 3 / 4",
            "lines": [
                "Mission Rules:",
                "",
                "Survive the corridor.",
                "Avoid meteors, UFOs, debris and plasma orbs.",
                "Pick up shield / heal / energy boxes.",
                "",
                "Destroy or outlast enough obstacles to clear the sector."
            ]
        },
        {
            "title": "TUTORIAL 4 / 4",
            "lines": [
                "HUD Guide:",
                "",
                "Left Panel = Ship Systems",
                "Right Panel = EEG Brain Metrics",
                "",
                "Goal:",
                "Complete each sector before losing all health.",
                "",
                "Press ENTER to begin your journey."
            ]
        }
    ]

    page = 0

    while True:
        draw_gradient(screen, (8, 10, 20), (20, 28, 44))
        draw_mountains(screen, pygame.time.get_ticks() * 0.15)
        draw_ground(screen, pygame.time.get_ticks() * 0.2, "mountains")

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        box = pygame.Rect(180, 120, WIDTH - 360, HEIGHT - 220)
        pygame.draw.rect(screen, (18, 18, 35), box, border_radius=20)
        pygame.draw.rect(screen, CYAN, box, 2, border_radius=20)

        draw_text(screen, pages[page]["title"], WIDTH // 2, 170, title_font, CYAN, center=True)

        y = 250
        for line in pages[page]["lines"]:
            draw_text(screen, line, WIDTH // 2, y, hud_font if line and ":" in line else small_font, WHITE, center=True)
            y += 42

        draw_text(screen, "← / → to navigate    |    ENTER to continue    |    ESC to skip",
                  WIDTH // 2, HEIGHT - 90, small_font, GRAY, center=True)

        pygame.display.flip()
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RIGHT:
                    page = min(len(pages) - 1, page + 1)
                elif event.key == pygame.K_LEFT:
                    page = max(0, page - 1)
                elif event.key == pygame.K_RETURN:
                    if page == len(pages) - 1:
                        return True
                    page += 1
                elif event.key == pygame.K_ESCAPE:
                    return True

def cinematic_story(screen, fonts, lines, title="STORY"):
    title_font, hud_font, small_font = fonts
    clock = pygame.time.Clock()
    index = 0
    reveal_timer = 0

    while True:
        screen.fill(BLACK)
        draw_gradient(screen, (8, 10, 20), (22, 30, 48))
        draw_text(screen, title, WIDTH // 2, 120, title_font, CYAN, center=True)

        y = 230
        for i in range(index):
            draw_text(screen, lines[i], WIDTH // 2, y, hud_font, WHITE, center=True)
            y += 70

        if index < len(lines):
            current = lines[index]
            chars = min(len(current), reveal_timer // 2)
            draw_text(screen, current[:chars], WIDTH // 2, y, hud_font, WHITE, center=True)

        draw_text(screen, "Press ENTER to continue", WIDTH // 2, 650, small_font, GRAY, center=True)

        pygame.display.flip()
        clock.tick(60)
        reveal_timer += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if index < len(lines) - 1:
                        index += 1
                        reveal_timer = 0
                    else:
                        return True
                if event.key == pygame.K_ESCAPE:
                    return False

def eeg_wait_screen(screen, fonts):
    title_font, hud_font, small_font = fonts
    clock = pygame.time.Clock()

    timeout_seconds = 30
    start_time = time.time()

    while True:
        screen.fill(BLACK)
        draw_gradient(screen, (8, 10, 20), (22, 30, 48))

        elapsed = int(time.time() - start_time)
        remaining = max(0, timeout_seconds - elapsed)

        draw_text(screen, "EEG LINK INITIALIZATION", WIDTH // 2, 140, title_font, CYAN, center=True)
        draw_text(screen, "Establishing neural sync with the pilot...", WIDTH // 2, 200, hud_font, WHITE, center=True)

        att = eeg_data["attention"]
        med = eeg_data["meditation"]
        signal = eeg_data["poorSignalLevel"]

        draw_text(screen, f"Attention: {att}", WIDTH // 2, 300, hud_font, YELLOW, center=True)
        draw_text(screen, f"Meditation: {med}", WIDTH // 2, 345, hud_font, GREEN, center=True)
        draw_text(screen, f"Low Gamma: {eeg_data['lowGamma']}", WIDTH // 2, 390, hud_font, MAGENTA, center=True)
        draw_text(screen, f"Signal: {signal}", WIDTH // 2, 435, hud_font,
                  GREEN if signal < 100 else RED, center=True)

        cond1 = "Signal OK" if eeg_data["has_signal"] else "Poor Signal"
        cond2 = "Attention Detected" if eeg_data["has_attention"] else "No Attention Yet"
        cond3 = "Meditation Detected" if eeg_data["has_meditation"] else "No Meditation Yet"

        draw_text(screen, cond1, WIDTH // 2, 500, small_font,
                  GREEN if eeg_data["has_signal"] else RED, center=True)
        draw_text(screen, cond2, WIDTH // 2, 535, small_font,
                  GREEN if eeg_data["has_attention"] else RED, center=True)
        draw_text(screen, cond3, WIDTH // 2, 570, small_font,
                  GREEN if eeg_data["has_meditation"] else RED, center=True)

        if eeg_is_ready():
            draw_text(screen, "NEURAL LINK STABLE", WIDTH // 2, 635, hud_font, GREEN, center=True)
            pygame.display.flip()
            pygame.time.delay(1200)
            return True

        draw_text(screen, f"Auto fallback in {remaining}s", WIDTH // 2, 635, small_font, GRAY, center=True)
        draw_text(screen, "Press SPACE to force start (debug mode)", WIDTH // 2, 670, small_font, ORANGE, center=True)

        debug_line = safe_clean_text(eeg_data["debug_last_line"])
        draw_text(screen, f"Debug Packet: {debug_line}", WIDTH // 2, 705, pygame.font.SysFont("Arial", 16), GRAY, center=True)

        pygame.display.flip()
        clock.tick(60)

        if elapsed >= timeout_seconds:
            print("EEG timeout reached. Starting anyway...")
            return True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    return True
                if event.key == pygame.K_ESCAPE:
                    return False

def calibration_screen(screen, fonts):
    title_font, hud_font, small_font = fonts
    clock = pygame.time.Clock()

    duration = 8
    start_time = time.time()

    samples = {
        "attention": [],
        "meditation": [],
        "lowBeta": [],
        "lowGamma": [],
        "theta": [],
        "lowAlpha": []
    }

    while True:
        elapsed = time.time() - start_time
        remaining = max(0, duration - int(elapsed))

        screen.fill(BLACK)
        draw_gradient(screen, (8, 10, 20), (22, 30, 48))

        draw_text(screen, "CALIBRATION", WIDTH // 2, 150, title_font, CYAN, center=True)
        draw_text(screen, "Stay still. Breathe normally. Let the system learn your baseline.", WIDTH // 2, 220, hud_font, WHITE, center=True)

        draw_text(screen, f"Attention: {eeg_data['attention']}", WIDTH // 2, 320, hud_font, YELLOW, center=True)
        draw_text(screen, f"Meditation: {eeg_data['meditation']}", WIDTH // 2, 365, hud_font, GREEN, center=True)
        draw_text(screen, f"Low Beta: {eeg_data['lowBeta']}", WIDTH // 2, 410, small_font, WHITE, center=True)
        draw_text(screen, f"Low Gamma: {eeg_data['lowGamma']}", WIDTH // 2, 445, small_font, WHITE, center=True)
        draw_text(screen, f"Signal: {eeg_data['poorSignalLevel']}", WIDTH // 2, 480, hud_font,
                  GREEN if eeg_data["poorSignalLevel"] < 100 else RED, center=True)

        if eeg_is_ready():
            samples["attention"].append(eeg_data["attention"])
            samples["meditation"].append(eeg_data["meditation"])
            samples["lowBeta"].append(eeg_data["lowBeta"])
            samples["lowGamma"].append(eeg_data["lowGamma"])
            samples["theta"].append(eeg_data["theta"])
            samples["lowAlpha"].append(eeg_data["lowAlpha"])

        draw_text(screen, f"Calibrating... {remaining}s", WIDTH // 2, 580, hud_font, WHITE, center=True)
        draw_text(screen, "Press SPACE to skip calibration", WIDTH // 2, 640, small_font, ORANGE, center=True)

        pygame.display.flip()
        clock.tick(60)

        if elapsed >= duration:
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    break
                if event.key == pygame.K_ESCAPE:
                    return False

    if len(samples["attention"]) > 0:
        eeg_data["baseline_attention"] = sum(samples["attention"]) / len(samples["attention"])
        eeg_data["baseline_meditation"] = sum(samples["meditation"]) / len(samples["meditation"])
        eeg_data["baseline_lowBeta"] = sum(samples["lowBeta"]) / len(samples["lowBeta"])
        eeg_data["baseline_lowGamma"] = sum(samples["lowGamma"]) / len(samples["lowGamma"])
        eeg_data["baseline_theta"] = sum(samples["theta"]) / len(samples["theta"])
        eeg_data["baseline_lowAlpha"] = sum(samples["lowAlpha"]) / len(samples["lowAlpha"])

    return True

def game_over_screen(screen, fonts, score, level_name):
    title_font, hud_font, small_font = fonts
    clock = pygame.time.Clock()
    high = load_high_score()
    if score > high:
        save_high_score(score)
        high = score

    while True:
        screen.fill(BLACK)
        draw_gradient(screen, (12, 6, 12), (34, 12, 20))
        draw_text(screen, "MISSION FAILED", WIDTH // 2, 180, title_font, RED, center=True)
        draw_text(screen, f"Sector lost: {level_name}", WIDTH // 2, 280, hud_font, WHITE, center=True)
        draw_text(screen, f"Final Score: {score}", WIDTH // 2, 340, hud_font, YELLOW, center=True)
        draw_text(screen, f"High Score: {high}", WIDTH // 2, 390, hud_font, CYAN, center=True)
        draw_text(screen, "Press R to Restart", WIDTH // 2, 520, hud_font, GREEN, center=True)
        draw_text(screen, "Press ESC to Quit", WIDTH // 2, 565, small_font, GRAY, center=True)

        pygame.display.flip()
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return True
                if event.key == pygame.K_ESCAPE:
                    return False

def mission_complete_screen(screen, fonts, level_data, score):
    title_font, hud_font, small_font = fonts
    clock = pygame.time.Clock()
    start = time.time()

    while time.time() - start < 2.2:
        screen.fill(BLACK)
        draw_gradient(screen, (6, 12, 18), (12, 24, 36))
        draw_text(screen, "MISSION COMPLETE", WIDTH // 2, 220, title_font, GREEN, center=True)
        draw_text(screen, f"{level_data['name']} cleared", WIDTH // 2, 310, hud_font, WHITE, center=True)
        draw_text(screen, f"Score: {score}", WIDTH // 2, 370, hud_font, YELLOW, center=True)
        draw_text(screen, "Proceeding to next sector...", WIDTH // 2, 470, small_font, CYAN, center=True)

        pygame.display.flip()
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
    return True

# =========================
# GAMEPLAY
# =========================
def play_level(screen, fonts, level_index):
    level = LEVELS[level_index]
    player = PlayerShip()
    particles = []

    barriers = []
    drones = []
    pickups = []

    score = 0
    cleared_count = 0
    target_clear = level["clear_target"]

    scroll = 0
    clock = pygame.time.Clock()
    tick = 0
    paused = False

    spawn_cooldown = 0
    pickup_cooldown = 0

    while True:
        dt = clock.tick(FPS) / 1000.0
        tick += 2

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, score
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None, score
                if event.key == pygame.K_p:
                    paused = not paused
                if event.key == pygame.K_SPACE:
                    player.activate_burst(particles)

        keys = pygame.key.get_pressed()

        if paused:
            draw_background(screen, tick, level["theme"], scroll)
            draw_text(screen, "PAUSED", WIDTH // 2, HEIGHT // 2, fonts[0], YELLOW, center=True)
            draw_text(screen, "Press P to Resume", WIDTH // 2, HEIGHT // 2 + 70, fonts[1], WHITE, center=True)
            pygame.display.flip()
            continue

        player.update(keys, particles)

        attention_drive = eeg_data["attention"] / 100.0
        scroll_speed = 2.4 + attention_drive * 1.8 + (compute_focus_score() / 140.0)
        scroll += scroll_speed

        spawn_cooldown -= dt
        pickup_cooldown -= dt

        # CONTINUOUS OBSTACLE SPAWNING
        if spawn_cooldown <= 0:
            far_x = WIDTH + random.randint(80, 220)
            spawn_type = random.choice(["meteor", "planet", "plasma", "debris", "drone"])

            if spawn_type == "drone":
                drones.append(Drone(far_x, random.randint(180, HEIGHT - 180)))
            else:
                size = random.randint(50, 90)
                barriers.append(Barrier(
                    far_x,
                    random.randint(150, HEIGHT - 180),
                    w=size,
                    h=size,
                    kind=spawn_type
                ))

            spawn_cooldown = random.uniform(0.9, 1.4)

        if pickup_cooldown <= 0 and random.random() < 0.5:
            pickups.append(Pickup(
                WIDTH + random.randint(120, 280),
                random.randint(170, HEIGHT - 160),
                kind=random.choice(["energy", "shield", "heal"])
            ))
            pickup_cooldown = random.uniform(4.5, 7.0)

        for b in barriers:
            b.update(scroll_speed)
        for d in drones:
            d.update(scroll_speed)
        for p in pickups:
            p.update(scroll_speed)

        for particle in particles[:]:
            particle.update()
            if particle.life <= 0:
                particles.remove(particle)

        for p in pickups[:]:
            if player.rect.colliderect(p.rect):
                if p.kind == "shield":
                    player.shield_timer = 220
                elif p.kind == "heal":
                    player.health = clamp(player.health + 1, 0, 3)
                elif p.kind == "energy":
                    player.energy = clamp(player.energy + 28, 0, 100)
                for _ in range(10):
                    particles.append(Particle(p.x, p.y, GREEN))
                pickups.remove(p)

        for b in barriers[:]:
            if b.x + b.w < -50:
                cleared_count += 1
                score += 60
                barriers.remove(b)
                continue

            if player.rect.colliderect(b.rect):
                if player.burst_timer > 0:
                    score += 100
                    cleared_count += 1
                    for _ in range(16):
                        particles.append(Particle(b.x + b.w/2, b.y + b.h/2, MAGENTA))
                    barriers.remove(b)
                    continue

                if player.shield_timer > 0:
                    cleared_count += 1
                    barriers.remove(b)
                    for _ in range(12):
                        particles.append(Particle(b.x + b.w/2, b.y + b.h/2, BLUE))
                    continue

                player.health -= 1
                player.shield_timer = 90
                for _ in range(18):
                    particles.append(Particle(player.x, player.y, RED))
                barriers.remove(b)

                if player.health <= 0:
                    return "fail", score

        for d in drones[:]:
            if d.x + d.w < -50:
                cleared_count += 1
                score += 80
                drones.remove(d)
                continue

            if player.rect.colliderect(d.rect):
                if player.burst_timer > 0 or player.shield_timer > 0:
                    score += 120
                    cleared_count += 1
                    for _ in range(14):
                        particles.append(Particle(d.x + d.w/2, d.y + d.h/2, MAGENTA))
                    drones.remove(d)
                    continue

                player.health -= 1
                player.shield_timer = 90
                for _ in range(18):
                    particles.append(Particle(player.x, player.y, RED))
                drones.remove(d)

                if player.health <= 0:
                    return "fail", score

        if cleared_count >= target_clear:
            return "complete", score + 500

        score += int(1 + scroll_speed * 0.15)

        draw_background(screen, tick, level["theme"], scroll)

        for p in pickups:
            p.draw(screen)
        for b in barriers:
            b.draw(screen)
        for d in drones:
            d.draw(screen)
        for particle in particles:
            particle.draw(screen)

        player.draw(screen)
        draw_hud(screen, fonts, player, level, cleared_count, score)

        pygame.display.flip()

# =========================
# MENU
# =========================
def start_menu(screen, fonts):
    title_font, hud_font, small_font = fonts
    clock = pygame.time.Clock()

    selected = 0
    options = ["Start Journey", "Calibration", "Quit"]

    while True:
        draw_gradient(screen, SKY1, SKY2)
        draw_mountains(screen, pygame.time.get_ticks() * 0.15)
        draw_ground(screen, pygame.time.get_ticks() * 0.2, "mountains")

        draw_text(screen, "NEURO VOYAGER", WIDTH // 2, 160, title_font, CYAN, center=True)
        draw_text(screen, "A Story-Driven EEG Adventure", WIDTH // 2, 220, hud_font, WHITE, center=True)

        draw_text(screen, "Use your mind to pilot through a collapsing neural world.", WIDTH // 2, 300, small_font, YELLOW, center=True)
        draw_text(screen, "Attention powers thrust. Meditation stabilizes flight. Gamma triggers Mind Burst.", WIDTH // 2, 335, small_font, WHITE, center=True)

        for idx, option in enumerate(options):
            color = GREEN if idx == selected else GRAY
            draw_text(screen, option, WIDTH // 2, 500 + idx * 45, hud_font if idx == selected else small_font, color, center=True)

        draw_text(screen, "Use ↑ ↓ and ENTER", WIDTH // 2, 680, small_font, GRAY, center=True)

        pygame.display.flip()
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % len(options)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(options)
                elif event.key == pygame.K_RETURN:
                    return options[selected].lower().replace(" ", "_")
                elif event.key == pygame.K_ESCAPE:
                    return "quit"

# =========================
# MAIN FLOW
# =========================
def run_story_game(screen, fonts):
    total_score = 0

    ready = eeg_wait_screen(screen, fonts)
    if not ready:
        return False

    cal = calibration_screen(screen, fonts)
    if not cal:
        return False

    show_tutorial = tutorial_screen(screen, fonts)
    if not show_tutorial:
        return False

    intro_lines = [
        "The Neural Grid is collapsing sector by sector.",
        "Only one ship can still navigate the unstable cognitive corridors.",
        "Your brain is now the engine. Your mind is now the key."
    ]
    if not cinematic_story(screen, fonts, intro_lines, title="PROLOGUE"):
        return False

    for i, level in enumerate(LEVELS):
        if not cinematic_story(screen, fonts, level["story_before"], title=level["name"]):
            return False

        if not cinematic_story(screen, fonts, level["story_mid"], title="MISSION BRIEF"):
            return False

        result, score = play_level(screen, fonts, i)
        total_score += score

        if result is None:
            return False
        if result == "fail":
            retry = game_over_screen(screen, fonts, total_score, level["name"])
            if retry:
                return run_story_game(screen, fonts)
            else:
                return False
        elif result == "complete":
            if i < len(LEVELS) - 1:
                if not mission_complete_screen(screen, fonts, level, total_score):
                    return False

    ending_lines = [
        "The final corridor opens. The collapse slows behind you.",
        "The Neural Grid survives — for now.",
        "Mission complete. Cognitive link stable. Voyager returns."
    ]
    cinematic_story(screen, fonts, ending_lines, title="EPILOGUE")
    return True

# =========================
# MAIN
# =========================
def main():
    global running_serial

    pygame.init()
    pygame.display.set_caption("Neuro Voyager - EEG Story Adventure")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    icon_surface = pygame.Surface((32, 32))
    icon_surface.fill(CYAN)
    pygame.display.set_icon(icon_surface)

    title_font = pygame.font.SysFont("Arial", 54, bold=True)
    hud_font = pygame.font.SysFont("Arial", 30, bold=True)
    small_font = pygame.font.SysFont("Arial", 22)
    fonts = (title_font, hud_font, small_font)

    init_csv()

    eeg_thread = threading.Thread(target=eeg_reader, daemon=True)
    eeg_thread.start()

    try:
        while True:
            choice = start_menu(screen, fonts)

            if choice == "quit":
                break

            if choice == "calibration":
                ready = eeg_wait_screen(screen, fonts)
                if not ready:
                    break
                calibration_screen(screen, fonts)
                continue

            if choice == "start_journey":
                finished = run_story_game(screen, fonts)
                if not finished:
                    continue

    except Exception as e:
        print("GAME CRASHED:", e)
        input("Press Enter to close...")

    finally:
        running_serial = False
        pygame.quit()

# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    main()