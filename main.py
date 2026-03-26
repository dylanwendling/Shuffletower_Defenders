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
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)
DARK_GRAY = (50, 50, 50)
RED = (220, 50, 50)
GREEN = (50, 220, 50)
BLUE = (50, 150, 255)
GOLD = (255, 215, 0)
BROWN = (139, 69, 19)
PURPLE = (150, 50, 200)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Spire Defense: Roguelike TD")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 20, bold=True)
large_font = pygame.font.SysFont("Arial", 40, bold=True)

# --- GAME DATA & CLASSES ---

# The hardcoded winding path for enemies (grid coordinates)
PATH = [(0,2), (1,2), (2,2), (3,2), (3,3), (3,4), (3,5), (4,5), (5,5), 
        (6,5), (7,5), (7,4), (7,3), (8,3), (9,3), (10,3), (11,3), (12,3), 
        (12,4), (12,5), (12,6), (12,7), (13,7), (14,7), (15,7)]

class CardTemplate:
    def __init__(self, name, cost, type, damage=0, range=0, fire_rate=0, description=""):
        self.name = name
        self.cost = cost
        self.type = type # "TOWER", "TRAP", "SKILL"
        self.damage = damage
        self.range = range
        self.fire_rate = fire_rate
        self.description = description

CARD_DATABASE = [
    CardTemplate("Arrow Tower", 1, "TOWER", damage=10, range=120, fire_rate=60, description="Basic fast tower."),
    CardTemplate("Cannon", 2, "TOWER", damage=30, range=100, fire_rate=120, description="Heavy dmg, slow."),
    CardTemplate("Spike Trap", 1, "TRAP", damage=50, description="Place on path. Damages passing enemies."),
    CardTemplate("Repair", 1, "SKILL", description="Heals base by 20 HP.")
]

class Enemy:
    def __init__(self, enemy_type, hp_scale=1.0):
        self.type = enemy_type
        if type == "BOSS":
            self.max_hp = 300 * hp_scale
            self.speed = 0.5
            self.color = PURPLE
            self.radius = 20
            self.reward = 25
        elif type == "FAST":
            self.max_hp = 20 * hp_scale
            self.speed = 2.0
            self.color = RED
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
        self.color = BLUE if template.name == "Arrow Tower" else DARK_GRAY

class GameState:
    def __init__(self):
        self.mode = "MENU" # MENU, MAP, BATTLE, REWARD, SHOP, GAMEOVER, WIN
        self.deck = [CARD_DATABASE[0], CARD_DATABASE[0], CARD_DATABASE[0], CARD_DATABASE[1], CARD_DATABASE[2], CARD_DATABASE[3]]
        self.draw_pile = []
        self.discard_pile = []
        self.hand = []
        
        self.base_max_hp = 100
        self.base_hp = self.base_max_hp
        self.gold = 50
        
        # Map Progression
        self.nodes = ["BATTLE", "BATTLE", "REWARD", "SHOP", "BATTLE", "BOSS"]
        self.current_node = 0
        
        # Battle State
        self.towers = []
        self.traps = {} # (gx, gy) -> HP
        self.enemies = []
        self.max_energy = 3
        self.energy = self.max_energy
        self.wave = 1
        self.battle_phase = "PLANNING" # PLANNING, ACTION
        self.spawn_timer = 0
        self.enemies_to_spawn = []
        self.lasers = [] # Visual effects for tower shots

        self.dragging_card = None
        self.mouse_pos = (0,0)
        self.reward_choices = []

    def start_run(self):
        self.base_hp = self.base_max_hp
        self.gold = 50
        self.current_node = 0
        self.mode = "MAP"

    def enter_battle(self, is_boss=False):
        self.towers.clear()
        self.traps.clear()
        self.enemies.clear()
        self.wave = 1
        self.is_boss = is_boss
        self.init_deck_for_battle()
        self.start_turn()
        self.mode = "BATTLE"

    def init_deck_for_battle(self):
        self.draw_pile = list(self.deck)
        random.shuffle(self.draw_pile)
        self.discard_pile.clear()
        self.hand.clear()

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
        self.discard_pile.extend(self.hand)
        self.hand.clear()
        self.draw_cards(5)
        
        # Prep wave
        count = 5 + self.wave * 2
        hp_scale = 1.0 + (self.current_node * 0.2)
        self.enemies_to_spawn = []
        if self.is_boss and self.wave == 3: # Boss on wave 3
            self.enemies_to_spawn.append(Enemy("BOSS", hp_scale))
        else:
            for _ in range(count):
                type = "FAST" if random.random() < 0.3 else "BASIC"
                self.enemies_to_spawn.append(Enemy(type, hp_scale))

    def play_card(self, card, gx, gy):
        if self.energy < card.cost: return False
        
        if card.type == "TOWER":
            if (gx, gy) in PATH or any(t.gx == gx and t.gy == gy for t in self.towers):
                return False
            self.towers.append(Tower(gx, gy, card))
        elif card.type == "TRAP":
            if (gx, gy) not in PATH: return False
            self.traps[(gx, gy)] = card.damage
        elif card.type == "SKILL":
            if card.name == "Repair":
                self.base_hp = min(self.base_max_hp, self.base_hp + 20)
                
        self.energy -= card.cost
        self.hand.remove(card)
        self.discard_pile.append(card)
        return True

    def update_battle(self):
        if self.battle_phase == "ACTION":
            # Spawn enemies
            if self.enemies_to_spawn:
                self.spawn_timer -= 1
                if self.spawn_timer <= 0:
                    self.enemies.append(self.enemies_to_spawn.pop(0))
                    self.spawn_timer = 40
            
            # Move enemies
            for e in self.enemies[:]:
                reached_end = e.move()
                
                # Check traps
                egx, egy = int((e.x - MAP_OFFSET_X)//GRID_SIZE), int((e.y - MAP_OFFSET_Y)//GRID_SIZE)
                if (egx, egy) in self.traps:
                    e.hp -= self.traps[(egx, egy)]
                    del self.traps[(egx, egy)] # single use trap
                
                if e.hp <= 0:
                    self.gold += e.reward
                    self.enemies.remove(e)
                elif reached_end:
                    self.base_hp -= 5
                    self.enemies.remove(e)
                    if self.base_hp <= 0:
                        self.mode = "GAMEOVER"
            
            # Towers fire
            self.lasers.clear()
            for t in self.towers:
                if t.cooldown > 0: t.cooldown -= 1
                if t.cooldown <= 0:
                    # find target
                    in_range = [e for e in self.enemies if math.hypot(e.x - t.x, e.y - t.y) <= t.template.range]
                    if in_range:
                        target = in_range[0] # target first
                        target.hp -= t.template.damage
                        t.cooldown = t.template.fire_rate
                        self.lasers.append((t.x, t.y, target.x, target.y))
                        if target.hp <= 0 and target in self.enemies:
                            self.gold += target.reward
                            self.enemies.remove(target)

            # Wave clear condition
            if not self.enemies and not self.enemies_to_spawn:
                if self.is_boss and self.wave == 3:
                    self.mode = "WIN"
                else:
                    self.wave += 1
                    if self.wave > 3: # 3 waves per standard battle
                        self.current_node += 1
                        self.mode = "MAP"
                    else:
                        self.start_turn()

    def generate_rewards(self):
        self.reward_choices = random.sample(CARD_DATABASE, 3)

# --- RENDERING FUNCTIONS ---

def draw_text(surf, text, font, color, x, y, center=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    surf.blit(img, rect)

def draw_card(surf, card, x, y, is_hover=False):
    rect = pygame.Rect(x, y, 120, 160)
    pygame.draw.rect(surf, WHITE, rect, border_radius=10)
    pygame.draw.rect(surf, GOLD if is_hover else BLACK, rect, 3, border_radius=10)
    
    draw_text(surf, card.name, font, BLACK, x+10, y+10)
    draw_text(surf, f"Cost: {card.cost}", font, BLUE, x+10, y+35)
    draw_text(surf, card.type, font, GRAY, x+10, y+60)
    
    desc_words = card.description.split()
    line_y, line = y + 90, ""
    for word in desc_words:
        if font.size(line + word)[0] > 100:
            draw_text(surf, line, font, BLACK, x+10, line_y)
            line_y += 20; line = word + " "
        else:
            line += word + " "
    draw_text(surf, line, font, BLACK, x+10, line_y)

def draw_grid(surf):
    for r in range(ROWS):
        for c in range(COLS):
            rect = pygame.Rect(MAP_OFFSET_X + c*GRID_SIZE, MAP_OFFSET_Y + r*GRID_SIZE, GRID_SIZE, GRID_SIZE)
            if (c, r) in PATH:
                pygame.draw.rect(surf, (100, 80, 60), rect) # Path color
            else:
                pygame.draw.rect(surf, (60, 140, 60), rect) # Grass color
                pygame.draw.rect(surf, (50, 120, 50), rect, 1)

def draw_base(surf):
    last_cx, last_cy = PATH[-1]
    bx = MAP_OFFSET_X + last_cx * GRID_SIZE
    by = MAP_OFFSET_Y + last_cy * GRID_SIZE
    pygame.draw.rect(surf, DARK_GRAY, (bx, by-20, GRID_SIZE, GRID_SIZE+20))
    draw_text(surf, "BASE", font, WHITE, bx+5, by)

# --- MAIN LOOP ---

game = GameState()
running = True

while running:
    game.mouse_pos = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if game.mode == "MENU":
                    game.start_run()
                elif game.mode == "MAP":
                    if game.nodes[game.current_node] == "BATTLE":
                        game.enter_battle()
                    elif game.nodes[game.current_node] == "BOSS":
                        game.enter_battle(is_boss=True)
                    else:
                        game.mode = game.nodes[game.current_node]
                
                elif game.mode == "BATTLE":
                    if game.battle_phase == "PLANNING":
                        # Check Card Click
                        hand_start_x = WIDTH//2 - (len(game.hand)*130)//2
                        for i, card in enumerate(game.hand):
                            cx = hand_start_x + i * 130
                            cy = HEIGHT - 180
                            if cx <= game.mouse_pos[0] <= cx+120 and cy <= game.mouse_pos[1] <= cy+160:
                                game.dragging_card = card
                                break
                        
                        # Check Start Wave button
                        if WIDTH-150 <= game.mouse_pos[0] <= WIDTH-20 and 20 <= game.mouse_pos[1] <= 60:
                            game.battle_phase = "ACTION"
                
                elif game.mode == "REWARD":
                    if not game.reward_choices: game.generate_rewards()
                    for i, card in enumerate(game.reward_choices):
                        cx = 300 + i * 150
                        if cx <= game.mouse_pos[0] <= cx+120 and 300 <= game.mouse_pos[1] <= 460:
                            game.deck.append(card)
                            game.current_node += 1
                            game.mode = "MAP"
                            game.reward_choices.clear()
                
                elif game.mode == "SHOP":
                    # Simple buy logic
                    for i, card in enumerate(CARD_DATABASE):
                        cx = 200 + i * 150
                        if cx <= game.mouse_pos[0] <= cx+120 and 300 <= game.mouse_pos[1] <= 460:
                            if game.gold >= 50:
                                game.gold -= 50
                                game.deck.append(card)
                    
                    # Leave shop
                    if 400 <= game.mouse_pos[0] <= 600 and 500 <= game.mouse_pos[1] <= 550:
                        game.current_node += 1
                        game.mode = "MAP"

                elif game.mode in ["GAMEOVER", "WIN"]:
                    game = GameState() # Reset game
                    
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and game.dragging_card:
                # Drop card on grid
                if MAP_OFFSET_X <= game.mouse_pos[0] <= MAP_OFFSET_X + COLS*GRID_SIZE and \
                   MAP_OFFSET_Y <= game.mouse_pos[1] <= MAP_OFFSET_Y + ROWS*GRID_SIZE:
                    gx = (game.mouse_pos[0] - MAP_OFFSET_X) // GRID_SIZE
                    gy = (game.mouse_pos[1] - MAP_OFFSET_Y) // GRID_SIZE
                    game.play_card(game.dragging_card, gx, gy)
                
                game.dragging_card = None

    # --- UPDATE ---
    game.update_battle()

    # --- DRAW ---
    screen.fill((30, 30, 40))

    if game.mode == "MENU":
        draw_text(screen, "SPIRE DEFENSE", large_font, WHITE, WIDTH//2, HEIGHT//3, center=True)
        draw_text(screen, "Click anywhere to start", font, GRAY, WIDTH//2, HEIGHT//2, center=True)
        
    elif game.mode == "MAP":
        draw_text(screen, "MAP PROGRESSION", large_font, WHITE, WIDTH//2, 100, center=True)
        for i, node in enumerate(game.nodes):
            color = GREEN if i == game.current_node else GRAY
            draw_text(screen, node, font, color, WIDTH//2, 200 + i*50, center=True)
        draw_text(screen, "Click to advance", font, WHITE, WIDTH//2, HEIGHT - 100, center=True)
        
    elif game.mode == "BATTLE":
        draw_grid(screen)
        draw_base(screen)
        
        # Traps
        for (gx, gy) in game.traps:
            pygame.draw.rect(screen, RED, (MAP_OFFSET_X + gx*GRID_SIZE+10, MAP_OFFSET_Y + gy*GRID_SIZE+10, 30, 30))
            
        # Towers
        for t in game.towers:
            pygame.draw.circle(screen, t.color, (t.x, t.y), 20)
            pygame.draw.circle(screen, BLACK, (t.x, t.y), 20, 2)
            
        # Enemies
        for e in game.enemies:
            pygame.draw.circle(screen, e.color, (int(e.x), int(e.y)), e.radius)
            # HP Bar
            pygame.draw.rect(screen, RED, (e.x-15, e.y-20, 30, 5))
            pygame.draw.rect(screen, GREEN, (e.x-15, e.y-20, 30 * (e.hp/e.max_hp), 5))

        # Lasers (visuals)
        for lx1, ly1, lx2, ly2 in game.lasers:
            pygame.draw.line(screen, GOLD, (lx1, ly1), (lx2, ly2), 3)

        # UI Overlay
        draw_text(screen, f"Base HP: {game.base_hp}/{game.base_max_hp}", font, GREEN, 20, 20)
        draw_text(screen, f"Gold: {game.gold}", font, GOLD, 20, 50)
        draw_text(screen, f"Wave: {game.wave}/3", font, WHITE, 20, 80)
        draw_text(screen, f"Energy: {game.energy}/{game.max_energy}", large_font, BLUE, 20, HEIGHT - 180)
        draw_text(screen, f"Deck: {len(game.draw_pile)}", font, WHITE, 20, HEIGHT - 100)
        draw_text(screen, f"Discard: {len(game.discard_pile)}", font, WHITE, WIDTH - 120, HEIGHT - 100)

        if game.battle_phase == "PLANNING":
            pygame.draw.rect(screen, GREEN, (WIDTH-150, 20, 130, 40), border_radius=5)
            draw_text(screen, "Start Wave", font, BLACK, WIDTH-140, 28)
            
            # Draw Hand
            hand_start_x = WIDTH//2 - (len(game.hand)*130)//2
            for i, card in enumerate(game.hand):
                if card != game.dragging_card:
                    cx = hand_start_x + i * 130
                    cy = HEIGHT - 180
                    is_hover = cx <= game.mouse_pos[0] <= cx+120 and cy <= game.mouse_pos[1] <= cy+160
                    draw_card(screen, card, cx, cy, is_hover)
                    
            if game.dragging_card:
                draw_card(screen, game.dragging_card, game.mouse_pos[0]-60, game.mouse_pos[1]-80, True)

    elif game.mode == "REWARD":
        draw_text(screen, "CHOOSE A CARD REWARD", large_font, WHITE, WIDTH//2, 100, center=True)
        if not game.reward_choices: game.generate_rewards()
        for i, card in enumerate(game.reward_choices):
            draw_card(screen, card, 300 + i * 150, 300)
            
    elif game.mode == "SHOP":
        draw_text(screen, f"SHOP - Gold: {game.gold}", large_font, GOLD, WIDTH//2, 100, center=True)
        draw_text(screen, "Cost: 50 Gold each", font, WHITE, WIDTH//2, 150, center=True)
        for i, card in enumerate(CARD_DATABASE):
            draw_card(screen, card, 200 + i * 150, 300)
        pygame.draw.rect(screen, RED, (400, 500, 200, 50), border_radius=5)
        draw_text(screen, "LEAVE SHOP", font, WHITE, 500, 525, center=True)

    elif game.mode == "GAMEOVER":
        draw_text(screen, "GAME OVER", large_font, RED, WIDTH//2, HEIGHT//2, center=True)
        draw_text(screen, "Click to restart", font, WHITE, WIDTH//2, HEIGHT//2 + 50, center=True)

    elif game.mode == "WIN":
        draw_text(screen, "YOU DEFENDED THE SPIRE!", large_font, GREEN, WIDTH//2, HEIGHT//2, center=True)
        draw_text(screen, "Click to play again", font, WHITE, WIDTH//2, HEIGHT//2 + 50, center=True)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()