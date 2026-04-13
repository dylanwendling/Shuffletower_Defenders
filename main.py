import pygame
import random
import math
import sys
import os

# --- CONFIGURATION & CONSTANTS ---
WIDTH, HEIGHT = 1000, 700
FPS = 60
GRID_SIZE = 50
ROWS, COLS = 10, 16
MAP_OFFSET_X, MAP_OFFSET_Y = 100, 50

# Colors
WHITE, BLACK, GRAY = (255, 255, 255), (0, 0, 0), (150, 150, 150)
DARK_GRAY, RED, GREEN = (50, 50, 50), (220, 50, 50), (50, 220, 50)
BLUE, GOLD, BROWN = (50, 150, 255), (255, 215, 0), (139, 69, 19)
PURPLE, CYAN, ORANGE = (150, 50, 200), (50, 200, 200), (255, 140, 0)
PINK, SLIME = (255, 105, 180), (100, 255, 100)
HEALER_COLOR = (180, 255, 180)
SHIELD_COLOR = (180, 180, 255)
SPLITTER_COLOR = (255, 165, 80)
FLYING_BOSS_COLOR = (200, 100, 255)
SPLITTER_BOSS_COLOR = (255, 120, 40)
SHIELDED_BOSS_COLOR = (140, 140, 255)

# Curse colors / identifiers
CURSE_COLOR = (180, 30, 180)
CURSE_DEFINITIONS = {
    "FASTER_ENEMIES":  ("Swift Horde",      "Enemies move 30% faster this battle."),
    "DOUBLE_SWARM":    ("Swarm Surge",       "All Swarms spawn in pairs this battle."),
    "ARMORED_ALL":     ("Iron Skin",         "All enemies gain +4 Armor this battle."),
    "REDUCED_ENERGY":  ("Drained Focus",     "Start this battle with -1 Max Energy (min 1)."),
}
CURSE_CYCLE = ["FASTER_ENEMIES", "DOUBLE_SWARM", "ARMORED_ALL", "REDUCED_ENERGY"]

pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Spire Defense")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 16, bold=True)
large_font = pygame.font.SysFont("Arial", 32, bold=True)

PATH = [(0,2), (1,2), (2,2), (3,2), (3,3), (3,4), (3,5), (4,5), (5,5), 
        (6,5), (7,5), (7,4), (7,3), (8,3), (9,3), (10,3), (11,3), (12,3), 
        (12,4), (12,5), (12,6), (12,7), (13,7), (14,7), (15,7)]

# --- AUDIO MANAGER ---

class AudioManager:
    def __init__(self):
        self.current_bgm = None
        self.sounds = {}
        self.bgm_files = {
            "MAIN": "bgm_main.ogg",
            "BATTLE": "bgm_battle.ogg",
            "SHOP_REST": "bgm_shop_rest.ogg",
            "ELITE_BOSS": "bgm_elite_boss.ogg"
        }
        sfx_files = {
            "click": "sfx_click.ogg",
            "draw": "sfx_card_draw.ogg",
            "play": "sfx_card_play.ogg",
            "shoot": "sfx_tower_shoot.ogg",
            "explode": "sfx_explode.ogg",
            "death": "sfx_death.ogg",
            "base_hit": "sfx_base_hit.ogg",
            "win": "sfx_win.ogg",
            "gameover": "sfx_gameover.ogg"
        }
        for name, path in sfx_files.items():
            if os.path.exists(path):
                self.sounds[name] = pygame.mixer.Sound(path)
                self.sounds[name].set_volume(0.5)
            else:
                self.sounds[name] = None

    def play_bgm(self, track_key):
        if self.current_bgm == track_key: return
        self.current_bgm = track_key
        try:
            pygame.mixer.music.load(self.bgm_files[track_key])
            pygame.mixer.music.set_volume(0.4)
            pygame.mixer.music.play(-1)
        except pygame.error:
            pass

    def stop_bgm(self):
        pygame.mixer.music.stop()
        self.current_bgm = None

    def play_sfx(self, sound_key):
        if sound_key in self.sounds and self.sounds[sound_key]:
            self.sounds[sound_key].play()

# --- DATA CLASSES ---

class CardTemplate:
    def __init__(self, name, cost, type, damage=0, range=0, fire_rate=0, hp=0,
                 aoe_radius=0, draw=0, energy_gain=0, exhaust=False,
                 description="", slows=False, piercing=False, chain=0):
        self.name, self.base_cost, self.cost = name, cost, cost
        self.type = type
        self.base_damage, self.damage = damage, damage
        self.range, self.fire_rate = range, fire_rate
        self.base_hp, self.hp = hp, hp
        self.aoe_radius = aoe_radius
        self.base_draw, self.draw_amount = draw, draw
        self.base_energy_gain, self.energy_gain = energy_gain, energy_gain
        self.exhaust = exhaust
        self.slows = slows
        self.piercing = piercing
        self.chain = chain
        self.description, self.upgraded = description, False

    def clone(self):
        c = CardTemplate(self.name, self.base_cost, self.type, self.base_damage,
                         self.range, self.fire_rate, self.base_hp, self.aoe_radius,
                         self.base_draw, self.base_energy_gain, self.exhaust,
                         self.description, self.slows, self.piercing, self.chain)
        c.upgraded, c.cost, c.damage, c.hp = self.upgraded, self.cost, self.damage, self.hp
        c.draw_amount, c.energy_gain = self.draw_amount, self.energy_gain
        return c

    def upgrade(self):
        if not self.upgraded:
            self.upgraded, self.name = True, self.name + "+"
            if self.type == "TOWER":
                self.damage += int(self.base_damage * 0.5)
                if self.aoe_radius > 0: self.aoe_radius += 20
                if "Frost" in self.name: self.cost = 1; self.description = "Low damage. Slows enemies by 50%."
                if "Sniper" in self.name: self.range += 30; self.description = "Pierces armor. Very slow."
                if "Chain" in self.name: self.chain += 4; self.cost = 1; self.description = f"Arcs to {self.chain} nearby enemies."
            elif self.type == "WALL": self.hp += int(self.base_hp * 0.5)
            elif self.type == "SKILL":
                if "Repair" in self.name:
                    self.energy_gain += 1; self.cost = 0; self.description = "Heals base by 15 HP. Gain 1 Energy."
                elif "Quick Thinking" in self.name:
                    self.draw_amount = 2; self.energy_gain = 2; self.description = "Draw 2. Gain 2 Energy."
                elif "Brainstorm" in self.name: self.cost = 0
                else: self.cost = max(0, self.cost - 1)

def get_all_cards():
    return [
        CardTemplate("Arrow Tower",    1, "TOWER", damage=10, range=120, fire_rate=45,  description="Fast, basic tower."),
        CardTemplate("Cannon",         2, "TOWER", damage=35, range=100, fire_rate=100, description="Heavy damage, slow."),
        CardTemplate("The Bomber",     2, "TOWER", damage=25, range=110, fire_rate=120, aoe_radius=60, description="Deals splash damage."),
        CardTemplate("Frost Tower",    2, "TOWER", damage=5,  range=110, fire_rate=50,  description="Low damage. Slows enemies by 50%.", slows=True),
        CardTemplate("Sniper Tower",   3, "TOWER", damage=50, range=120, fire_rate=180, description="Pierces armor. Very slow.", piercing=True),
        CardTemplate("Chain Lightning",2, "TOWER", damage=18, range=110, fire_rate=80,  description="Arcs to 2 nearby enemies.", chain=2),
        CardTemplate("Wooden Wall",    1, "WALL",  hp=50,  description="Blocks path. Has 50 HP."),
        CardTemplate("Repair",         1, "SKILL", description="Heals base by 15 HP."),
        CardTemplate("Quick Thinking", 0, "SKILL", draw=1,  energy_gain=1, description="Draw 1. Gain 1 Energy."),
        CardTemplate("Brainstorm",     1, "SKILL", draw=3,  energy_gain=1, exhaust=True, description="Draw 3. Gain 1 Energy. Exhaust.")
    ]

# --- CLASS DEFINITIONS ---
CLASS_DEFS = {
    "MAGE": {
        "name": "Mage",
        "color": CYAN,
        "desc": "Master of elemental towers. Controls the battlefield with frost and lightning.",
        "detail": "3x Frost Tower, 2x Chain Lightning, 1x Repair, 2x Wooden Wall, 1x Quick Thinking, 1x Brainstorm",
        "deck_indices": [3, 3, 3, 5, 5, 7, 6, 6, 8, 9],  # indices into get_all_cards()
    },
    "BOMBER": {
        "name": "Bomber",
        "color": ORANGE,
        "desc": "Explosive specialist. Obliterates groups with cannon fire and cluster bombs.",
        "detail": "3x Cannon, 2x The Bomber, 1x Repair, 2x Wooden Wall, 1x Quick Thinking, 1x Brainstorm",
        "deck_indices": [1, 1, 1, 2, 2, 7, 6, 6, 8, 9],
    },
    "ROGUE": {
        "name": "Rogue",
        "color": GREEN,
        "desc": "Swift and precise. Overwhelms enemies with rapid arrows and piercing shots.",
        "detail": "3x Arrow Tower, 2x Sniper Tower, 1x Repair, 2x Wooden Wall, 1x Quick Thinking, 1x Brainstorm",
        "deck_indices": [0, 0, 0, 4, 4, 7, 6, 6, 8, 9],
    },
}

class Passive:
    def __init__(self, id, name, cost, description):
        self.id, self.name, self.cost, self.description = id, name, cost, description

PASSIVE_DB = {
    "ENG_1":    Passive("ENG_1",    "Energy Crystal",  100, "Start battles with +1 Max Energy."),
    "HP_1":     Passive("HP_1",     "Iron Plating",     75, "+20 Max Base HP immediately."),
    "DMG_1":    Passive("DMG_1",    "Sharpening Stone",120, "All towers do +5 damage."),
    "GOLD_1":   Passive("GOLD_1",   "Golden Coin",     100, "Gain 20 extra gold after battles."),
    "HARDENED": Passive("HARDENED", "Battle Hardened", 110, "Restore 5 Base HP after each wave."),
    "OVERCHARGE":Passive("OVERCHARGE","Overcharge",     90, "First card played each battle costs 0 Energy."),
    "SYNERGY":  Passive("SYNERGY",  "Twin Tactics",    120, "Same-type adjacent towers deal +10% damage."),
}
def get_all_passives(): return list(PASSIVE_DB.values())

class Wall:
    def __init__(self, gx, gy, hp): self.gx, self.gy, self.max_hp, self.hp = gx, gy, hp, hp

class Enemy:
    def __init__(self, enemy_type, hp_scale=1.0, extra_armor=0, speed_mult=1.0):
        self.type, self.attack_cooldown, self.flying = enemy_type, 0, False
        self.heal_cooldown = 0
        self.slow_timer = 0
        self.armor = 0
        self.has_split = False
        if enemy_type == "BOSS":            self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg = 450*hp_scale, 0.5, PURPLE, 24, 50, 20
        elif enemy_type == "FLYING_BOSS":   self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg, self.flying = 350*hp_scale, 1.0, FLYING_BOSS_COLOR, 26, 60, 0, True
        elif enemy_type == "SPLITTER_BOSS": self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg = 500*hp_scale, 0.5, SPLITTER_BOSS_COLOR, 28, 65, 20
        elif enemy_type == "SHIELDED_BOSS": self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg, self.armor = 400*hp_scale, 0.55, SHIELDED_BOSS_COLOR, 26, 65, 20, 12
        elif enemy_type == "ELITE":         self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg = 150*hp_scale, 0.7, RED, 20, 20, 15
        elif enemy_type == "SWARM":         self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg = 15*hp_scale, 2.2, SLIME, 8, 2, 1
        elif enemy_type == "TANK":          self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg = 100*hp_scale, 0.6, DARK_GRAY, 18, 15, 15
        elif enemy_type == "FLYING":        self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg, self.flying = 30*hp_scale, 1.5, PINK, 12, 10, 0, True
        elif enemy_type == "HEALER":        self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg = 60*hp_scale, 0.8, HEALER_COLOR, 14, 12, 3
        elif enemy_type == "SHIELDED":      self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg, self.armor = 70*hp_scale, 0.75, SHIELD_COLOR, 16, 14, 8, 6
        elif enemy_type == "SPLITTER":      self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg = 60*hp_scale, 0.9, SPLITTER_COLOR, 16, 10, 8
        else:                               self.max_hp, self.speed, self.color, self.radius, self.reward, self.wall_dmg = 40*hp_scale, 1.0, BROWN, 14, 5, 5

        self.armor += extra_armor
        self.speed *= speed_mult
        self.hp, self.path_index = self.max_hp, 0
        self.x = MAP_OFFSET_X + PATH[0][0] * GRID_SIZE + GRID_SIZE//2
        self.y = MAP_OFFSET_Y + PATH[0][1] * GRID_SIZE + GRID_SIZE//2

class Tower:
    def __init__(self, gx, gy, template):
        self.gx, self.gy, self.template, self.cooldown = gx, gy, template, 0
        self.x = MAP_OFFSET_X + gx * GRID_SIZE + GRID_SIZE//2
        self.y = MAP_OFFSET_Y + gy * GRID_SIZE + GRID_SIZE//2

class MapNode:
    def __init__(self, x, y, type, tier):
        self.x, self.y, self.type, self.tier, self.connections = x, y, type, tier, []

# --- MAIN GAME STATE ---

class GameState:
    def __init__(self):
        self.audio = AudioManager()
        self.selected_class = None
        self.setup_menu()

        self.tutorial_messages = [
            "NARRATOR: Welcome to Spire Defense! I'll be your guide. (Press SPACE to continue)",
            "NARRATOR: Your Base is at the end of the dirt path. If enemies touch it, you lose HP.",
            "NARRATOR: Drag cards from your hand onto green grass to place towers. Walls go ON the path.",
            "NARRATOR: Cards cost Energy (bottom left). You start with 3 Energy per turn.",
            "NARRATOR: Enemies vary! Normal (Brown), Swarms (Green), Tanks (Gray)...",
            "NARRATOR: ...Flyers (Pink) ignore walls! Watch for pale green HEALERS — they restore nearby enemies!",
            "NARRATOR: SHIELDED enemies (blue ring) reduce all damage. Use Sniper Towers — they pierce armor!",
            "NARRATOR: SPLITTERS (orange) split into 2 Swarms when killed. Chain Lightning clears groups fast!",
            "NARRATOR: Frost Towers (Cyan) slow enemies by 50%. Pair them with Cannons for big damage!",
            "NARRATOR: Click 'Draw / Discard' to view your deck anytime during planning.",
            "NARRATOR: Build your defenses, then click 'Start Wave' to begin. Good luck!"
        ]
        self.tutorial_index = 0

        self.shopkeeper_intro = [
            "SHOPKEEPER: Ah, a customer! Welcome to my shop! (Press SPACE to continue)",
            "SHOPKEEPER: Cards cost 50 gold each. Click one to buy it and add it to your deck.",
            "SHOPKEEPER: That passive ability on the right? Permanent bonus for the whole run. Worth it!",
            "SHOPKEEPER: You can PURGE up to 3 cards from your deck — once per visit. Thin it to win!",
            "SHOPKEEPER: Pay gold to refresh my stock. New cards, new possibilities!",
            "SHOPKEEPER: Now then — browse at your leisure. I'll be right here.",
        ]
        self.shopkeeper_tips = [
            "SHOPKEEPER: Frost Towers pair beautifully with Cannons. Just saying.",
            "SHOPKEEPER: A lean deck draws better than a bloated one. Think before you buy!",
            "SHOPKEEPER: Healers on the battlefield? Buy a Cannon. Trust me.",
            "SHOPKEEPER: I've seen many defenders pass through. Not many make it past the Boss.",
            "SHOPKEEPER: Come back soon! ...If you survive, that is.",
            "SHOPKEEPER: Gold unspent is gold wasted. Mostly.",
            "SHOPKEEPER: Upgraded cards cost more to sell but are worth far more in battle.",
            "SHOPKEEPER: Shielded enemies laugh at your arrows. Try a Sniper Tower.",
            "SHOPKEEPER: Splitters become two on death. Kill them last... or first. Hard to say.",
            "SHOPKEEPER: Chain Lightning loves packed groups. Let them cluster, then strike.",
            "SHOPKEEPER: Overcharge is best saved for your most expensive card. Plan ahead!",
            "SHOPKEEPER: In Endless mode, the bosses get more exotic each loop. You've been warned.",
            "SHOPKEEPER: Twin Tactics passive? Place the same towers side by side — power in numbers!",
            "SHOPKEEPER: Curses are tempting... but two at once is a gamble even I wouldn't take.",
        ]
        self.shopkeeper_index = 0
        self.shopkeeper_tip = self.shopkeeper_tips[0]

    def setup_menu(self):
        self.mode, self.paused, self.tutorial_active = "MENU", False, False
        self.is_endless, self.loop_count, self.beat_boss_in_endless = False, 0, False

        self.audio.play_bgm("MAIN")

        cards = get_all_cards()
        self.towers = [
            Tower(1, 4, cards[0]), Tower(3, 6, cards[3]), Tower(5, 3, cards[1]),
            Tower(7, 7, cards[3]), Tower(8, 4, cards[2]), Tower(11, 2, cards[3]),
            Tower(13, 6, cards[0]), Tower(14, 3, cards[1]),
        ]
        self.walls = {(7, 5): Wall(7, 5, 1000), (3, 5): Wall(3, 5, 1000)}
        self.enemies, self.lasers, self.explosions, self.spawn_timer = [], [], [], 0
        self.master_deck, self.passives, self.map_tiers = [], [], []
        self.base_max_hp, self.gold, self.base_hp = 100, 50, 100
        self.current_node, self.available_next_nodes = None, []
        self.draw_pile, self.discard_pile, self.exhaust_pile, self.hand = [], [], [], []
        self.max_energy, self.energy = 3, 3
        self.wave, self.max_waves, self.battle_phase = 1, 3, "PLANNING"
        self.enemies_to_spawn, self.shop_cards, self.shop_passive = [], [], None
        self.shop_refresh_cost = 10
        self.reward_choices, self.elite_passive_choices = [], []
        self.reward_card_picked, self.reward_passive_picked = False, False
        self.dragging_card, self.mouse_pos = None, (0, 0)
        self.deck_viewer_tab = "DRAW"
        self.deck_viewer_prev_mode = "BATTLE"
        self.purge_used = False
        self.purge_cards = []
        self.confirm_wave = False
        self.overcharge_used = False

        # Curse system
        self.active_curses = []        # curses active THIS battle
        self.pending_curses = []       # curses chosen, applied on next battle entry
        self.curse_cycle_index = 0     # cycles through CURSE_CYCLE

        # Curse reward state
        self.curse_reward_cards = []   # all 3 possible reward cards
        self.curse_choice_made = False

    def _init_class_deck(self, class_key):
        all_cards = get_all_cards()
        indices = CLASS_DEFS[class_key]["deck_indices"]
        self.master_deck = [all_cards[i].clone() for i in indices]

    def generate_map(self):
        self.map_tiers = []
        for t in range(5):
            num_nodes = random.randint(4, 6)
            tier_nodes = []
            for n in range(num_nodes):
                x = WIDTH // 2 + (n - (num_nodes-1)/2) * 120 + random.randint(-15, 15)
                y = HEIGHT - 100 - t * 100
                if self.loop_count == 0 and t == 0: type = 'TUTORIAL'
                elif t == 0: type = 'BATTLE'
                else: type = random.choices(['BATTLE','ELITE','SHOP','CAMPFIRE'], weights=[35,15,25,25])[0]
                tier_nodes.append(MapNode(x, y, type, t))
            self.map_tiers.append(tier_nodes)
        self.map_tiers.append([MapNode(WIDTH//2, 120, 'BOSS', 5)])

        for t in range(5):
            for node in self.map_tiers[t]:
                targets = random.sample(self.map_tiers[t+1], k=random.randint(1, min(2, len(self.map_tiers[t+1]))))
                node.connections.extend(targets)
        for t in range(1, 6):
            for target in self.map_tiers[t]:
                if not any(target in n.connections for n in self.map_tiers[t-1]):
                    random.choice(self.map_tiers[t-1]).connections.append(target)
        self.available_next_nodes = self.map_tiers[0]

    def start_run(self, class_key):
        self.selected_class = class_key
        self._init_class_deck(class_key)
        self.passives.clear()
        self.base_hp, self.gold = self.base_max_hp, 50
        self.loop_count = 0
        self.active_curses = []
        self.pending_curses = []
        self.curse_cycle_index = 0
        self.generate_map()
        self.mode = "MAP"

    def select_node(self, node):
        self.current_node = node
        self.available_next_nodes = node.connections
        if node.type in ['BATTLE', 'TUTORIAL', 'ELITE', 'BOSS']:
            self.enter_battle(node.type)
        elif node.type == 'SHOP':
            self.shop_refresh_cost = 10; self.refresh_shop_items(); self.mode = "SHOP"
            self.purge_used = False; self.purge_cards = []
            self.shopkeeper_index = 0
            self.shopkeeper_tip = random.choice(self.shopkeeper_tips)
            self.audio.play_bgm("SHOP_REST")
        elif node.type == 'CAMPFIRE':
            self.mode = "CAMPFIRE"
            self.audio.play_bgm("SHOP_REST")
        else:
            self.mode = node.type

    def refresh_shop_items(self):
        self.shop_cards = [c.clone() for c in random.sample(get_all_cards(), 3)]
        for c in self.shop_cards:
            if random.random() < 0.25: c.upgrade()
        avail = [p for p in get_all_passives() if p.id not in self.passives]
        self.shop_passive = random.choice(avail) if avail else None

    def add_passive(self, passive_id):
        self.passives.append(passive_id)
        if passive_id == "HP_1": self.base_max_hp += 20; self.base_hp += 20
        elif passive_id == "ENG_1": self.max_energy += 1

    def enter_battle(self, encounter_type):
        if encounter_type in ['ELITE', 'BOSS']: self.audio.play_bgm("ELITE_BOSS")
        else: self.audio.play_bgm("BATTLE")

        self.towers.clear(); self.walls.clear(); self.enemies.clear(); self.explosions.clear()
        self.wave, self.max_waves = 1, (4 if encounter_type == 'ELITE' else 3)
        self.tutorial_active = (encounter_type == 'TUTORIAL' and self.loop_count == 0)
        self.tutorial_index = 0
        self.draw_pile = [c.clone() for c in self.master_deck]
        random.shuffle(self.draw_pile)
        self.discard_pile.clear(); self.exhaust_pile.clear(); self.hand.clear()
        self.overcharge_used = False

        # Apply pending curses for this battle
        self.active_curses = list(self.pending_curses)
        self.pending_curses = []

        self.start_turn()
        self.mode = "BATTLE"

    def _get_curse_energy_penalty(self):
        return 1 if "REDUCED_ENERGY" in self.active_curses else 0

    def draw_cards(self, amount):
        for _ in range(amount):
            if not self.draw_pile:
                if not self.discard_pile: break
                self.draw_pile = list(self.discard_pile)
                random.shuffle(self.draw_pile)
                self.discard_pile.clear()
            if self.draw_pile:
                self.hand.append(self.draw_pile.pop(0))
                self.audio.play_sfx("draw")

    def start_turn(self):
        self.battle_phase = "PLANNING"
        base_energy = self.max_energy - self._get_curse_energy_penalty()
        self.energy = max(1, base_energy)
        self.discard_pile.extend(self.hand); self.hand.clear(); self.draw_cards(5)
        self.enemies_to_spawn = []
        if self.wave > 1 and "HARDENED" in self.passives:
            self.base_hp = min(self.base_max_hp, self.base_hp + 5)

        if self.tutorial_active:
            hp_scale = 0.5
            if self.wave == 1:   self.enemies_to_spawn = [Enemy("NORMAL", hp_scale) for _ in range(3)]
            elif self.wave == 2: self.enemies_to_spawn = [Enemy("NORMAL", hp_scale) for _ in range(5)]
            else:                self.enemies_to_spawn = [Enemy("TANK", hp_scale)] + [Enemy("NORMAL", hp_scale) for _ in range(2)]
            return

        hp_scale   = 0.8 + (self.current_node.tier * 0.25) + (self.loop_count * 2.0)
        count      = 3 + self.wave * 2 + self.current_node.tier + (self.loop_count * 2)
        extra_armor = 4 if "ARMORED_ALL" in self.active_curses else 0
        speed_mult  = 1.3 if "FASTER_ENEMIES" in self.active_curses else 1.0
        double_swarm = "DOUBLE_SWARM" in self.active_curses

        def make_enemy(etype):
            return Enemy(etype, hp_scale, extra_armor=extra_armor, speed_mult=speed_mult)

        def add_swarm():
            self.enemies_to_spawn.append(make_enemy("SWARM"))
            if double_swarm:
                self.enemies_to_spawn.append(make_enemy("SWARM"))

        if self.current_node.type in ['ELITE', 'BOSS'] and self.wave in [2, 3]: count += 4

        if self.current_node.type == 'BOSS':
            boss_cycle = ["BOSS", "FLYING_BOSS", "SPLITTER_BOSS", "SHIELDED_BOSS"]
            boss_type  = boss_cycle[self.loop_count % len(boss_cycle)]
            if self.wave == 3:
                self.enemies_to_spawn.append(make_enemy(boss_type))
                for _ in range(count):
                    etype = random.choices(["SWARM","TANK","FLYING","HEALER","SHIELDED","SPLITTER"], weights=[20,28,20,12,12,8])[0]
                    if etype == "SWARM": add_swarm()
                    else: self.enemies_to_spawn.append(make_enemy(etype))
            else:
                for _ in range(count):
                    etype = random.choices(["SWARM","TANK","FLYING","HEALER","SHIELDED","SPLITTER"], weights=[25,22,20,13,12,8])[0]
                    if etype == "SWARM": add_swarm(); add_swarm()
                    else: self.enemies_to_spawn.append(make_enemy(etype))

        elif self.current_node.type == 'ELITE':
            if self.wave == 4:
                self.enemies_to_spawn.append(make_enemy("ELITE"))
                for _ in range(count // 2):
                    self.enemies_to_spawn.append(make_enemy(random.choice(["TANK","FLYING","HEALER","SHIELDED"])))
            else:
                for _ in range(count):
                    etype = random.choices(["SWARM","TANK","FLYING","HEALER","SHIELDED","SPLITTER"], weights=[30,22,20,10,10,8])[0]
                    if etype == "SWARM": add_swarm(); add_swarm()
                    else: self.enemies_to_spawn.append(make_enemy(etype))
        else:
            for _ in range(count):
                roll = random.random()
                if roll < 0.48:   self.enemies_to_spawn.append(make_enemy("NORMAL"))
                elif roll < 0.62: add_swarm(); add_swarm()
                elif roll < 0.74: self.enemies_to_spawn.append(make_enemy("TANK"))
                elif roll < 0.83: self.enemies_to_spawn.append(make_enemy("FLYING"))
                elif roll < 0.90 and self.current_node and self.current_node.tier >= 1:
                    self.enemies_to_spawn.append(make_enemy("SHIELDED"))
                elif roll < 0.96 and self.current_node and self.current_node.tier >= 2:
                    self.enemies_to_spawn.append(make_enemy("SPLITTER"))
                elif self.current_node and self.current_node.tier >= 2:
                    self.enemies_to_spawn.append(make_enemy("HEALER"))
                else: self.enemies_to_spawn.append(make_enemy("NORMAL"))

    def play_card(self, card, gx, gy):
        actual_cost = card.cost
        if "OVERCHARGE" in self.passives and not self.overcharge_used:
            actual_cost = 0
        if self.energy < actual_cost: return False
        if card.type == "TOWER":
            if (gx, gy) in PATH or any(t.gx == gx and t.gy == gy for t in self.towers): return False
            self.towers.append(Tower(gx, gy, card))
        elif card.type == "WALL":
            if (gx, gy) not in PATH or (gx, gy) in self.walls: return False
            self.walls[(gx, gy)] = Wall(gx, gy, card.hp)
        elif card.type == "SKILL":
            if "Repair" in card.name: self.base_hp = min(self.base_max_hp, self.base_hp + 15)

        self.energy -= actual_cost
        if "OVERCHARGE" in self.passives and not self.overcharge_used:
            self.overcharge_used = True
        self.hand.remove(card)
        self.audio.play_sfx("play")

        if card.draw_amount > 0: self.draw_cards(card.draw_amount)
        if card.energy_gain > 0: self.energy += card.energy_gain

        if card.exhaust: self.exhaust_pile.append(card)
        else: self.discard_pile.append(card)
        return True

    def _get_synergy_multiplier(self, tower):
        """Returns 1.0 + 0.1 per adjacent same-type tower (SYNERGY passive)."""
        if "SYNERGY" not in self.passives:
            return 1.0
        adjacents = [(tower.gx-1, tower.gy), (tower.gx+1, tower.gy),
                     (tower.gx, tower.gy-1), (tower.gx, tower.gy+1)]
        count = sum(1 for t in self.towers
                    if (t.gx, t.gy) in adjacents and t.template.name == tower.template.name)
        return 1.0 + count * 0.10

    def _simulate_entities(self, is_menu=False):
        for e in self.enemies[:]:
            if e.slow_timer > 0: e.slow_timer -= 1
            effective_speed = e.speed * (0.5 if e.slow_timer > 0 else 1.0)

            blocked = False
            if not e.flying and e.path_index < len(PATH) - 1:
                nx, ny = PATH[e.path_index + 1]
                if (nx, ny) in self.walls:
                    blocked = True
                    if e.attack_cooldown <= 0:
                        self.walls[(nx, ny)].hp -= e.wall_dmg
                        e.attack_cooldown = 60
                        if self.walls[(nx, ny)].hp <= 0: del self.walls[(nx, ny)]
                    else: e.attack_cooldown -= 1

            reached_end = False
            if not blocked:
                if e.path_index < len(PATH) - 1:
                    tx = MAP_OFFSET_X + PATH[e.path_index + 1][0] * GRID_SIZE + GRID_SIZE//2
                    ty = MAP_OFFSET_Y + PATH[e.path_index + 1][1] * GRID_SIZE + GRID_SIZE//2
                    dist = math.hypot(tx - e.x, ty - e.y)
                    if dist < effective_speed: e.x, e.y = tx, ty; e.path_index += 1
                    else: e.x += ((tx-e.x)/dist)*effective_speed; e.y += ((ty-e.y)/dist)*effective_speed
                else: reached_end = True

            if e.hp <= 0:
                if not is_menu:
                    self.gold += e.reward
                    self.audio.play_sfx("death")
                    if e.type == "SPLITTER" and not e.has_split:
                        for _ in range(2):
                            child = Enemy("SWARM", 1.0)
                            child.x, child.y = e.x, e.y
                            child.path_index = e.path_index
                            self.enemies.append(child)
                    if e.type == "SPLITTER_BOSS" and not e.has_split:
                        for _ in range(3):
                            child = Enemy("SPLITTER", 1.0)
                            child.x, child.y = e.x, e.y
                            child.path_index = e.path_index
                            self.enemies.append(child)
                self.enemies.remove(e)
            elif reached_end:
                if not is_menu:
                    if e.type == 'BOSS':
                        self.base_hp = 0; self.mode = "GAMEOVER"
                        self.audio.stop_bgm(); self.audio.play_sfx("gameover")
                    else:
                        dmg = 15 if e.type == 'ELITE' else 5
                        if self.current_node and self.current_node.type in ['ELITE','BOSS']: dmg *= 2
                        self.base_hp -= dmg
                        self.audio.play_sfx("base_hit")
                        if self.base_hp <= 0:
                            self.mode = "GAMEOVER"
                            self.audio.stop_bgm(); self.audio.play_sfx("gameover")
                if e in self.enemies: self.enemies.remove(e)

        self.lasers.clear()
        bonus_dmg = 5 if "DMG_1" in self.passives and not is_menu else 0

        # HEALER pulse logic
        for healer in self.enemies:
            if healer.type == "HEALER":
                if healer.heal_cooldown > 0: healer.heal_cooldown -= 1
                elif healer.hp > 0:
                    heal_range = 80
                    for other in self.enemies:
                        if other is not healer and other.hp < other.max_hp:
                            if math.hypot(other.x - healer.x, other.y - healer.y) <= heal_range:
                                other.hp = min(other.max_hp, other.hp + 8)
                    healer.heal_cooldown = 120

        for t in self.towers:
            if t.cooldown > 0: t.cooldown -= 1
            if t.cooldown <= 0:
                in_range = [e for e in self.enemies if math.hypot(e.x - t.x, e.y - t.y) <= t.template.range]
                if in_range:
                    target = in_range[0]
                    synergy_mult = self._get_synergy_multiplier(t) if not is_menu else 1.0
                    total_dmg = int((t.template.damage + bonus_dmg) * synergy_mult)

                    if t.template.aoe_radius > 0:
                        self.audio.play_sfx("explode")
                        self.explosions.append([target.x, target.y, t.template.aoe_radius, 15])
                        for splash in self.enemies:
                            if math.hypot(splash.x - target.x, splash.y - target.y) <= t.template.aoe_radius:
                                arm = 0 if t.template.piercing else splash.armor
                                splash.hp -= max(1, total_dmg - arm)
                    elif t.template.chain > 0:
                        self.lasers.append((t.x, t.y, target.x, target.y))
                        arm = 0 if t.template.piercing else target.armor
                        target.hp -= max(1, total_dmg - arm)
                        if not is_menu: self.audio.play_sfx("shoot")
                        hit_targets = {target}
                        last_target = target
                        chain_dmg = total_dmg // 2
                        for _ in range(t.template.chain):
                            nearby = [e for e in self.enemies if e not in hit_targets and math.hypot(e.x - last_target.x, e.y - last_target.y) <= 80]
                            if not nearby: break
                            arc_t = min(nearby, key=lambda e: math.hypot(e.x - last_target.x, e.y - last_target.y))
                            self.lasers.append((int(last_target.x), int(last_target.y), int(arc_t.x), int(arc_t.y)))
                            arm = 0 if t.template.piercing else arc_t.armor
                            arc_t.hp -= max(1, chain_dmg - arm)
                            hit_targets.add(arc_t); last_target = arc_t; chain_dmg = chain_dmg // 2
                    else:
                        arm = 0 if t.template.piercing else target.armor
                        target.hp -= max(1, total_dmg - arm)
                        if t.template.slows: target.slow_timer = 90
                        self.lasers.append((t.x, t.y, target.x, target.y))
                        if not is_menu: self.audio.play_sfx("shoot")
                    t.cooldown = t.template.fire_rate

        for e in self.enemies[:]:
            if e.hp <= 0:
                if not is_menu:
                    self.gold += e.reward
                    self.audio.play_sfx("death")
                if e in self.enemies: self.enemies.remove(e)

    def update_menu(self):
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.enemies.append(Enemy(random.choice(["NORMAL","SWARM","TANK","FLYING","HEALER","SHIELDED","SPLITTER"]), 1.0))
            self.spawn_timer = 45
        self._simulate_entities(is_menu=True)

    def generate_elite_rewards(self):
        self.reward_choices = [c.clone() for c in random.sample(get_all_cards(), 3)]
        for c in self.reward_choices: c.upgrade()
        avail = [p for p in get_all_passives() if p.id not in self.passives]
        self.elite_passive_choices = random.sample(avail, min(3, len(avail)))
        self.reward_card_picked, self.reward_passive_picked = False, False

    def open_curse_reward(self):
        """After a normal battle, show the 3-card / curse choice screen."""
        self.reward_choices  = random.sample(get_all_cards(), 3)
        self.curse_reward_cards = [c.clone() for c in self.reward_choices]
        self.curse_choice_made  = False
        self.mode = "CURSE_REWARD"
        self.audio.play_bgm("SHOP_REST")

    def _next_curse(self):
        curse_id = CURSE_CYCLE[self.curse_cycle_index % len(CURSE_CYCLE)]
        self.curse_cycle_index += 1
        return curse_id

    def update_battle(self):
        if self.paused: return
        if self.battle_phase == "ACTION":
            if self.enemies_to_spawn:
                self.spawn_timer -= 1
                if self.spawn_timer <= 0:
                    self.enemies.append(self.enemies_to_spawn.pop(0))
                    self.spawn_timer = 30

            self._simulate_entities(is_menu=False)

            if not self.enemies and not self.enemies_to_spawn:
                if self.wave >= self.max_waves:
                    if "GOLD_1" in self.passives: self.gold += 20
                    self.audio.play_sfx("win")

                    if self.current_node.type == 'BOSS':
                        if self.is_endless:
                            self.beat_boss_in_endless = True
                            self.generate_elite_rewards()
                            self.mode = "ELITE_REWARD"
                            self.audio.play_bgm("SHOP_REST")
                        else:
                            self.mode = "WIN"
                            self.audio.stop_bgm()
                    elif self.current_node.type == 'ELITE':
                        self.generate_elite_rewards()
                        self.mode = "ELITE_REWARD"
                        self.audio.play_bgm("SHOP_REST")
                    else:
                        # Normal battle: go to curse reward screen
                        self.open_curse_reward()
                else:
                    self.wave += 1; self.start_turn()

# --- RENDERING UTILS ---

def draw_text(surf, text, font, color, x, y, center=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center: rect.center = (x, y)
    else:       rect.topleft = (x, y)
    surf.blit(img, rect)

def draw_card(surf, card, x, y, is_hover=False):
    rect = pygame.Rect(x, y, 120, 160)
    pygame.draw.rect(surf, WHITE, rect, border_radius=8)
    pygame.draw.rect(surf, GOLD if is_hover else (GREEN if card.upgraded else BLACK), rect, 3, border_radius=8)
    draw_text(surf, card.name, font, BLACK, x+5, y+5)
    draw_text(surf, f"Cost: {card.cost}", font, BLUE, x+5, y+25)
    draw_text(surf, card.type, font, GRAY, x+5, y+45)
    ly, line = y + 70, ""
    for w in card.description.split():
        if font.size(line + w)[0] > 100: draw_text(surf, line, font, BLACK, x+5, ly); ly += 20; line = w + " "
        else: line += w + " "
    draw_text(surf, line, font, BLACK, x+5, ly)
    if card.damage > 0: draw_text(surf, f"DMG: {card.damage}", font, RED,   x+5,  y+135)
    if card.hp > 0:     draw_text(surf, f"HP: {card.hp}",      font, GREEN, x+60, y+135)

def draw_item_box(surf, title, desc, cost, x, y, width, height, is_hover, show_cost=True):
    rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surf, DARK_GRAY, rect, border_radius=8)
    pygame.draw.rect(surf, GOLD if is_hover else WHITE, rect, 2, border_radius=8)
    draw_text(surf, title, font, GOLD, x+10, y+10)
    if show_cost: draw_text(surf, f"{cost}g", font, WHITE, x+width-40, y+10)
    draw_text(surf, desc, font, GRAY, x+10, y+40)

def draw_passives(surf, game, mx, my):
    tooltip = None
    for i, pid in enumerate(game.passives):
        passive = PASSIVE_DB[pid]
        px, py = WIDTH//2 - (len(game.passives)*40)//2 + i*40, 10
        pygame.draw.rect(surf, PURPLE, (px, py, 32, 32), border_radius=5)
        pygame.draw.rect(surf, GOLD,   (px, py, 32, 32), 2, border_radius=5)
        draw_text(surf, "P", font, WHITE, px+16, py+16, center=True)
        if px <= mx <= px+32 and py <= my <= py+32:
            tooltip = (passive.name, passive.description, px, py+40)
    if tooltip:
        box_w = max(font.size(tooltip[0])[0], font.size(tooltip[1])[0]) + 20
        pygame.draw.rect(surf, DARK_GRAY, (tooltip[2], tooltip[3], box_w, 45), border_radius=5)
        pygame.draw.rect(surf, GOLD,      (tooltip[2], tooltip[3], box_w, 45), 2, border_radius=5)
        draw_text(surf, tooltip[0], font, GOLD,  tooltip[2]+10, tooltip[3]+5)
        draw_text(surf, tooltip[1], font, WHITE, tooltip[2]+10, tooltip[3]+25)

def draw_active_curses(surf, game):
    if not game.active_curses: return
    x = WIDTH - 10
    for cid in game.active_curses:
        name, _ = CURSE_DEFINITIONS[cid]
        tw = font.size(f"CURSE: {name}")[0] + 12
        x -= tw + 6
        pygame.draw.rect(surf, (80, 0, 80), (x, 65, tw, 22), border_radius=4)
        pygame.draw.rect(surf, CURSE_COLOR, (x, 65, tw, 22), 2, border_radius=4)
        draw_text(surf, f"CURSE: {name}", font, (255, 150, 255), x+6, 66)

def draw_grid_and_entities(surf, game):
    for r in range(ROWS):
        for c in range(COLS):
            rect = pygame.Rect(MAP_OFFSET_X + c*GRID_SIZE, MAP_OFFSET_Y + r*GRID_SIZE, GRID_SIZE, GRID_SIZE)
            if (c, r) in PATH: pygame.draw.rect(surf, (100, 80, 60), rect)
            else: pygame.draw.rect(surf, (60, 140, 60), rect); pygame.draw.rect(surf, (50, 120, 50), rect, 1)

    bx = MAP_OFFSET_X + PATH[-1][0]*GRID_SIZE
    by = MAP_OFFSET_Y + PATH[-1][1]*GRID_SIZE
    pygame.draw.rect(surf, DARK_GRAY, (bx, by-20, GRID_SIZE, GRID_SIZE+20))
    draw_text(surf, "BASE", font, WHITE, bx+GRID_SIZE//2, by, center=True)

    for (gx, gy), wall in game.walls.items():
        pygame.draw.rect(surf, BROWN, (MAP_OFFSET_X + gx*GRID_SIZE+5, MAP_OFFSET_Y + gy*GRID_SIZE+5, 40, 40))
        draw_text(surf, str(wall.hp), font, WHITE, MAP_OFFSET_X + gx*GRID_SIZE+25, MAP_OFFSET_Y + gy*GRID_SIZE+25, center=True)

    for t in game.towers:
        # Synergy glow: green ring if SYNERGY passive and has adjacent same-type
        if "SYNERGY" in game.passives:
            syng = game._get_synergy_multiplier(t)
            if syng > 1.0:
                pygame.draw.circle(surf, (0, 255, 100), (t.x, t.y), 24, 3)
        color = ORANGE if "Bomber" in t.template.name else (CYAN if "Frost" in t.template.name else (DARK_GRAY if "Cannon" in t.template.name else (WHITE if "Sniper" in t.template.name else (GOLD if "Chain" in t.template.name else BLUE))))
        pygame.draw.circle(surf, color, (t.x, t.y), 20)
        pygame.draw.circle(surf, BLACK, (t.x, t.y), 20, 2)

    for e in game.enemies:
        pygame.draw.circle(surf, e.color, (int(e.x), int(e.y)), e.radius)
        if e.armor > 0:
            pygame.draw.circle(surf, (200, 200, 255), (int(e.x), int(e.y)), e.radius + 3, 3)
        if e.slow_timer > 0:
            slow_surf = pygame.Surface((e.radius*2, e.radius*2), pygame.SRCALPHA)
            pygame.draw.circle(slow_surf, (100, 180, 255, 100), (e.radius, e.radius), e.radius)
            surf.blit(slow_surf, (int(e.x) - e.radius, int(e.y) - e.radius))
        if e.flying: pygame.draw.circle(surf, WHITE, (int(e.x), int(e.y)), e.radius+2, 1)
        if e.type == "HEALER":
            pygame.draw.circle(surf, (100, 255, 100), (int(e.x), int(e.y)), 80, 1)
            draw_text(surf, "H", font, (0,100,0), int(e.x), int(e.y), center=True)
        if e.type in ["SPLITTER","SPLITTER_BOSS"]:
            draw_text(surf, "S", font, WHITE, int(e.x), int(e.y), center=True)
        if e.type in ["FLYING_BOSS","SPLITTER_BOSS","SHIELDED_BOSS","BOSS"]:
            draw_text(surf, "B", font, WHITE, int(e.x), int(e.y), center=True)
        if game.mode != "MENU":
            pygame.draw.rect(surf, RED,   (e.x-15, e.y-20, 30, 5))
            pygame.draw.rect(surf, GREEN, (e.x-15, e.y-20, 30*(e.hp/e.max_hp), 5))

    for lx1, ly1, lx2, ly2 in game.lasers:
        pygame.draw.line(surf, GOLD, (lx1, ly1), (lx2, ly2), 3)
    for ex in game.explosions[:]:
        pygame.draw.circle(surf, ORANGE, (int(ex[0]), int(ex[1])), ex[2], 3)
        ex[3] -= 1
        if ex[3] <= 0: game.explosions.remove(ex)

# --- MAIN LOOP ---

game = GameState()
running = True

while running:
    game.mouse_pos = pygame.mouse.get_pos()
    mx, my = game.mouse_pos

    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and game.mode in ["BATTLE","MAP"]:
                game.paused = not game.paused

            if event.key == pygame.K_SPACE and game.mode == "BATTLE" and game.tutorial_active:
                if game.tutorial_index < len(game.tutorial_messages) - 1:
                    game.tutorial_index += 1
                    game.audio.play_sfx("click")

            if event.key == pygame.K_SPACE and game.mode == "SHOP" and game.shopkeeper_index < len(game.shopkeeper_intro) - 1:
                game.shopkeeper_index += 1
                game.audio.play_sfx("click")

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if game.paused:
                game.audio.play_sfx("click")
                if WIDTH//2-100 <= mx <= WIDTH//2+100 and HEIGHT//2-30 <= my <= HEIGHT//2+20: game.paused = False
                if WIDTH//2-100 <= mx <= WIDTH//2+100 and HEIGHT//2+40 <= my <= HEIGHT//2+90: game.setup_menu()
                continue

            # ---- MENU ----
            if game.mode == "MENU":
                if WIDTH//2-150 <= mx <= WIDTH//2+150:
                    if HEIGHT//2-40 <= my <= HEIGHT//2+20:
                        game.audio.play_sfx("click")
                        game.is_endless = False; game.mode = "CLASS_SELECT"
                    elif HEIGHT//2+40 <= my <= HEIGHT//2+100:
                        game.audio.play_sfx("click")
                        game.is_endless = True; game.mode = "CLASS_SELECT"

            # ---- CLASS SELECT ----
            elif game.mode == "CLASS_SELECT":
                class_keys = list(CLASS_DEFS.keys())
                for i, ckey in enumerate(class_keys):
                    bx = WIDTH//2 - 420 + i * 290
                    by = HEIGHT//2 - 120
                    if bx <= mx <= bx+260 and by <= my <= by+300:
                        game.audio.play_sfx("click")
                        game.start_run(ckey)
                        break
                # Back button
                if 20 <= mx <= 130 and 20 <= my <= 55:
                    game.audio.play_sfx("click")
                    game.mode = "MENU"

            # ---- MAP ----
            elif game.mode == "MAP":
                if 20 <= mx <= 160 and HEIGHT-45 <= my <= HEIGHT-15:
                    game.audio.play_sfx("click")
                    game.deck_viewer_tab = "DRAW"
                    game.deck_viewer_prev_mode = "MAP"
                    game.mode = "DECK_VIEWER"
                else:
                    for node in game.available_next_nodes:
                        if math.hypot(mx - node.x, my - node.y) < 25:
                            game.audio.play_sfx("click")
                            game.select_node(node); break

            # ---- BATTLE ----
            elif game.mode == "BATTLE" and game.battle_phase == "PLANNING":
                if WIDTH-150 <= mx <= WIDTH-20 and 20 <= my <= 60:
                    if not game.towers and not game.confirm_wave:
                        game.confirm_wave = True
                        game.audio.play_sfx("click")
                    else:
                        game.audio.play_sfx("click")
                        game.battle_phase = "ACTION"
                        game.confirm_wave = False
                elif game.confirm_wave:
                    if WIDTH//2-120 <= mx <= WIDTH//2-10 and HEIGHT//2+20 <= my <= HEIGHT//2+60:
                        game.audio.play_sfx("click"); game.battle_phase = "ACTION"; game.confirm_wave = False
                    elif WIDTH//2+10 <= mx <= WIDTH//2+120 and HEIGHT//2+20 <= my <= HEIGHT//2+60:
                        game.audio.play_sfx("click"); game.confirm_wave = False
                if 18 <= mx <= 163 and HEIGHT-83 <= my <= HEIGHT-58:
                    game.audio.play_sfx("click")
                    game.deck_viewer_tab = "DRAW"
                    game.deck_viewer_prev_mode = game.battle_phase
                    game.mode = "DECK_VIEWER"
                hand_x = WIDTH//2 - (len(game.hand)*130)//2
                for i, card in enumerate(game.hand):
                    cx, cy = hand_x + i*130, HEIGHT-180
                    if cx <= mx <= cx+120 and cy <= my <= cy+160:
                        game.audio.play_sfx("click"); game.dragging_card = card; break

            # ---- CURSE REWARD ----
            elif game.mode == "CURSE_REWARD":
                # Three options: top area = no curse (1 card), middle = 1 curse (2 cards), bottom = 2 curses (3 cards)
                options = [
                    (1, 0, HEIGHT//2 - 200, "1 Card — No Curse"),
                    (2, 1, HEIGHT//2 - 60,  "2 Cards — 1 Curse"),
                    (3, 2, HEIGHT//2 + 80,  "3 Cards — 2 Curses"),
                ]
                for num_cards, num_curses, oy, label in options:
                    if WIDTH//2 - 280 <= mx <= WIDTH//2 + 280 and oy <= my <= oy + 110:
                        game.audio.play_sfx("click")
                        # Add cards
                        chosen = random.sample(game.curse_reward_cards, min(num_cards, len(game.curse_reward_cards)))
                        for c in chosen:
                            game.master_deck.append(c.clone())
                        # Add curses as pending
                        for _ in range(num_curses):
                            game.pending_curses.append(game._next_curse())
                        game.curse_choice_made = True
                        game.mode = "MAP"
                        game.audio.play_bgm("MAIN")
                        break

            # ---- REWARD (elite/boss) ----
            elif game.mode == "REWARD":
                if WIDTH//2-50 <= mx <= WIDTH//2+50 and 550 <= my <= 590:
                    game.audio.play_sfx("click"); game.mode = "MAP"; game.audio.play_bgm("MAIN")
                for i, card in enumerate(game.reward_choices):
                    if 300+i*150 <= mx <= 300+i*150+120 and 300 <= my <= 460:
                        game.audio.play_sfx("click")
                        game.master_deck.append(card.clone()); game.mode = "MAP"
                        game.audio.play_bgm("MAIN")

            elif game.mode == "ELITE_REWARD":
                if WIDTH//2-100 <= mx <= WIDTH//2+100 and 600 <= my <= 640:
                    game.audio.play_sfx("click")
                    if game.beat_boss_in_endless:
                        game.beat_boss_in_endless = False; game.loop_count += 1; game.generate_map()
                    game.mode = "MAP"; game.audio.play_bgm("MAIN")
                if not game.reward_card_picked:
                    for i, card in enumerate(game.reward_choices):
                        if 150+i*150 <= mx <= 150+i*150+120 and 200 <= my <= 360:
                            game.audio.play_sfx("click"); game.master_deck.append(card.clone()); game.reward_card_picked = True
                if not game.reward_passive_picked:
                    for i, passive in enumerate(game.elite_passive_choices):
                        if 650 <= mx <= 850 and 200+i*100 <= my <= 280+i*100:
                            game.audio.play_sfx("click"); game.add_passive(passive.id); game.reward_passive_picked = True
                if game.reward_card_picked and game.reward_passive_picked:
                    if game.beat_boss_in_endless:
                        game.beat_boss_in_endless = False; game.loop_count += 1; game.generate_map()
                    game.mode = "MAP"; game.audio.play_bgm("MAIN")

            elif game.mode == "SHOP":
                if 400 <= mx <= 600 and 610 <= my <= 655:
                    game.audio.play_sfx("click"); game.mode = "MAP"; game.audio.play_bgm("MAIN")
                elif not game.purge_used and 400 <= mx <= 600 and 555 <= my <= 600:
                    game.audio.play_sfx("click")
                    game.purge_cards = random.sample(game.master_deck, min(3, len(game.master_deck)))
                    game.mode = "SHOP_PURGE"
                elif 400 <= mx <= 600 and 500 <= my <= 545:
                    if game.gold >= game.shop_refresh_cost:
                        game.audio.play_sfx("click"); game.gold -= game.shop_refresh_cost
                        game.shop_refresh_cost += 10; game.refresh_shop_items()
                for i, card in enumerate(game.shop_cards):
                    if card and 150+i*150 <= mx <= 150+i*150+120 and 300 <= my <= 460:
                        if game.gold >= 50:
                            game.audio.play_sfx("click"); game.gold -= 50
                            game.master_deck.append(card.clone()); game.shop_cards[i] = None
                if game.shop_passive and 650 <= mx <= 850 and 300 <= my <= 380:
                    if game.gold >= game.shop_passive.cost:
                        game.audio.play_sfx("click"); game.gold -= game.shop_passive.cost
                        game.add_passive(game.shop_passive.id); game.shop_passive = None

            elif game.mode == "SHOP_PURGE":
                if WIDTH//2-100 <= mx <= WIDTH//2+100 and HEIGHT-70 <= my <= HEIGHT-30:
                    game.audio.play_sfx("click"); game.purge_used = True; game.mode = "SHOP"
                for i, card in enumerate(game.purge_cards):
                    cx = 200 + i*220; cy = 280
                    if cx <= mx <= cx+120 and cy <= my <= cy+160:
                        if card and card in game.master_deck:
                            game.audio.play_sfx("click")
                            sell_price = 75 if card.upgraded else 25
                            game.gold += sell_price
                            game.master_deck.remove(card)
                            game.purge_cards[i] = None
                        break

            elif game.mode == "CAMPFIRE":
                if 200 <= mx <= 350 and 300 <= my <= 400:
                    game.audio.play_sfx("click"); game.base_hp = min(game.base_max_hp, game.base_hp + 30)
                    game.mode = "MAP"; game.audio.play_bgm("MAIN")
                if 425 <= mx <= 575 and 300 <= my <= 400:
                    game.audio.play_sfx("click"); game.mode = "CAMPFIRE_SMITH"
                if 650 <= mx <= 800 and 300 <= my <= 400:
                    game.audio.play_sfx("click"); game.mode = "CAMPFIRE_COPY"

            elif game.mode == "CAMPFIRE_SMITH":
                for i, card in enumerate(game.master_deck):
                    if not card.upgraded:
                        cx, cy = 20 + (i%6)*130, 150 + (i//6)*170
                        if cx <= mx <= cx+120 and cy <= my <= cy+160:
                            game.audio.play_sfx("click"); card.upgrade()
                            game.mode = "MAP"; game.audio.play_bgm("MAIN"); break

            elif game.mode == "CAMPFIRE_COPY":
                for i, card in enumerate(game.master_deck):
                    cx, cy = 20 + (i%6)*130, 150 + (i//6)*170
                    if cx <= mx <= cx+120 and cy <= my <= cy+160:
                        game.audio.play_sfx("click"); game.master_deck.append(card.clone())
                        game.mode = "MAP"; game.audio.play_bgm("MAIN"); break

            elif game.mode in ["GAMEOVER", "WIN"]:
                game.setup_menu()

            elif game.mode == "DECK_VIEWER":
                if 20 <= my <= 55:
                    if 20 <= mx <= 140:  game.deck_viewer_tab = "DRAW";    game.audio.play_sfx("click")
                    elif 150 <= mx <= 290: game.deck_viewer_tab = "DISCARD"; game.audio.play_sfx("click")
                    elif 300 <= mx <= 420: game.deck_viewer_tab = "EXHAUST"; game.audio.play_sfx("click")
                if WIDTH-130 <= mx <= WIDTH-20 and 20 <= my <= 55:
                    game.audio.play_sfx("click")
                    game.mode = game.deck_viewer_prev_mode if game.deck_viewer_prev_mode in ["MAP","BATTLE"] else "BATTLE"

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if game.dragging_card:
                if MAP_OFFSET_X <= mx <= MAP_OFFSET_X+COLS*GRID_SIZE and MAP_OFFSET_Y <= my <= MAP_OFFSET_Y+ROWS*GRID_SIZE:
                    gx = (mx - MAP_OFFSET_X) // GRID_SIZE
                    gy = (my - MAP_OFFSET_Y) // GRID_SIZE
                    game.play_card(game.dragging_card, gx, gy)
                game.dragging_card = None

    # --- UPDATE ---
    if game.mode == "BATTLE": game.update_battle()
    elif game.mode == "MENU": game.update_menu()

    # --- DRAW ---
    screen.fill((30, 30, 40))

    # ===================== MENU =====================
    if game.mode == "MENU":
        draw_grid_and_entities(screen, game)
        overlay = pygame.Surface((WIDTH, HEIGHT)); overlay.set_alpha(150); overlay.fill(BLACK); screen.blit(overlay, (0,0))
        draw_text(screen, "SPIRE DEFENSE", pygame.font.SysFont("Arial", 60, bold=True), GOLD, WIDTH//2, HEIGHT//3, center=True)
        pygame.draw.rect(screen, BLUE if (WIDTH//2-150 <= mx <= WIDTH//2+150 and HEIGHT//2-40 <= my <= HEIGHT//2+20) else DARK_GRAY, (WIDTH//2-150, HEIGHT//2-40, 300, 60), border_radius=10)
        draw_text(screen, "STANDARD RUN",  large_font, WHITE, WIDTH//2, HEIGHT//2-10, center=True)
        pygame.draw.rect(screen, PURPLE if (WIDTH//2-150 <= mx <= WIDTH//2+150 and HEIGHT//2+40 <= my <= HEIGHT//2+100) else DARK_GRAY, (WIDTH//2-150, HEIGHT//2+40, 300, 60), border_radius=10)
        draw_text(screen, "ENDLESS MODE",  large_font, WHITE, WIDTH//2, HEIGHT//2+70, center=True)

    # ===================== CLASS SELECT =====================
    elif game.mode == "CLASS_SELECT":
        draw_text(screen, "CHOOSE YOUR CLASS", pygame.font.SysFont("Arial", 48, bold=True), GOLD, WIDTH//2, 60, center=True)
        class_keys = list(CLASS_DEFS.keys())
        for i, ckey in enumerate(class_keys):
            cdef = CLASS_DEFS[ckey]
            bx = WIDTH//2 - 420 + i * 290
            by = HEIGHT//2 - 120
            is_hover = bx <= mx <= bx+260 and by <= my <= by+300
            pygame.draw.rect(screen, (20, 20, 30), (bx, by, 260, 300), border_radius=12)
            pygame.draw.rect(screen, cdef["color"] if is_hover else DARK_GRAY, (bx, by, 260, 300), 3, border_radius=12)
            # Class name
            draw_text(screen, cdef["name"], pygame.font.SysFont("Arial", 28, bold=True), cdef["color"], bx+130, by+30, center=True)
            # Description
            desc_words = cdef["desc"].split()
            dy = by + 70; line = ""
            for w in desc_words:
                if font.size(line + w)[0] > 230: draw_text(screen, line, font, WHITE, bx+15, dy); dy += 20; line = w + " "
                else: line += w + " "
            draw_text(screen, line, font, WHITE, bx+15, dy); dy += 30
            # Deck detail (smaller text)
            detail_words = ("DECK: " + cdef["detail"]).split()
            line = ""
            for w in detail_words:
                if font.size(line + w)[0] > 230: draw_text(screen, line, font, GRAY, bx+15, dy); dy += 18; line = w + " "
                else: line += w + " "
            draw_text(screen, line, font, GRAY, bx+15, dy)
            # Click hint
            draw_text(screen, "Click to Select", font, GOLD if is_hover else GRAY, bx+130, by+270, center=True)

        # Back button
        back_hover = 20 <= mx <= 130 and 20 <= my <= 55
        pygame.draw.rect(screen, RED if back_hover else DARK_GRAY, (20, 20, 110, 35), border_radius=5)
        draw_text(screen, "BACK", font, WHITE, 75, 37, center=True)

    # ===================== MAP =====================
    elif game.mode == "MAP":
        loop_text = f" | Loop: {game.loop_count + 1}" if game.is_endless else ""
        draw_text(screen, f"HP: {game.base_hp}/{game.base_max_hp}  Gold: {game.gold}{loop_text}", large_font, WHITE, WIDTH//2, 30, center=True)
        draw_passives(screen, game, mx, my)
        # Active curses display on map
        if game.pending_curses:
            cx = 10
            draw_text(screen, "Next battle curses:", font, CURSE_COLOR, cx, 65)
            for cid in game.pending_curses:
                name, _ = CURSE_DEFINITIONS[cid]
                draw_text(screen, f"  {name}", font, (255,120,255), cx, 83 + game.pending_curses.index(cid)*18)
        deck_btn_hover = 20 <= mx <= 160 and HEIGHT-45 <= my <= HEIGHT-15
        pygame.draw.rect(screen, BLUE if deck_btn_hover else DARK_GRAY, (20, HEIGHT-45, 140, 30), border_radius=5)
        draw_text(screen, f"View Deck ({len(game.master_deck)})", font, WHITE, 90, HEIGHT-30, center=True)
        for tier in game.map_tiers:
            for node in tier:
                for t in node.connections:
                    pygame.draw.line(screen, GOLD if node == game.current_node else GRAY, (node.x, node.y), (t.x, t.y), 2)
        for tier in game.map_tiers:
            for node in tier:
                color = GREEN if node in game.available_next_nodes else (GOLD if node == game.current_node else GRAY)
                pygame.draw.circle(screen, color, (node.x, node.y), 20)
                icon = "B"
                if node.type == 'TUTORIAL': icon = "T"; pygame.draw.circle(screen, BLUE, (node.x, node.y), 20, 3)
                elif node.type == 'ELITE':   icon = "E"; pygame.draw.circle(screen, RED,  (node.x, node.y), 20, 3)
                elif node.type == 'SHOP':    icon = "$"
                elif node.type == 'CAMPFIRE':icon = "R"
                elif node.type == 'BOSS':    icon = "BOSS"
                draw_text(screen, icon, font, BLACK, node.x, node.y, center=True)

    # ===================== BATTLE =====================
    elif game.mode == "BATTLE":
        draw_grid_and_entities(screen, game)
        draw_text(screen, f"Base HP: {game.base_hp}/{game.base_max_hp}", font, GREEN, 20, 20)
        draw_text(screen, f"Gold: {game.gold}", font, GOLD, 20, 40)
        draw_text(screen, f"Wave: {game.wave}/{game.max_waves}", font, WHITE, 20, 60)
        draw_active_curses(screen, game)

        draw_text(screen, f"Energy: {game.energy}/{game.max_energy}", large_font, BLUE, 20, HEIGHT-130)
        if "OVERCHARGE" in game.passives and not game.overcharge_used:
            draw_text(screen, "OVERCHARGE READY", font, GOLD, 20, HEIGHT-108)
        draw_pile_hover = 20 <= mx <= 160 and HEIGHT-80 <= my <= HEIGHT-60
        pygame.draw.rect(screen, DARK_GRAY if not draw_pile_hover else (70,70,90), (18, HEIGHT-83, 145, 25), border_radius=4)
        draw_text(screen, f"Draw: {len(game.draw_pile)}  Discard: {len(game.discard_pile)}", font, WHITE, 20, HEIGHT-80)
        draw_text(screen, f"Exhaust: {len(game.exhaust_pile)}", font, ORANGE, WIDTH-150, HEIGHT-90)
        draw_passives(screen, game, mx, my)

        if game.tutorial_active:
            pygame.draw.rect(screen, DARK_GRAY, (WIDTH//2-380, 20, 760, 60), border_radius=10)
            pygame.draw.rect(screen, GOLD,      (WIDTH//2-380, 20, 760, 60), 2, border_radius=10)
            draw_text(screen, game.tutorial_messages[game.tutorial_index], font, WHITE, WIDTH//2, 50, center=True)

        if game.battle_phase == "PLANNING":
            pygame.draw.rect(screen, GREEN, (WIDTH-150, 20, 130, 40), border_radius=5)
            draw_text(screen, "Start Wave", font, BLACK, WIDTH-140, 30)

            preview_counts = {}
            for e in game.enemies_to_spawn: preview_counts[e.type] = preview_counts.get(e.type, 0) + 1
            draw_text(screen, "INCOMING WAVE:", font, RED, WIDTH-140, 80)
            y_off = 100
            for etype, ecount in preview_counts.items():
                draw_text(screen, f"{ecount}x {etype}", font, WHITE, WIDTH-140, y_off); y_off += 20

            hand_x = WIDTH//2 - (len(game.hand)*130)//2
            for i, card in enumerate(game.hand):
                if card != game.dragging_card:
                    draw_card(screen, card, hand_x + i*130, HEIGHT-180,
                              hand_x+i*130 <= mx <= hand_x+i*130+120 and HEIGHT-180 <= my <= HEIGHT-20)
            if game.dragging_card: draw_card(screen, game.dragging_card, mx-60, my-80, True)

            if game.confirm_wave:
                overlay = pygame.Surface((WIDTH, HEIGHT)); overlay.set_alpha(160); overlay.fill(BLACK); screen.blit(overlay, (0,0))
                dlg_x, dlg_y, dlg_w, dlg_h = WIDTH//2-220, HEIGHT//2-80, 440, 160
                pygame.draw.rect(screen, DARK_GRAY, (dlg_x, dlg_y, dlg_w, dlg_h), border_radius=10)
                pygame.draw.rect(screen, RED, (dlg_x, dlg_y, dlg_w, dlg_h), 3, border_radius=10)
                draw_text(screen, "No towers placed!", large_font, RED, WIDTH//2, HEIGHT//2-50, center=True)
                draw_text(screen, "Are you sure you want to start the wave?", font, WHITE, WIDTH//2, HEIGHT//2-15, center=True)
                sh = WIDTH//2-120 <= mx <= WIDTH//2-10 and HEIGHT//2+20 <= my <= HEIGHT//2+60
                bh = WIDTH//2+10  <= mx <= WIDTH//2+120 and HEIGHT//2+20 <= my <= HEIGHT//2+60
                pygame.draw.rect(screen, RED   if sh else (100,30,30),  (WIDTH//2-120, HEIGHT//2+20, 110, 40), border_radius=6)
                pygame.draw.rect(screen, GREEN if bh else (30,100,30),  (WIDTH//2+10,  HEIGHT//2+20, 110, 40), border_radius=6)
                draw_text(screen, "Start anyway", font, WHITE, WIDTH//2-65, HEIGHT//2+40, center=True)
                draw_text(screen, "Go back",      font, WHITE, WIDTH//2+65, HEIGHT//2+40, center=True)

    # ===================== CURSE REWARD =====================
    elif game.mode == "CURSE_REWARD":
        draw_text(screen, "BATTLE COMPLETE! CHOOSE YOUR REWARD", large_font, GOLD, WIDTH//2, 50, center=True)
        draw_text(screen, "More cards = more power, but also more curses on your next battle!", font, GRAY, WIDTH//2, 90, center=True)

        options = [
            (1, 0, HEIGHT//2 - 200, "1 Card  |  No Curse"),
            (2, 1, HEIGHT//2 - 60,  "2 Cards  |  1 Curse"),
            (3, 2, HEIGHT//2 + 80,  "3 Cards  |  2 Curses"),
        ]
        cards_all = game.curse_reward_cards
        for num_cards, num_curses, oy, label in options:
            is_hover = WIDTH//2-280 <= mx <= WIDTH//2+280 and oy <= my <= oy+110
            # Background box
            box_color = (40, 40, 55) if not is_hover else (60, 60, 80)
            border_color = GOLD if is_hover else (CURSE_COLOR if num_curses > 0 else GREEN)
            pygame.draw.rect(screen, box_color, (WIDTH//2-280, oy, 560, 110), border_radius=10)
            pygame.draw.rect(screen, border_color, (WIDTH//2-280, oy, 560, 110), 3, border_radius=10)
            # Label
            label_color = GREEN if num_curses == 0 else (ORANGE if num_curses == 1 else RED)
            draw_text(screen, label, large_font, label_color, WIDTH//2-270, oy+10)
            # Show card names for this option
            shown_cards = cards_all[:num_cards]
            for ci, card in enumerate(shown_cards):
                draw_text(screen, f"  {card.name}", font, WHITE, WIDTH//2-270 + ci*185, oy+55)
            # Show curse names
            if num_curses > 0:
                curse_text = "  ".join(CURSE_DEFINITIONS[CURSE_CYCLE[(game.curse_cycle_index + j) % len(CURSE_CYCLE)]][0] for j in range(num_curses))
                draw_text(screen, f"Curses: {curse_text}", font, CURSE_COLOR, WIDTH//2-270, oy+80)

    # ===================== ELITE REWARD =====================
    elif game.mode == "ELITE_REWARD":
        draw_text(screen, "ELITE DEFEATED! CHOOSE 1 CARD & 1 PASSIVE", large_font, GOLD, WIDTH//2, 80, center=True)
        if not game.reward_card_picked:
            draw_text(screen, "CHOOSE 1 UPGRADED CARD", font, WHITE, 350, 160, center=True)
            for i, card in enumerate(game.reward_choices): draw_card(screen, card, 150+i*150, 200, (150+i*150 <= mx <= 150+i*150+120 and 200 <= my <= 360))
        else: draw_text(screen, "CARD SELECTED", large_font, GREEN, 350, 250, center=True)
        if not game.reward_passive_picked:
            draw_text(screen, "CHOOSE 1 PASSIVE", font, WHITE, 750, 160, center=True)
            for i, passive in enumerate(game.elite_passive_choices):
                draw_item_box(screen, passive.name, passive.description, 0, 650, 200+i*100, 200, 80,
                              650 <= mx <= 850 and 200+i*100 <= my <= 280+i*100, show_cost=False)
        else: draw_text(screen, "PASSIVE SELECTED", large_font, GREEN, 750, 250, center=True)
        pygame.draw.rect(screen, GRAY, (WIDTH//2-100, 600, 200, 40), border_radius=5)
        draw_text(screen, "CONTINUE / SKIP", font, BLACK, WIDTH//2, 620, center=True)

    # ===================== SHOP =====================
    elif game.mode == "SHOP":
        draw_text(screen, f"SHOP - Gold: {game.gold}", large_font, GOLD, WIDTH//2, 55, center=True)
        pygame.draw.circle(screen, (210,180,140), (80, 200), 28)
        pygame.draw.rect(screen, (120,60,20), (52,228,56,70), border_radius=6)
        pygame.draw.rect(screen, (80,40,10), (44,195,72,18), border_radius=4)
        pygame.draw.rect(screen, (80,40,10), (54,160,52,40), border_radius=4)
        draw_text(screen, "~", font, (210,180,140), 80, 248, center=True)

        if game.shopkeeper_index < len(game.shopkeeper_intro):
            line = game.shopkeeper_intro[game.shopkeeper_index]
            show_prompt = game.shopkeeper_index < len(game.shopkeeper_intro) - 1
        else:
            line = game.shopkeeper_tip; show_prompt = False
        bubble_w = min(max(font.size(line)[0]+24, 200), WIDTH-140)
        bubble_x, bubble_y = 118, 160
        pygame.draw.rect(screen, WHITE, (bubble_x, bubble_y, bubble_w, 54), border_radius=8)
        pygame.draw.rect(screen, DARK_GRAY, (bubble_x, bubble_y, bubble_w, 54), 2, border_radius=8)
        pygame.draw.polygon(screen, WHITE, [(bubble_x+10, bubble_y+42),(bubble_x-10, bubble_y+60),(bubble_x+24, bubble_y+42)])
        pygame.draw.line(screen, DARK_GRAY, (bubble_x+10, bubble_y+42), (bubble_x-10, bubble_y+60), 2)
        draw_text(screen, line, font, DARK_GRAY, bubble_x+12, bubble_y+8)
        if show_prompt: draw_text(screen, "SPACE to continue...", font, GRAY, bubble_x+12, bubble_y+32)

        for i, card in enumerate(game.shop_cards):
            if card:
                cx, cy = 150+i*150, 300
                draw_text(screen, "Cost: 50g", font, GOLD, cx+25, cy-25)
                draw_card(screen, card, cx, cy, (cx <= mx <= cx+120 and cy <= my <= cy+160))
        if game.shop_passive:
            draw_item_box(screen, game.shop_passive.name, game.shop_passive.description,
                          game.shop_passive.cost, 650, 300, 200, 80, 650 <= mx <= 850 and 300 <= my <= 380)

        pygame.draw.rect(screen, BLUE if 400 <= mx <= 600 and 500 <= my <= 545 else DARK_GRAY, (400,500,200,45), border_radius=5)
        draw_text(screen, f"Refresh Shop ({game.shop_refresh_cost}g)", font, WHITE, 500, 522, center=True)
        purge_color = GRAY if game.purge_used else (ORANGE if 400 <= mx <= 600 and 555 <= my <= 600 else DARK_GRAY)
        pygame.draw.rect(screen, purge_color, (400,555,200,45), border_radius=5)
        draw_text(screen, "PURGE CARDS" if not game.purge_used else "PURGE USED", font, WHITE, 500, 577, center=True)
        pygame.draw.rect(screen, RED if 400 <= mx <= 600 and 610 <= my <= 655 else DARK_GRAY, (400,610,200,45), border_radius=5)
        draw_text(screen, "LEAVE SHOP", font, WHITE, 500, 632, center=True)
        draw_passives(screen, game, mx, my)

    # ===================== SHOP PURGE =====================
    elif game.mode == "SHOP_PURGE":
        draw_text(screen, "PURGE CARDS", large_font, ORANGE, WIDTH//2, 100, center=True)
        draw_text(screen, f"Gold: {game.gold}", font, GOLD, WIDTH//2, 145, center=True)
        draw_text(screen, "Sell any of these 3 cards. This offer is one-time only.", font, GRAY, WIDTH//2, 230, center=True)
        for i, card in enumerate(game.purge_cards):
            if card:
                cx = 200 + i*220; cy = 280
                is_hover = cx <= mx <= cx+120 and cy <= my <= cy+160
                draw_card(screen, card, cx, cy, is_hover)
                sell_price = 75 if card.upgraded else 25
                draw_text(screen, f"Sell: +{sell_price}g", font, GOLD, cx+60, cy+170, center=True)
            else:
                cx = 200 + i*220
                draw_text(screen, "SOLD", large_font, GRAY, cx+60, 360, center=True)
        done_hover = WIDTH//2-100 <= mx <= WIDTH//2+100 and HEIGHT-70 <= my <= HEIGHT-30
        pygame.draw.rect(screen, GREEN if done_hover else DARK_GRAY, (WIDTH//2-100, HEIGHT-70, 200, 40), border_radius=5)
        draw_text(screen, "DONE", font, BLACK, WIDTH//2, HEIGHT-50, center=True)

    # ===================== CAMPFIRE =====================
    elif game.mode == "CAMPFIRE":
        draw_text(screen, "CAMPFIRE", large_font, GOLD, WIDTH//2, 100, center=True)
        pygame.draw.rect(screen, GREEN,  (200,300,150,100), border_radius=10)
        draw_text(screen, "REST",  large_font, BLACK, 275, 340, center=True)
        pygame.draw.rect(screen, BLUE,   (425,300,150,100), border_radius=10)
        draw_text(screen, "SMITH", large_font, BLACK, 500, 340, center=True)
        pygame.draw.rect(screen, PURPLE, (650,300,150,100), border_radius=10)
        draw_text(screen, "COPY",  large_font, WHITE, 725, 340, center=True)

    elif game.mode == "CAMPFIRE_SMITH":
        draw_text(screen, "CHOOSE A CARD TO UPGRADE", large_font, GOLD, WIDTH//2, 50, center=True)
        preview_card = None
        for i, card in enumerate(game.master_deck):
            if not card.upgraded:
                cx, cy = 20 + (i%6)*130, 150 + (i//6)*170
                is_hover = cx <= mx <= cx+120 and cy <= my <= cy+160
                draw_card(screen, card, cx, cy, is_hover)
                if is_hover: preview_card = card.clone(); preview_card.upgrade()
        if preview_card:
            pygame.draw.rect(screen, DARK_GRAY, (WIDTH-220, 150, 200, 300), border_radius=10)
            draw_text(screen, "UPGRADE PREVIEW", font, GOLD, WIDTH-120, 170, center=True)
            draw_card(screen, preview_card, WIDTH-180, 210, True)

    elif game.mode == "CAMPFIRE_COPY":
        draw_text(screen, "CHOOSE A CARD TO DUPLICATE", large_font, PURPLE, WIDTH//2, 50, center=True)
        for i, card in enumerate(game.master_deck):
            cx, cy = 20 + (i%6)*130, 150 + (i//6)*170
            draw_card(screen, card, cx, cy, cx <= mx <= cx+120 and cy <= my <= cy+160)

    # ===================== REWARD =====================
    elif game.mode == "REWARD":
        draw_text(screen, "VICTORY! CHOOSE A REWARD", large_font, WHITE, WIDTH//2, 100, center=True)
        for i, card in enumerate(game.reward_choices):
            draw_card(screen, card, 300+i*150, 300, (300+i*150 <= mx <= 300+i*150+120 and 300 <= my <= 460))
        pygame.draw.rect(screen, GRAY, (WIDTH//2-50, 550, 100, 40), border_radius=5)
        draw_text(screen, "SKIP", font, BLACK, WIDTH//2, 570, center=True)

    # ===================== GAME OVER / WIN =====================
    elif game.mode in ["GAMEOVER", "WIN"]:
        msg = "GAME OVER" if game.mode == "GAMEOVER" else "YOU DEFENDED THE SPIRE!"
        draw_text(screen, msg, large_font, RED if game.mode == "GAMEOVER" else GREEN, WIDTH//2, HEIGHT//2, center=True)
        draw_text(screen, "Click to restart", font, WHITE, WIDTH//2, HEIGHT//2+50, center=True)

    # ===================== DECK VIEWER =====================
    elif game.mode == "DECK_VIEWER":
        screen.fill((20, 20, 30))
        from_map = game.deck_viewer_prev_mode == "MAP"
        if from_map:
            tabs = [("DRAW", "FULL DECK", 20)]
        else:
            tabs = [("DRAW","DRAW",20),("DISCARD","DISCARD",150),("EXHAUST","EXHAUST",300)]
        for tab_id, tab_label, tx in tabs:
            active = game.deck_viewer_tab == tab_id
            pygame.draw.rect(screen, BLUE if active else DARK_GRAY, (tx, 20, 120, 35), border_radius=5)
            draw_text(screen, tab_label, font, WHITE, tx+60, 37, center=True)
        pygame.draw.rect(screen, RED if WIDTH-130 <= mx <= WIDTH-20 and 20 <= my <= 55 else DARK_GRAY, (WIDTH-130, 20, 110, 35), border_radius=5)
        draw_text(screen, "BACK", font, WHITE, WIDTH-75, 37, center=True)
        if from_map:
            draw_text(screen, f"Total cards in deck: {len(game.master_deck)}", font, GRAY, WIDTH//2, 70, center=True)
            pile = game.master_deck
        else:
            draw_text(screen, f"Draw: {len(game.draw_pile)}  Discard: {len(game.discard_pile)}  Exhaust: {len(game.exhaust_pile)}  Hand: {len(game.hand)}", font, GRAY, WIDTH//2, 70, center=True)
            if game.deck_viewer_tab == "DRAW":    pile = game.draw_pile
            elif game.deck_viewer_tab == "DISCARD": pile = game.discard_pile
            else: pile = game.exhaust_pile
        if not pile:
            draw_text(screen, "(empty)", large_font, GRAY, WIDTH//2, HEIGHT//2, center=True)
        else:
            cols_per_row = 7
            for i, card in enumerate(pile):
                cx = 20 + (i % cols_per_row) * 130
                cy = 100 + (i // cols_per_row) * 170
                if cy + 160 < HEIGHT:
                    draw_card(screen, card, cx, cy, False)

    # ===================== PAUSE =====================
    if game.paused:
        overlay = pygame.Surface((WIDTH, HEIGHT)); overlay.set_alpha(180); overlay.fill(BLACK); screen.blit(overlay, (0,0))
        draw_text(screen, "PAUSED", pygame.font.SysFont("Arial", 50, bold=True), WHITE, WIDTH//2, HEIGHT//3, center=True)
        rh = WIDTH//2-100 <= mx <= WIDTH//2+100 and HEIGHT//2-30 <= my <= HEIGHT//2+20
        pygame.draw.rect(screen, BLUE if rh else DARK_GRAY, (WIDTH//2-100, HEIGHT//2-30, 200, 50), border_radius=5)
        draw_text(screen, "Resume", large_font, WHITE, WIDTH//2, HEIGHT//2-5, center=True)
        qh = WIDTH//2-100 <= mx <= WIDTH//2+100 and HEIGHT//2+40 <= my <= HEIGHT//2+90
        pygame.draw.rect(screen, RED if qh else DARK_GRAY, (WIDTH//2-100, HEIGHT//2+40, 200, 50), border_radius=5)
        draw_text(screen, "Quit to Menu", large_font, WHITE, WIDTH//2, HEIGHT//2+65, center=True)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()