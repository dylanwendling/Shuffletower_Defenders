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
pygame.display.set_caption("Spire Defense: Node Map Edition")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 18, bold=True)
large_font = pygame.font.SysFont("Arial", 36, bold=True)

# Fixed Winding Path for TD Grid
PATH = [(0,2), (1,2), (2,2), (3,2), (3,3), (3,4), (3,5), (4,5), (5,5), 
        (6,5), (7,5), (7,4), (7,3), (8,3), (9,3), (10,3), (11,3), (12,3), 
        (12,4), (12,5), (12,6), (12,7), (13,7), (14,7), (15,7)]

# --- DATA CLASSES ---

class CardTemplate:
    def __init__(self, name, cost, type, damage=0, range=0, fire_rate=0, description=""):
        self.name = name
        self.base_cost = cost
        self.cost = cost
        self.type = type # "TOWER", "TRAP", "SKILL"
        self.base_damage = damage
        self.damage = damage
        self.range = range
        self.fire_rate = fire_rate
        self.description = description
        self.upgraded = False

    def clone(self):
        c = CardTemplate(self.name, self.base_cost, self.type, self.base_damage, self.range, self.fire_rate, self.description)
        c.upgraded = self.upgraded
        c.cost = self.cost
        c.damage = self.damage
        return c

    def upgrade(self):
        if not self.upgraded:
            self.upgraded = True
            self.name += "+"
            if self.type == "TOWER" or self.type == "TRAP":
                self.damage += int(self.base_damage * 0.5) # +50% damage
            elif self.type == "SKILL":
                self.cost = max(0, self.cost - 1) # Reduce cost

def get_all_cards():
    return [
        CardTemplate("Arrow Tower", 1, "TOWER", damage=10, range=120, fire_rate=45, description="Fast, basic tower."),
        CardTemplate("Cannon", 2, "TOWER", damage=35, range=100, fire_rate=100, description="Heavy damage, slow."),
        CardTemplate("Spike Trap", 1, "TRAP", damage=40, description="Damages passing enemies."),
        CardTemplate("Ice Tower", 2, "TOWER", damage=5, range=90, fire_rate=60, description="Low damage. (Slow not implemented yet)"),
        CardTemplate("Repair", 1, "SKILL", description="Heals base by 15 HP.")
    ]

class MapNode:
    def __init__(self, x, y, type, tier):
        self.x = x
        self.y = y
        self.type = type # 'BATTLE', 'ELITE', 'SHOP', 'CAMPFIRE', 'BOSS'
        self.tier = tier
        self.connections = [] # Next nodes

class Enemy:
    def __init__(self, enemy_type, hp_scale=1.0):
        self.type = enemy_type
        if type == "BOSS":
            self.max_hp = 400 * hp_scale
            self.speed = 0.5
            self.color = PURPLE
            self.radius = 22
            self.reward = 50
        elif type == "ELITE":
            self.max_hp = 100 * hp_scale
            self.speed = 0.8
            self.color = RED
            self.radius = 18
            self.reward = 20
        elif type == "FAST":
            self.max_hp = 20 * hp_scale
            self.speed = 2.0
            self.color = CYAN
            self.radius = 10
            self.reward = 5
        else: # BASIC
            self.max_hp = 40 * hp_scale
            self.speed = 1.0
            self.color = BROWN
            self.radius = 14
            self.reward = 10
            
        self.hp = self.max_hp
        self.path_index = 0
        self.x = MAP_OFFSET_X + PATH[0][0] * GRID_SIZE + GRID_SIZE//2
        self.y = MAP_OFFSET_Y + PATH[0][1] * GRID_SIZE + GRID_SIZE//2

    def move(self):
        if self.path_index < len(PATH) - 1:
            target_cx, target_cy = PATH[self.path_index + 1]
            tx = MAP_OFFSET_X + target_cx * GRID_SIZE + GRID_SIZE//2
            ty = MAP_OFFSET_Y + target_cy * GRID_SIZE + GRID_SIZE//2
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            if dist < self.speed:
                self.x, self.y = tx, ty
                self.path_index += 1
            else:
                self.x += (dx / dist) * self.speed
                self.y += (dy / dist) * self.speed
        return self.path_index == len(PATH) - 1

class Tower:
    def __init__(self, gx, gy, template):
        self.gx, self.gy = gx, gy
        self.x = MAP_OFFSET_X + gx * GRID_SIZE + GRID_SIZE//2
        self.y = MAP_OFFSET_Y + gy * GRID_SIZE + GRID_SIZE//2
        self.template = template
        self.cooldown = 0

# --- MAIN GAME STATE ---

class GameState:
    def __init__(self):
        self.mode = "MENU"
        # Run specific data
        self.master_deck = []
        self.base_max_hp = 100
        self.base_hp = self.base_max_hp
        self.gold = 50
        self.map_tiers = []
        self.current_node = None
        self.available_next_nodes = []
        
        # Battle specific data
        self.draw_pile = []
        self.discard_pile = []
        self.hand = []
        self.towers = []
        self.traps = {} 
        self.enemies = []
        self.max_energy = 3
        self.energy = self.max_energy
        self.wave = 1
        self.max_waves = 3
        self.battle_phase = "PLANNING"
        self.spawn_timer = 0
        self.enemies_to_spawn = []
        self.lasers = []
        
        # Interaction data
        self.dragging_card = None
        self.mouse_pos = (0,0)
        self.reward_choices = []
        
        self._init_starter_deck()

    def _init_starter_deck(self):
        cards = get_all_cards()
        # 4 Basic Towers, 1 Trap, 1 Repair
        self.master_deck = [cards[0].clone(), cards[0].clone(), cards[0].clone(), cards[0].clone(), cards[2].clone(), cards[4].clone()]

    def generate_map(self):
        self.map_tiers = []
        # Tiers 0 to 4
        for t in range(5):
            num_nodes = random.randint(2, 4)
            tier_nodes = []
            for n in range(num_nodes):
                x = WIDTH // 2 + (n - (num_nodes-1)/2) * 150 + random.randint(-20, 20)
                y = HEIGHT - 100 - t * 100
                if t == 0:
                    type = 'BATTLE'
                else:
                    type = random.choices(['BATTLE', 'ELITE', 'SHOP', 'CAMPFIRE'], weights=[50, 20, 15, 15])[0]
                tier_nodes.append(MapNode(x, y, type, t))
            self.map_tiers.append(tier_nodes)
            
        # Tier 5: BOSS
        boss_node = MapNode(WIDTH//2, 80, 'BOSS', 5)
        self.map_tiers.append([boss_node])

        # Connect paths
        for t in range(5):
            for node in self.map_tiers[t]:
                possible_targets = self.map_tiers[t+1]
                # Each node connects to 1 or 2 nodes in the next tier
                num_connections = random.randint(1, min(2, len(possible_targets)))
                targets = random.sample(possible_targets, k=num_connections)
                node.connections.extend(targets)
                
        # Make sure every node in next tier has at least one parent (basic fix)
        for t in range(1, 6):
            for target in self.map_tiers[t]:
                parents = [n for n in self.map_tiers[t-1] if target in n.connections]
                if not parents:
                    random.choice(self.map_tiers[t-1]).connections.append(target)

        self.available_next_nodes = self.map_tiers[0] # Can choose any start node

    def start_run(self):
        self._init_starter_deck()
        self.base_hp = self.base_max_hp
        self.gold = 50
        self.generate_map()
        self.current_node = None
        self.mode = "MAP"

    def select_node(self, node):
        self.current_node = node
        self.available_next_nodes = node.connections
        
        if node.type in ['BATTLE', 'ELITE', 'BOSS']:
            self.enter_battle(node.type)
        else:
            self.mode = node.type

    def enter_battle(self, encounter_type):
        self.towers.clear()
        self.traps.clear()
        self.enemies.clear()
        self.wave = 1
        self.max_waves = 3 if encounter_type != 'ELITE' else 4
        
        # Clone master deck into draw pile
        self.draw_pile = [c.clone() for c in self.master_deck]
        random.shuffle(self.draw_pile)
        self.discard_pile.clear()
        self.hand.clear()
        
        self.start_turn()
        self.mode = "BATTLE"

    def draw_cards(self, amount):
        for _ in range(amount):
            if not self.draw_pile:
                self.draw_pile = list(self.discard_pile)
                random.shuffle(self.draw_pile)
                self.discard_pile.clear()
            if self.draw_pile:
                self.hand.append(self.draw_pile.pop(0))

    def start_turn(self):
        self.battle_phase = "PLANNING"
        self.energy = self.max_energy
        # Discard remaining hand
        self.discard_pile.extend(self.hand)
        self.hand.clear()
        self.draw_cards(5)
        
        # Prep wave enemies
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
                type = "FAST" if random.random() < 0.3 else "BASIC"
                self.enemies_to_spawn.append(Enemy(type, hp_scale))

    def play_card(self, card, gx, gy):
        if self.energy < card.cost: return False
        
        if card.type == "TOWER":
            if (gx, gy) in PATH or any(t.gx == gx and t.gy == gy for t in self.towers): return False
            self.towers.append(Tower(gx, gy, card))
        elif card.type == "TRAP":
            if (gx, gy) not in PATH: return False
            self.traps[(gx, gy)] = card.damage
        elif card.type == "SKILL":
            if "Repair" in card.name:
                self.base_hp = min(self.base_max_hp, self.base_hp + 15)
                
        self.energy -= card.cost
        self.hand.remove(card)
        self.discard_pile.append(card)
        return True

    def update_battle(self):
        if self.battle_phase == "ACTION":
            # Spawn
            if self.enemies_to_spawn:
                self.spawn_timer -= 1
                if self.spawn_timer <= 0:
                    self.enemies.append(self.enemies_to_spawn.pop(0))
                    self.spawn_timer = 45
            
            # Enemy Movement & Traps
            for e in self.enemies[:]:
                reached_end = e.move()
                egx, egy = int((e.x - MAP_OFFSET_X)//GRID_SIZE), int((e.y - MAP_OFFSET_Y)//GRID_SIZE)
                
                if (egx, egy) in self.traps:
                    e.hp -= self.traps[(egx, egy)]
                    del self.traps[(egx, egy)]
                
                if e.hp <= 0:
                    self.gold += e.reward
                    self.enemies.remove(e)
                elif reached_end:
                    damage = 10 if e.type in ['BOSS', 'ELITE'] else 5
                    self.base_hp -= damage
                    self.enemies.remove(e)
                    if self.base_hp <= 0:
                        self.mode = "GAMEOVER"
            
            # Towers Fire
            self.lasers.clear()
            for t in self.towers:
                if t.cooldown > 0: t.cooldown -= 1
                if t.cooldown <= 0:
                    in_range = [e for e in self.enemies if math.hypot(e.x - t.x, e.y - t.y) <= t.template.range]
                    if in_range:
                        target = in_range[0]
                        target.hp -= t.template.damage
                        t.cooldown = t.template.fire_rate
                        self.lasers.append((t.x, t.y, target.x, target.y))
                        if target.hp <= 0 and target in self.enemies:
                            self.gold += target.reward
                            self.enemies.remove(target)

            # Wave Check
            if not self.enemies and not self.enemies_to_spawn:
                if self.wave >= self.max_waves:
                    if self.current_node.type == 'BOSS':
                        self.mode = "WIN"
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
    
    # Description wrap
    words = card.description.split()
    ly, line = y + 70, ""
    for w in words:
        if font.size(line + w)[0] > 100:
            draw_text(surf, line, font, BLACK, x+5, ly)
            ly += 20; line = w + " "
        else: line += w + " "
    draw_text(surf, line, font, BLACK, x+5, ly)
    if card.damage > 0:
        draw_text(surf, f"DMG: {card.damage}", font, RED, x+5, y+135)

# --- MAIN LOOP ---

game = GameState()
running = True

while running:
    game.mouse_pos = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = game.mouse_pos
            
            if game.mode == "MENU":
                game.start_run()
                
            elif game.mode == "MAP":
                # Check clicking on valid next nodes
                for node in game.available_next_nodes:
                    if math.hypot(mx - node.x, my - node.y) < 25:
                        game.select_node(node)
                        break
                        
            elif game.mode == "BATTLE" and game.battle_phase == "PLANNING":
                # Start Wave Button
                if WIDTH-150 <= mx <= WIDTH-20 and 20 <= my <= 60:
                    game.battle_phase = "ACTION"
                # Pick up card
                hand_x = WIDTH//2 - (len(game.hand)*130)//2
                for i, card in enumerate(game.hand):
                    cx, cy = hand_x + i * 130, HEIGHT - 180
                    if cx <= mx <= cx+120 and cy <= my <= cy+160:
                        game.dragging_card = card
                        break

            elif game.mode == "REWARD":
                # Skip Reward
                if WIDTH//2-50 <= mx <= WIDTH//2+50 and 550 <= my <= 590:
                    game.mode = "MAP"
                # Pick Card
                for i, card in enumerate(game.reward_choices):
                    cx = 300 + i * 150
                    if cx <= mx <= cx+120 and 300 <= my <= 460:
                        game.master_deck.append(card.clone())
                        game.mode = "MAP"

            elif game.mode == "SHOP":
                if 400 <= mx <= 600 and 500 <= my <= 550: game.mode = "MAP"
                # Buy cards (hardcoded shop items for now)
                shop_items = get_all_cards()[:4]
                for i, card in enumerate(shop_items):
                    cx = 200 + i * 150
                    if cx <= mx <= cx+120 and 300 <= my <= 460:
                        if game.gold >= 60:
                            game.gold -= 60
                            game.master_deck.append(card.clone())

            elif game.mode == "CAMPFIRE":
                # Heal
                if 300 <= mx <= 450 and 300 <= my <= 400:
                    game.base_hp = min(game.base_max_hp, game.base_hp + 30)
                    game.mode = "MAP"
                # Upgrade random card (simplification for UI brevity)
                if 550 <= mx <= 700 and 300 <= my <= 400:
                    upgradable = [c for c in game.master_deck if not c.upgraded]
                    if upgradable:
                        random.choice(upgradable).upgrade()
                    game.mode = "MAP"

            elif game.mode in ["GAMEOVER", "WIN"]:
                game = GameState()
                
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if game.dragging_card:
                mx, my = game.mouse_pos
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
        draw_text(screen, f"MAP - Base HP: {game.base_hp} | Gold: {game.gold}", large_font, WHITE, WIDTH//2, 40, center=True)
        # Draw Connections
        for tier in game.map_tiers:
            for node in tier:
                for target in node.connections:
                    color = GOLD if node == game.current_node else GRAY
                    pygame.draw.line(screen, color, (node.x, node.y), (target.x, target.y), 2)
        # Draw Nodes
        for tier in game.map_tiers:
            for node in tier:
                color = GRAY
                if node in game.available_next_nodes: color = GREEN
                if node == game.current_node: color = GOLD
                pygame.draw.circle(screen, color, (node.x, node.y), 20)
                
                # Icons (text based)
                icon = "B"
                if node.type == 'ELITE': icon = "E"; pygame.draw.circle(screen, RED, (node.x, node.y), 20, 3)
                if node.type == 'SHOP': icon = "$"
                if node.type == 'CAMPFIRE': icon = "R"
                if node.type == 'BOSS': icon = "BOSS"
                draw_text(screen, icon, font, BLACK, node.x, node.y, center=True)

    elif game.mode == "BATTLE":
        # Draw Grid
        for r in range(ROWS):
            for c in range(COLS):
                rect = pygame.Rect(MAP_OFFSET_X + c*GRID_SIZE, MAP_OFFSET_Y + r*GRID_SIZE, GRID_SIZE, GRID_SIZE)
                if (c, r) in PATH: pygame.draw.rect(screen, (100, 80, 60), rect)
                else: 
                    pygame.draw.rect(screen, (60, 140, 60), rect)
                    pygame.draw.rect(screen, (50, 120, 50), rect, 1)

        # Draw Base
        bx, by = MAP_OFFSET_X + PATH[-1][0]*GRID_SIZE, MAP_OFFSET_Y + PATH[-1][1]*GRID_SIZE
        pygame.draw.rect(screen, DARK_GRAY, (bx, by-20, GRID_SIZE, GRID_SIZE+20))
        draw_text(screen, "BASE", font, WHITE, bx+GRID_SIZE//2, by, center=True)

        # Draw Traps & Towers
        for (gx, gy) in game.traps:
            pygame.draw.rect(screen, RED, (MAP_OFFSET_X + gx*GRID_SIZE+10, MAP_OFFSET_Y + gy*GRID_SIZE+10, 30, 30))
        for t in game.towers:
            color = CYAN if "Ice" in t.template.name else (DARK_GRAY if "Cannon" in t.template.name else BLUE)
            pygame.draw.circle(screen, color, (t.x, t.y), 20)
            pygame.draw.circle(screen, BLACK, (t.x, t.y), 20, 2)
            
        # Draw Enemies & Lasers
        for e in game.enemies:
            pygame.draw.circle(screen, e.color, (int(e.x), int(e.y)), e.radius)
            pygame.draw.rect(screen, RED, (e.x-15, e.y-20, 30, 5))
            pygame.draw.rect(screen, GREEN, (e.x-15, e.y-20, 30 * (e.hp/e.max_hp), 5))
        for lx1, ly1, lx2, ly2 in game.lasers:
            pygame.draw.line(screen, GOLD, (lx1, ly1), (lx2, ly2), 3)

        # UI Overlay
        draw_text(screen, f"Base HP: {game.base_hp}/{game.base_max_hp}", font, GREEN, 20, 20)
        draw_text(screen, f"Gold: {game.gold}", font, GOLD, 20, 50)
        draw_text(screen, f"Wave: {game.wave}/{game.max_waves}", font, WHITE, 20, 80)
        draw_text(screen, f"Energy: {game.energy}/{game.max_energy}", large_font, BLUE, 20, HEIGHT - 180)
        draw_text(screen, f"Draw Pile: {len(game.draw_pile)}", font, WHITE, 20, HEIGHT - 100)
        draw_text(screen, f"Discard Pile: {len(game.discard_pile)}", font, WHITE, WIDTH - 160, HEIGHT - 100)

        if game.battle_phase == "PLANNING":
            pygame.draw.rect(screen, GREEN, (WIDTH-150, 20, 130, 40), border_radius=5)
            draw_text(screen, "Start Wave", font, BLACK, WIDTH-140, 30)
            
            # Draw Hand
            hand_x = WIDTH//2 - (len(game.hand)*130)//2
            for i, card in enumerate(game.hand):
                if card != game.dragging_card:
                    cx, cy = hand_x + i * 130, HEIGHT - 180
                    is_hover = cx <= game.mouse_pos[0] <= cx+120 and cy <= game.mouse_pos[1] <= cy+160
                    draw_card(screen, card, cx, cy, is_hover)
                    
            if game.dragging_card:
                draw_card(screen, game.dragging_card, game.mouse_pos[0]-60, game.mouse_pos[1]-80, True)

    elif game.mode == "REWARD":
        draw_text(screen, "VICTORY! CHOOSE A REWARD", large_font, WHITE, WIDTH//2, 100, center=True)
        for i, card in enumerate(game.reward_choices):
            draw_card(screen, card, 300 + i * 150, 300)
        pygame.draw.rect(screen, GRAY, (WIDTH//2-50, 550, 100, 40), border_radius=5)
        draw_text(screen, "SKIP", font, BLACK, WIDTH//2, 570, center=True)

    elif game.mode == "SHOP":
        draw_text(screen, f"SHOP - Gold: {game.gold}", large_font, GOLD, WIDTH//2, 100, center=True)
        draw_text(screen, "Cost: 60 Gold each", font, WHITE, WIDTH//2, 150, center=True)
        shop_items = get_all_cards()[:4]
        for i, card in enumerate(shop_items):
            draw_card(screen, card, 200 + i * 150, 300)
        pygame.draw.rect(screen, RED, (400, 500, 200, 50), border_radius=5)
        draw_text(screen, "LEAVE SHOP", font, WHITE, 500, 525, center=True)

    elif game.mode == "CAMPFIRE":
        draw_text(screen, "CAMPFIRE", large_font, GOLD, WIDTH//2, 100, center=True)
        pygame.draw.rect(screen, GREEN, (300, 300, 150, 100), border_radius=10)
        draw_text(screen, "REST", font, BLACK, 375, 340, center=True)
        draw_text(screen, "+30 HP", font, BLACK, 375, 360, center=True)
        pygame.draw.rect(screen, BLUE, (550, 300, 150, 100), border_radius=10)
        draw_text(screen, "SMITH", font, BLACK, 625, 340, center=True)
        draw_text(screen, "Upgrade Random", font, BLACK, 625, 360, center=True)

    elif game.mode == "GAMEOVER":
        draw_text(screen, "GAME OVER", large_font, RED, WIDTH//2, HEIGHT//2, center=True)
        draw_text(screen, "Click to restart", font, WHITE, WIDTH//2, HEIGHT//2 + 50, center=True)

    elif game.mode == "WIN":
        draw_text(screen, "YOU DEFENDED THE SPIRE!", large_font, GREEN, WIDTH//2, HEIGHT//2, center=True)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()