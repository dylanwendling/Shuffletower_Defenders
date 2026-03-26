import pygame
import random
import math
import sys

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
PURPLE, CYAN = (150, 50, 200), (50, 200, 200)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Spire Defense: Walls & Relics")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 16, bold=True)
large_font = pygame.font.SysFont("Arial", 32, bold=True)

PATH = [(0,2), (1,2), (2,2), (3,2), (3,3), (3,4), (3,5), (4,5), (5,5), 
        (6,5), (7,5), (7,4), (7,3), (8,3), (9,3), (10,3), (11,3), (12,3), 
        (12,4), (12,5), (12,6), (12,7), (13,7), (14,7), (15,7)]

# --- DATA CLASSES ---

class CardTemplate:
    def __init__(self, name, cost, type, damage=0, range=0, fire_rate=0, hp=0, description=""):
        self.name = name
        self.base_cost = cost
        self.cost = cost
        self.type = type # "TOWER", "WALL", "SKILL"
        self.base_damage = damage
        self.damage = damage
        self.range = range
        self.fire_rate = fire_rate
        self.base_hp = hp
        self.hp = hp
        self.description = description
        self.upgraded = False

    def clone(self):
        c = CardTemplate(self.name, self.base_cost, self.type, self.base_damage, self.range, self.fire_rate, self.base_hp, self.description)
        c.upgraded = self.upgraded
        c.cost = self.cost
        c.damage = self.damage
        c.hp = self.hp
        return c

    def upgrade(self):
        if not self.upgraded:
            self.upgraded = True
            self.name += "+"
            if self.type == "TOWER":
                self.damage += int(self.base_damage * 0.5)
            elif self.type == "WALL":
                self.hp += int(self.base_hp * 0.5)
            elif self.type == "SKILL":
                self.cost = max(0, self.cost - 1)

def get_all_cards():
    return [
        CardTemplate("Arrow Tower", 1, "TOWER", damage=10, range=120, fire_rate=45, description="Fast, basic tower."),
        CardTemplate("Cannon", 2, "TOWER", damage=35, range=100, fire_rate=100, description="Heavy damage, slow."),
        CardTemplate("Wooden Wall", 1, "WALL", hp=100, description="Blocks path. Has 100 HP."),
        CardTemplate("Ice Tower", 2, "TOWER", damage=5, range=90, fire_rate=60, description="Low damage. (Slow WIP)"),
        CardTemplate("Repair", 1, "SKILL", description="Heals base by 15 HP.")
    ]

class Passive:
    def __init__(self, id, name, cost, description):
        self.id = id
        self.name = name
        self.cost = cost
        self.description = description

def get_all_passives():
    return [
        Passive("ENG_1", "Energy Crystal", 100, "Start battles with +1 Max Energy."),
        Passive("HP_1", "Iron Plating", 75, "+20 Max Base HP immediately."),
        Passive("DMG_1", "Sharpening Stone", 120, "All towers do +5 damage.")
    ]

class Wall:
    def __init__(self, gx, gy, hp):
        self.gx, self.gy = gx, gy
        self.max_hp = hp
        self.hp = hp

class Enemy:
    def __init__(self, enemy_type, hp_scale=1.0):
        self.type = enemy_type
        self.attack_cooldown = 0
        if type == "BOSS":
            self.max_hp = 400 * hp_scale
            self.speed, self.color, self.radius, self.reward, self.wall_dmg = 0.5, PURPLE, 22, 50, 20
        elif type == "ELITE":
            self.max_hp = 100 * hp_scale
            self.speed, self.color, self.radius, self.reward, self.wall_dmg = 0.8, RED, 18, 20, 15
        elif type == "FAST":
            self.max_hp = 20 * hp_scale
            self.speed, self.color, self.radius, self.reward, self.wall_dmg = 2.0, CYAN, 10, 5, 2
        else: # BASIC
            self.max_hp = 40 * hp_scale
            self.speed, self.color, self.radius, self.reward, self.wall_dmg = 1.0, BROWN, 14, 10, 5
            
        self.hp = self.max_hp
        self.path_index = 0
        self.x = MAP_OFFSET_X + PATH[0][0] * GRID_SIZE + GRID_SIZE//2
        self.y = MAP_OFFSET_Y + PATH[0][1] * GRID_SIZE + GRID_SIZE//2

class Tower:
    def __init__(self, gx, gy, template):
        self.gx, self.gy = gx, gy
        self.x = MAP_OFFSET_X + gx * GRID_SIZE + GRID_SIZE//2
        self.y = MAP_OFFSET_Y + gy * GRID_SIZE + GRID_SIZE//2
        self.template = template
        self.cooldown = 0

class MapNode:
    def __init__(self, x, y, type, tier):
        self.x, self.y, self.type, self.tier = x, y, type, tier
        self.connections = []

# --- MAIN GAME STATE ---

class GameState:
    def __init__(self):
        self.mode = "MENU"
        self.master_deck = []
        self.passives = []
        self.base_max_hp = 100
        self.base_hp = self.base_max_hp
        self.gold = 50
        self.map_tiers = []
        self.current_node = None
        self.available_next_nodes = []
        
        self.draw_pile, self.discard_pile, self.hand = [], [], []
        self.towers, self.walls, self.enemies, self.lasers = [], {}, [], []
        
        self.max_energy = 3
        self.energy = self.max_energy
        self.wave, self.max_waves = 1, 3
        self.battle_phase = "PLANNING"
        self.spawn_timer = 0
        self.enemies_to_spawn = []
        
        self.shop_cards = []
        self.shop_passive = None
        self.shop_refresh_cost = 10
        
        self.dragging_card = None
        self.mouse_pos = (0,0)

    def _init_starter_deck(self):
        cards = get_all_cards()
        self.master_deck = [cards[0].clone(), cards[0].clone(), cards[0].clone(), cards[2].clone(), cards[2].clone(), cards[4].clone()]

    def generate_map(self):
        self.map_tiers = []
        for t in range(5):
            num_nodes = random.randint(2, 4)
            tier_nodes = []
            for n in range(num_nodes):
                x = WIDTH // 2 + (n - (num_nodes-1)/2) * 150 + random.randint(-20, 20)
                y = HEIGHT - 100 - t * 100
                type = 'BATTLE' if t == 0 else random.choices(['BATTLE', 'ELITE', 'SHOP', 'CAMPFIRE'], weights=[50, 20, 15, 15])[0]
                tier_nodes.append(MapNode(x, y, type, t))
            self.map_tiers.append(tier_nodes)
        self.map_tiers.append([MapNode(WIDTH//2, 80, 'BOSS', 5)])

        for t in range(5):
            for node in self.map_tiers[t]:
                targets = random.sample(self.map_tiers[t+1], k=random.randint(1, min(2, len(self.map_tiers[t+1]))))
                node.connections.extend(targets)
                
        for t in range(1, 6):
            for target in self.map_tiers[t]:
                if not any(target in n.connections for n in self.map_tiers[t-1]):
                    random.choice(self.map_tiers[t-1]).connections.append(target)

        self.available_next_nodes = self.map_tiers[0]

    def start_run(self):
        self._init_starter_deck()
        self.passives.clear()
        self.base_hp = self.base_max_hp
        self.gold = 50
        self.generate_map()
        self.mode = "MAP"

    def select_node(self, node):
        self.current_node = node
        self.available_next_nodes = node.connections
        
        if node.type in ['BATTLE', 'ELITE', 'BOSS']: self.enter_battle(node.type)
        elif node.type == 'SHOP': self.generate_shop(); self.mode = "SHOP"
        else: self.mode = node.type

    def generate_shop(self):
        self.shop_refresh_cost = 10
        self.refresh_shop_items()

    def refresh_shop_items(self):
        self.shop_cards = random.sample(get_all_cards(), 3)
        available_passives = [p for p in get_all_passives() if p.id not in self.passives]
        self.shop_passive = random.choice(available_passives) if available_passives else None

    def add_passive(self, passive_id):
        self.passives.append(passive_id)
        if passive_id == "HP_1":
            self.base_max_hp += 20
            self.base_hp += 20
        elif passive_id == "ENG_1":
            self.max_energy += 1

    def enter_battle(self, encounter_type):
        self.towers.clear(); self.walls.clear(); self.enemies.clear()
        self.wave, self.max_waves = 1, (4 if encounter_type == 'ELITE' else 3)
        self.draw_pile = [c.clone() for c in self.master_deck]
        random.shuffle(self.draw_pile)
        self.discard_pile.clear(); self.hand.clear()
        self.start_turn()
        self.mode = "BATTLE"

    def draw_cards(self, amount):
        for _ in range(amount):
            if not self.draw_pile:
                self.draw_pile = list(self.discard_pile)
                random.shuffle(self.draw_pile)
                self.discard_pile.clear()
            if self.draw_pile: self.hand.append(self.draw_pile.pop(0))

    def start_turn(self):
        self.battle_phase = "PLANNING"
        self.energy = self.max_energy
        self.discard_pile.extend(self.hand)
        self.hand.clear()
        self.draw_cards(5)
        
        hp_scale = 1.0 + (self.current_node.tier * 0.2)
        count = 4 + self.wave * 2
        self.enemies_to_spawn = []
        
        if self.current_node.type == 'BOSS' and self.wave == 3:
            self.enemies_to_spawn.append(Enemy("BOSS", hp_scale))
        elif self.current_node.type == 'ELITE' and self.wave == 4:
            self.enemies_to_spawn.append(Enemy("ELITE", hp_scale))
            for _ in range(3): self.enemies_to_spawn.append(Enemy("FAST", hp_scale))
        else:
            for _ in range(count):
                self.enemies_to_spawn.append(Enemy("FAST" if random.random() < 0.3 else "BASIC", hp_scale))

    def play_card(self, card, gx, gy):
        if self.energy < card.cost: return False
        
        if card.type == "TOWER":
            if (gx, gy) in PATH or any(t.gx == gx and t.gy == gy for t in self.towers): return False
            self.towers.append(Tower(gx, gy, card))
        elif card.type == "WALL":
            if (gx, gy) not in PATH or (gx, gy) in self.walls: return False
            self.walls[(gx, gy)] = Wall(gx, gy, card.hp)
        elif card.type == "SKILL":
            if "Repair" in card.name: self.base_hp = min(self.base_max_hp, self.base_hp + 15)
                
        self.energy -= card.cost
        self.hand.remove(card)
        self.discard_pile.append(card)
        return True

    def update_battle(self):
        if self.battle_phase == "ACTION":
            if self.enemies_to_spawn:
                self.spawn_timer -= 1
                if self.spawn_timer <= 0:
                    self.enemies.append(self.enemies_to_spawn.pop(0))
                    self.spawn_timer = 45
            
            for e in self.enemies[:]:
                # Check for walls on next path tile
                blocked_by_wall = False
                if e.path_index < len(PATH) - 1:
                    next_gx, next_gy = PATH[e.path_index + 1]
                    if (next_gx, next_gy) in self.walls:
                        blocked_by_wall = True
                        if e.attack_cooldown <= 0:
                            self.walls[(next_gx, next_gy)].hp -= e.wall_dmg
                            e.attack_cooldown = 60 # 1 attack per second
                            if self.walls[(next_gx, next_gy)].hp <= 0:
                                del self.walls[(next_gx, next_gy)]
                        else:
                            e.attack_cooldown -= 1
                
                reached_end = False
                if not blocked_by_wall:
                    # Move Enemy
                    if e.path_index < len(PATH) - 1:
                        target_cx, target_cy = PATH[e.path_index + 1]
                        tx = MAP_OFFSET_X + target_cx * GRID_SIZE + GRID_SIZE//2
                        ty = MAP_OFFSET_Y + target_cy * GRID_SIZE + GRID_SIZE//2
                        dist = math.hypot(tx - e.x, ty - e.y)
                        if dist < e.speed:
                            e.x, e.y = tx, ty
                            e.path_index += 1
                        else:
                            e.x += ((tx - e.x) / dist) * e.speed
                            e.y += ((ty - e.y) / dist) * e.speed
                    else:
                        reached_end = True

                if e.hp <= 0:
                    self.gold += e.reward
                    self.enemies.remove(e)
                elif reached_end:
                    self.base_hp -= (10 if e.type in ['BOSS', 'ELITE'] else 5)
                    self.enemies.remove(e)
                    if self.base_hp <= 0: self.mode = "GAMEOVER"
            
            self.lasers.clear()
            bonus_dmg = 5 if "DMG_1" in self.passives else 0
            for t in self.towers:
                if t.cooldown > 0: t.cooldown -= 1
                if t.cooldown <= 0:
                    in_range = [e for e in self.enemies if math.hypot(e.x - t.x, e.y - t.y) <= t.template.range]
                    if in_range:
                        target = in_range[0]
                        target.hp -= (t.template.damage + bonus_dmg)
                        t.cooldown = t.template.fire_rate
                        self.lasers.append((t.x, t.y, target.x, target.y))

            if not self.enemies and not self.enemies_to_spawn:
                if self.wave >= self.max_waves:
                    if self.current_node.type == 'BOSS': self.mode = "WIN"
                    else:
                        self.reward_choices = random.sample(get_all_cards(), 3)
                        self.mode = "REWARD"
                else:
                    self.wave += 1
                    self.start_turn()

# --- RENDERING UTILS ---

def draw_text(surf, text, font, color, x, y, center=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center: rect.center = (x, y)
    else: rect.topleft = (x, y)
    surf.blit(img, rect)

def draw_card(surf, card, x, y, is_hover=False):
    rect = pygame.Rect(x, y, 120, 160)
    pygame.draw.rect(surf, WHITE, rect, border_radius=8)
    color_border = GOLD if is_hover else (GREEN if card.upgraded else BLACK)
    pygame.draw.rect(surf, color_border, rect, 3, border_radius=8)
    
    draw_text(surf, card.name, font, BLACK, x+5, y+5)
    draw_text(surf, f"Cost: {card.cost}", font, BLUE, x+5, y+25)
    draw_text(surf, card.type, font, GRAY, x+5, y+45)
    
    words = card.description.split()
    ly, line = y + 70, ""
    for w in words:
        if font.size(line + w)[0] > 100:
            draw_text(surf, line, font, BLACK, x+5, ly)
            ly += 20; line = w + " "
        else: line += w + " "
    draw_text(surf, line, font, BLACK, x+5, ly)
    if card.damage > 0: draw_text(surf, f"DMG: {card.damage}", font, RED, x+5, y+135)
    if card.hp > 0: draw_text(surf, f"HP: {card.hp}", font, GREEN, x+60, y+135)

def draw_item_box(surf, title, desc, cost, x, y, width, height, is_hover):
    rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surf, DARK_GRAY, rect, border_radius=8)
    pygame.draw.rect(surf, GOLD if is_hover else WHITE, rect, 2, border_radius=8)
    draw_text(surf, title, font, GOLD, x+10, y+10)
    draw_text(surf, f"Cost: {cost}g", font, WHITE, x+width-80, y+10)
    draw_text(surf, desc, font, GRAY, x+10, y+40)

# --- MAIN LOOP ---

game = GameState()
running = True

while running:
    game.mouse_pos = pygame.mouse.get_pos()
    mx, my = game.mouse_pos
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if game.mode == "MENU": game.start_run()
                
            elif game.mode == "MAP":
                for node in game.available_next_nodes:
                    if math.hypot(mx - node.x, my - node.y) < 25:
                        game.select_node(node)
                        break
                        
            elif game.mode == "BATTLE" and game.battle_phase == "PLANNING":
                if WIDTH-150 <= mx <= WIDTH-20 and 20 <= my <= 60: game.battle_phase = "ACTION"
                hand_x = WIDTH//2 - (len(game.hand)*130)//2
                for i, card in enumerate(game.hand):
                    cx, cy = hand_x + i * 130, HEIGHT - 180
                    if cx <= mx <= cx+120 and cy <= my <= cy+160:
                        game.dragging_card = card
                        break

            elif game.mode == "REWARD":
                if WIDTH//2-50 <= mx <= WIDTH//2+50 and 550 <= my <= 590: game.mode = "MAP"
                for i, card in enumerate(game.reward_choices):
                    cx = 300 + i * 150
                    if cx <= mx <= cx+120 and 300 <= my <= 460:
                        game.master_deck.append(card.clone())
                        game.mode = "MAP"

            elif game.mode == "SHOP":
                if 400 <= mx <= 600 and 600 <= my <= 650: game.mode = "MAP"
                
                # Buy Cards
                for i, card in enumerate(game.shop_cards):
                    if card is None: continue
                    cx, cy = 150 + i * 150, 300
                    if cx <= mx <= cx+120 and cy <= my <= cy+160:
                        if game.gold >= 50:
                            game.gold -= 50
                            game.master_deck.append(card.clone())
                            game.shop_cards[i] = None # Item gone
                            
                # Buy Passive
                if game.shop_passive:
                    if 650 <= mx <= 850 and 300 <= my <= 380:
                        if game.gold >= game.shop_passive.cost:
                            game.gold -= game.shop_passive.cost
                            game.add_passive(game.shop_passive.id)
                            game.shop_passive = None
                            
                # Refresh Button
                if 400 <= mx <= 600 and 520 <= my <= 570:
                    if game.gold >= game.shop_refresh_cost:
                        game.gold -= game.shop_refresh_cost
                        game.shop_refresh_cost += 10
                        game.refresh_shop_items()

            elif game.mode == "CAMPFIRE":
                # Rest
                if 300 <= mx <= 450 and 300 <= my <= 400:
                    game.base_hp = min(game.base_max_hp, game.base_hp + 30)
                    game.mode = "MAP"
                # Select Smith mode
                if 550 <= mx <= 700 and 300 <= my <= 400:
                    game.mode = "CAMPFIRE_SMITH"
            
            elif game.mode == "CAMPFIRE_SMITH":
                # Click a card to upgrade
                cols = 6
                for i, card in enumerate(game.master_deck):
                    if not card.upgraded:
                        r, c = i // cols, i % cols
                        cx, cy = 100 + c*130, 150 + r*170
                        if cx <= mx <= cx+120 and cy <= my <= cy+160:
                            card.upgrade()
                            game.mode = "MAP"
                            break

            elif game.mode in ["GAMEOVER", "WIN"]:
                game = GameState()
                
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if game.dragging_card:
                if MAP_OFFSET_X <= mx <= MAP_OFFSET_X + COLS*GRID_SIZE and MAP_OFFSET_Y <= my <= MAP_OFFSET_Y + ROWS*GRID_SIZE:
                    gx, gy = (mx - MAP_OFFSET_X) // GRID_SIZE, (my - MAP_OFFSET_Y) // GRID_SIZE
                    game.play_card(game.dragging_card, gx, gy)
                game.dragging_card = None

    # --- UPDATE & DRAW ---
    if game.mode == "BATTLE": game.update_battle()

    screen.fill((30, 30, 40))

    if game.mode == "MENU":
        draw_text(screen, "SPIRE DEFENSE", large_font, WHITE, WIDTH//2, HEIGHT//3, center=True)
        draw_text(screen, "Click anywhere to start", font, GRAY, WIDTH//2, HEIGHT//2, center=True)
        
    elif game.mode == "MAP":
        draw_text(screen, f"MAP - HP: {game.base_hp}/{game.base_max_hp} | Gold: {game.gold}", large_font, WHITE, WIDTH//2, 40, center=True)
        for tier in game.map_tiers:
            for node in tier:
                for target in node.connections:
                    pygame.draw.line(screen, GOLD if node == game.current_node else GRAY, (node.x, node.y), (target.x, target.y), 2)
        for tier in game.map_tiers:
            for node in tier:
                color = GREEN if node in game.available_next_nodes else (GOLD if node == game.current_node else GRAY)
                pygame.draw.circle(screen, color, (node.x, node.y), 20)
                icon = "B"
                if node.type == 'ELITE': icon = "E"; pygame.draw.circle(screen, RED, (node.x, node.y), 20, 3)
                elif node.type == 'SHOP': icon = "$"
                elif node.type == 'CAMPFIRE': icon = "R"
                elif node.type == 'BOSS': icon = "BOSS"
                draw_text(screen, icon, font, BLACK, node.x, node.y, center=True)

    elif game.mode == "BATTLE":
        for r in range(ROWS):
            for c in range(COLS):
                rect = pygame.Rect(MAP_OFFSET_X + c*GRID_SIZE, MAP_OFFSET_Y + r*GRID_SIZE, GRID_SIZE, GRID_SIZE)
                if (c, r) in PATH: pygame.draw.rect(screen, (100, 80, 60), rect)
                else: 
                    pygame.draw.rect(screen, (60, 140, 60), rect)
                    pygame.draw.rect(screen, (50, 120, 50), rect, 1)

        bx, by = MAP_OFFSET_X + PATH[-1][0]*GRID_SIZE, MAP_OFFSET_Y + PATH[-1][1]*GRID_SIZE
        pygame.draw.rect(screen, DARK_GRAY, (bx, by-20, GRID_SIZE, GRID_SIZE+20))
        draw_text(screen, "BASE", font, WHITE, bx+GRID_SIZE//2, by, center=True)

        for (gx, gy), wall in game.walls.items():
            pygame.draw.rect(screen, BROWN, (MAP_OFFSET_X + gx*GRID_SIZE+5, MAP_OFFSET_Y + gy*GRID_SIZE+5, 40, 40))
            draw_text(screen, str(wall.hp), font, WHITE, MAP_OFFSET_X + gx*GRID_SIZE+25, MAP_OFFSET_Y + gy*GRID_SIZE+25, center=True)
            
        for t in game.towers:
            pygame.draw.circle(screen, CYAN if "Ice" in t.template.name else (DARK_GRAY if "Cannon" in t.template.name else BLUE), (t.x, t.y), 20)
            pygame.draw.circle(screen, BLACK, (t.x, t.y), 20, 2)
            
        for e in game.enemies:
            pygame.draw.circle(screen, e.color, (int(e.x), int(e.y)), e.radius)
            pygame.draw.rect(screen, RED, (e.x-15, e.y-20, 30, 5))
            pygame.draw.rect(screen, GREEN, (e.x-15, e.y-20, 30 * (e.hp/e.max_hp), 5))
            
        for lx1, ly1, lx2, ly2 in game.lasers:
            pygame.draw.line(screen, GOLD, (lx1, ly1), (lx2, ly2), 3)

        draw_text(screen, f"Base HP: {game.base_hp}/{game.base_max_hp}", font, GREEN, 20, 20)
        draw_text(screen, f"Gold: {game.gold}", font, GOLD, 20, 40)
        draw_text(screen, f"Wave: {game.wave}/{game.max_waves}", font, WHITE, 20, 60)
        draw_text(screen, f"Energy: {game.energy}/{game.max_energy}", large_font, BLUE, 20, HEIGHT - 180)

        if game.battle_phase == "PLANNING":
            pygame.draw.rect(screen, GREEN, (WIDTH-150, 20, 130, 40), border_radius=5)
            draw_text(screen, "Start Wave", font, BLACK, WIDTH-140, 30)
            hand_x = WIDTH//2 - (len(game.hand)*130)//2
            for i, card in enumerate(game.hand):
                if card != game.dragging_card:
                    cx, cy = hand_x + i * 130, HEIGHT - 180
                    is_hover = cx <= mx <= cx+120 and cy <= my <= cy+160
                    draw_card(screen, card, cx, cy, is_hover)
            if game.dragging_card:
                draw_card(screen, game.dragging_card, mx-60, my-80, True)

    elif game.mode == "SHOP":
        draw_text(screen, f"SHOP - Gold: {game.gold}", large_font, GOLD, WIDTH//2, 100, center=True)
        draw_text(screen, "CARDS (50g)", font, WHITE, 300, 250, center=True)
        draw_text(screen, "RELICS", font, WHITE, 750, 250, center=True)
        
        # Draw Cards
        for i, card in enumerate(game.shop_cards):
            if card: draw_card(screen, card, 150 + i * 150, 300, (150+i*150 <= mx <= 150+i*150+120 and 300 <= my <= 460))
                
        # Draw Passive
        if game.shop_passive:
            is_hover = 650 <= mx <= 850 and 300 <= my <= 380
            draw_item_box(screen, game.shop_passive.name, game.shop_passive.description, game.shop_passive.cost, 650, 300, 200, 80, is_hover)
            
        # Draw Refresh Button
        refresh_hover = 400 <= mx <= 600 and 520 <= my <= 570
        pygame.draw.rect(screen, BLUE if refresh_hover else DARK_GRAY, (400, 520, 200, 50), border_radius=5)
        draw_text(screen, f"Refresh Shop ({game.shop_refresh_cost}g)", font, WHITE, 500, 545, center=True)

        # Draw Leave Button
        pygame.draw.rect(screen, RED, (400, 600, 200, 50), border_radius=5)
        draw_text(screen, "LEAVE SHOP", font, WHITE, 500, 625, center=True)

    elif game.mode == "CAMPFIRE":
        draw_text(screen, "CAMPFIRE", large_font, GOLD, WIDTH//2, 100, center=True)
        draw_text(screen, "Choose your action for this rest site:", font, WHITE, WIDTH//2, 160, center=True)
        
        pygame.draw.rect(screen, GREEN, (300, 300, 150, 100), border_radius=10)
        draw_text(screen, "REST", large_font, BLACK, 375, 340, center=True)
        draw_text(screen, "Heal 30 Base HP", font, BLACK, 375, 370, center=True)
        
        pygame.draw.rect(screen, BLUE, (550, 300, 150, 100), border_radius=10)
        draw_text(screen, "SMITH", large_font, BLACK, 625, 340, center=True)
        draw_text(screen, "Upgrade a Card", font, BLACK, 625, 370, center=True)

    elif game.mode == "CAMPFIRE_SMITH":
        draw_text(screen, "CHOOSE A CARD TO UPGRADE", large_font, GOLD, WIDTH//2, 50, center=True)
        cols = 6
        for i, card in enumerate(game.master_deck):
            if not card.upgraded:
                r, c = i // cols, i % cols
                cx, cy = 100 + c*130, 150 + r*170
                is_hover = cx <= mx <= cx+120 and cy <= my <= cy+160
                draw_card(screen, card, cx, cy, is_hover)

    elif game.mode == "REWARD":
        draw_text(screen, "VICTORY! CHOOSE A REWARD", large_font, WHITE, WIDTH//2, 100, center=True)
        for i, card in enumerate(game.reward_choices):
            draw_card(screen, card, 300 + i * 150, 300, (300+i*150 <= mx <= 300+i*150+120 and 300 <= my <= 460))
        pygame.draw.rect(screen, GRAY, (WIDTH//2-50, 550, 100, 40), border_radius=5)
        draw_text(screen, "SKIP", font, BLACK, WIDTH//2, 570, center=True)

    elif game.mode == "GAMEOVER":
        draw_text(screen, "GAME OVER", large_font, RED, WIDTH//2, HEIGHT//2, center=True)
        draw_text(screen, "Click to restart", font, WHITE, WIDTH//2, HEIGHT//2 + 50, center=True)

    elif game.mode == "WIN":
        draw_text(screen, "YOU DEFENDED THE SPIRE!", large_font, GREEN, WIDTH//2, HEIGHT//2, center=True)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()