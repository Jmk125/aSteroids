import pygame
import sys
import math
import random
import sqlite3
import os
from datetime import datetime
from pygame import joystick

# Initialize pygame
pygame.init()

# Initialize sound mixer
pygame.mixer.pre_init(44100, -16, 2, 512)  # Setup for low sound latency
pygame.mixer.init()

# Load sound effects
sounds = {
    'shoot': pygame.mixer.Sound('sounds/shoot.wav'),
    'explosion_large': pygame.mixer.Sound('sounds/explosion_large.wav'),
    'explosion_medium': pygame.mixer.Sound('sounds/explosion_medium.wav'),
    'explosion_small': pygame.mixer.Sound('sounds/explosion_small.wav'),
    'player_explosion': pygame.mixer.Sound('sounds/player_explosion.wav'),
    'ufo': pygame.mixer.Sound('sounds/ufo.wav'),
    'ufo_shoot': pygame.mixer.Sound('sounds/ufo_shoot.wav'),
    'powerup': pygame.mixer.Sound('sounds/powerup.wav'),
    'laser': pygame.mixer.Sound('sounds/laser.wav'),
    'nuke': pygame.mixer.Sound('sounds/nuke.wav'),
    'thrust': pygame.mixer.Sound('sounds/thrust.wav'),
    'menu_select': pygame.mixer.Sound('sounds/menu_select.wav'),
    'menu_change': pygame.mixer.Sound('sounds/menu_change.wav'),
    'nuke_fire': pygame.mixer.Sound('sounds/nuke_fire.wav'),
}

# Sound management functions
def play_sound(sound_name, loops=0):
    """Play a sound by name with optional looping"""
    if sound_name in sounds:
        sounds[sound_name].play(loops)
        
def stop_sound(sound_name):
    """Stop a specific sound"""
    if sound_name in sounds:
        sounds[sound_name].stop()
        
def stop_all_sounds():
    """Stop all currently playing sounds"""
    pygame.mixer.stop()

# Set volume levels for different sound categories
for sound in ['shoot', 'ufo_shoot', 'laser', 'thrust']:
    sounds[sound].set_volume(0.4)  # Slightly lower volume for frequent sounds

for sound in ['explosion_large', 'explosion_medium', 'explosion_small', 'player_explosion', 'powerup', 'nuke']:
    sounds[sound].set_volume(0.6)  # Medium volume for effects

for sound in ['menu_select', 'menu_change']:
    sounds[sound].set_volume(0.5)  # Menu sounds

# Get the actual display resolution
info = pygame.display.Info()
DISPLAY_WIDTH, DISPLAY_HEIGHT = info.current_w, info.current_h

# Game logic uses pixel-perfect dimensions that match your actual screen
# but maintain the 16:9 aspect ratio
target_width = DISPLAY_WIDTH
target_height = int(DISPLAY_WIDTH * 9 / 16)

if target_height > DISPLAY_HEIGHT:
    # If height is too large, calculate based on height instead
    target_height = DISPLAY_HEIGHT
    target_width = int(DISPLAY_HEIGHT * 16 / 9)

WIDTH, HEIGHT = target_width, target_height

# Calculate offsets to center the game on screen
OFFSET_X = (DISPLAY_WIDTH - WIDTH) // 2
OFFSET_Y = (DISPLAY_HEIGHT - HEIGHT) // 2

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
PURPLE = (128, 0, 128)
YELLOW = (255, 255, 0)
GREY = (192, 192, 192)
CYAN = (0, 255, 255)  # Color for player 2
FPS = 60

# Game states
TITLE_SCREEN = 0
GAME_PLAYING = 1
GAME_OVER = 2
HIGH_SCORES = 3
NAME_INPUT = 4

# Game modes
SINGLE_PLAYER = 0
COOPERATIVE = 1

# Power-up spawn rate (in seconds)
POWERUP_SPAWN_RATE = 10

# After-image settings for invincibility
AFTERIMAGE_FREQUENCY = 5  # Frames between each after-image (lower = more images)
AFTERIMAGE_DURATION = 30  # How long after-images last in frames

# Controller settings
CONTROLLER_DEADZONE = 0.2  # Analog stick deadzone
CONTROLLER_REPEAT_DELAY = 200  # Milliseconds

# Set up the display
screen = pygame.display.set_mode((DISPLAY_WIDTH, DISPLAY_HEIGHT), pygame.FULLSCREEN)
game_surface = pygame.Surface((WIDTH, HEIGHT))
pygame.display.set_caption("aSteroids")
clock = pygame.time.Clock()

# Load fonts
font = pygame.font.Font(None, 36)
title_font = pygame.font.Font(None, 72)
big_font = pygame.font.Font(None, 48)

def init_controllers():
    """Initialize all connected controllers"""
    joystick.init()
    controllers = []
    
    # Get count of joysticks
    joystick_count = joystick.get_count()
    
    # Initialize all connected joysticks
    for i in range(joystick_count):
        controller = joystick.Joystick(i)
        controller.init()
        controllers.append(controller)
        print(f"Controller {i} initialized: {controller.get_name()}")
        
    return controllers

# Database setup
def init_database():
    """Initialize the high scores database"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'asteroids_scores.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table if it doesn't exist - add game_mode column
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS high_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        score INTEGER NOT NULL,
        date TEXT NOT NULL,
        game_mode TEXT DEFAULT 'single'
    )
    ''')
    
    # Check if game_mode column exists, add it if it doesn't
    cursor.execute("PRAGMA table_info(high_scores)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    if 'game_mode' not in column_names:
        cursor.execute("ALTER TABLE high_scores ADD COLUMN game_mode TEXT DEFAULT 'single'")
    
    conn.commit()
    conn.close()
    
    return db_path

def save_score(db_path, name, score, game_mode='single'):
    """Save a score to the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get current date and time
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("INSERT INTO high_scores (name, score, date, game_mode) VALUES (?, ?, ?, ?)",
                  (name, score, date, game_mode))
    
    conn.commit()
    conn.close()

def get_high_scores(db_path, limit=10):
    """Get the top scores from the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, score, date, game_mode FROM high_scores ORDER BY score DESC LIMIT ?", (limit,))
    scores = cursor.fetchall()
    
    conn.close()
    return scores

class TextInput:
    def __init__(self, x, y, width, font, max_length=10):
        self.rect = pygame.Rect(x, y, width, font.get_height() + 10)
        self.color = WHITE
        self.text = ""
        self.font = font
        self.active = False
        self.max_length = max_length
        self.cursor_visible = True
        self.cursor_timer = 0
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            # No need to convert mouse position since we're at native resolution
            self.active = self.rect.collidepoint((event.pos[0] - OFFSET_X, event.pos[1] - OFFSET_Y))
                
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                return self.text
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif len(self.text) < self.max_length and event.unicode.isprintable():
                self.text += event.unicode
                
        return None
        
    def update(self):
        # Blink cursor
        self.cursor_timer += 1
        if self.cursor_timer > 30:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
        
    def draw(self):
        # Draw background
        pygame.draw.rect(game_surface, BLACK, self.rect)
        pygame.draw.rect(game_surface, self.color, self.rect, 2)
        
        # Draw text
        if self.text:
            text_surface = self.font.render(self.text, True, self.color)
            game_surface.blit(text_surface, (self.rect.x + 5, self.rect.y + 5))
            
        # Draw cursor
        if self.active and self.cursor_visible:
            cursor_pos = self.font.size(self.text)[0] + self.rect.x + 5
            pygame.draw.line(game_surface, self.color, 
                            (cursor_pos, self.rect.y + 5),
                            (cursor_pos, self.rect.y + self.rect.height - 5),
                            2)

class Button:
    def __init__(self, x, y, width, height, text, font, color=WHITE, hover_color=GREEN, selected_color=GREEN):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.color = color
        self.hover_color = hover_color
        self.selected_color = selected_color
        self.is_hovered = False
        self.is_selected = False
        
    def draw(self):
        # Draw button
        color = self.selected_color if self.is_selected else (self.hover_color if self.is_hovered else self.color)
        pygame.draw.rect(game_surface, BLACK, self.rect)
        pygame.draw.rect(game_surface, color, self.rect, 2)
        
        # Draw text
        text_surface = self.font.render(self.text, True, color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        game_surface.blit(text_surface, text_rect)
        
        # Draw selection indicator if selected (triangle)
        if self.is_selected:
            triangle_points = [
                (self.rect.x - 20, self.rect.centery),
                (self.rect.x - 10, self.rect.centery - 5),
                (self.rect.x - 10, self.rect.centery + 5)
            ]
            pygame.draw.polygon(game_surface, self.selected_color, triangle_points)
        
    def check_hover(self, pos):
        # Adjust for offset
        game_x = pos[0] - OFFSET_X
        game_y = pos[1] - OFFSET_Y
        
        self.is_hovered = self.rect.collidepoint((game_x, game_y))
        return self.is_hovered
        
    def is_clicked(self, pos, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Adjust for offset
            game_x = pos[0] - OFFSET_X
            game_y = pos[1] - OFFSET_Y
            
            if self.rect.collidepoint((game_x, game_y)):
                return True
        return False

class AfterImage:
    def __init__(self, points, position, rotation, color=PURPLE):
        self.points = points.copy()  # Copy the ship points
        self.position = position.copy()  # Position remains fixed
        self.rotation = rotation
        self.color = color
        self.lifetime = AFTERIMAGE_DURATION
        self.max_lifetime = AFTERIMAGE_DURATION
        
    def update(self):
        self.lifetime -= 1
        return self.lifetime <= 0
        
    def draw(self):
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        
        # Transform ship points to screen coordinates
        transformed_points = []
        for point in self.points:
            transformed_points.append((
                self.position[0] + point[0],
                self.position[1] + point[1]
            ))
            
        pygame.draw.polygon(surf, (*self.color, alpha), transformed_points)
        game_surface.blit(surf, (0, 0))

class PowerUp:
    """Represents a power-up in the game."""
    POWERUP_TYPES = ['invincibility', 'laser_beam', 'nuclear_bomb', 'rapid_fire']
    COLORS = {'invincibility': PURPLE, 'laser_beam': YELLOW, 'nuclear_bomb': GREY, 'rapid_fire': RED}

    def __init__(self, x, y, powerup_type=None):
        self.x = x
        self.y = y
        self.velocity = [random.uniform(-1, 1), random.uniform(-1, 1)]
        self.radius = 10
        self.type = powerup_type if powerup_type else random.choice(self.POWERUP_TYPES)
        self.color = self.COLORS[self.type]
        self.lifetime = 500  # Power-up stays on screen for this many frames
        self.pulse_size = 0
        self.growing = True

    def draw(self):
        # Draw main powerup circle
        pygame.draw.circle(game_surface, self.color, (int(self.x), int(self.y)), self.radius)
        
        # Draw pulsing outer ring
        pygame.draw.circle(game_surface, self.color, (int(self.x), int(self.y)), 
                          self.radius + self.pulse_size, 1)
        
        # Draw icon inside based on powerup type
        if self.type == 'invincibility':
            # Shield icon
            pygame.draw.circle(game_surface, WHITE, (int(self.x), int(self.y)), self.radius-4, 1)
        elif self.type == 'laser_beam':
            # Beam icon
            pygame.draw.line(game_surface, WHITE, 
                           (self.x-self.radius+3, self.y), 
                           (self.x+self.radius-3, self.y), 2)
        elif self.type == 'nuclear_bomb':
            # Bomb icon
            pygame.draw.circle(game_surface, WHITE, (int(self.x), int(self.y)), self.radius-4)
            pygame.draw.line(game_surface, self.color, 
                           (self.x, self.y-self.radius+3), 
                           (self.x, self.y-3), 2)
        elif self.type == 'rapid_fire':
            # Bullet icon
            for i in range(3):
                pygame.draw.circle(game_surface, WHITE, 
                                 (int(self.x-4+i*4), int(self.y)), 2)

    def update(self):
        # Update position
        self.x += self.velocity[0]
        self.y += self.velocity[1]
        
        # Wrap around screen edges
        if self.x < 0:
            self.x = WIDTH
        elif self.x > WIDTH:
            self.x = 0
            
        if self.y < 0:
            self.y = HEIGHT
        elif self.y > HEIGHT:
            self.y = 0
            
        # Update pulse effect
        if self.growing:
            self.pulse_size += 0.2
            if self.pulse_size > 4:
                self.growing = False
        else:
            self.pulse_size -= 0.2
            if self.pulse_size < 0:
                self.growing = True
        
        # Update lifetime
        self.lifetime -= 1
        return self.lifetime <= 0  # Return True if the power-up expires

    def check_collision(self, player):
        distance = math.sqrt((self.x - player.position[0])**2 + (self.y - player.position[1])**2)
        return distance < self.radius + player.radius

class Bullet:
    def __init__(self, x, y, vx, vy, is_nuke=False, player_id=0):
        self.position = [x, y]
        self.velocity = [vx, vy]
        self.radius = 2
        self.lifetime = 90  # Adjusted for larger play area
        self.is_nuke = is_nuke
        self.color = GREY if is_nuke else (WHITE if player_id == 0 else CYAN)
        self.prev_position = [x - vx, y - vy]  # Store previous position for continuous collision detection
        self.player_id = player_id  # Track which player fired the bullet
        
    def draw(self):
        if self.is_nuke:
            # Draw larger nuke bullet
            pygame.draw.circle(game_surface, self.color, (int(self.position[0]), int(self.position[1])), self.radius * 2)
            # Pulsing effect
            pulse = int(pygame.time.get_ticks() / 100) % 3
            pygame.draw.circle(game_surface, RED, (int(self.position[0]), int(self.position[1])), 
                              self.radius * 2 + pulse, 1)
        else:
            pygame.draw.circle(game_surface, self.color, (int(self.position[0]), int(self.position[1])), self.radius)
        
    def update(self):
        # Store previous position for collision detection
        self.prev_position[0] = self.position[0]
        self.prev_position[1] = self.position[1]
        
        # Update position
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        
        # Wrap around screen edges
        if self.position[0] < 0:
            self.position[0] = WIDTH
            self.prev_position[0] = WIDTH - 1  # Adjust prev_position for wrapped bullets
        elif self.position[0] > WIDTH:
            self.position[0] = 0
            self.prev_position[0] = 1  # Adjust prev_position for wrapped bullets
            
        if self.position[1] < 0:
            self.position[1] = HEIGHT
            self.prev_position[1] = HEIGHT - 1  # Adjust prev_position for wrapped bullets
        elif self.position[1] > HEIGHT:
            self.position[1] = 0
            self.prev_position[1] = 1  # Adjust prev_position for wrapped bullets
            
        # Decrease lifetime
        self.lifetime -= 1
        
    def is_dead(self):
        return self.lifetime <= 0
        
    def check_collision(self, asteroid):
        distance = math.sqrt((self.position[0] - asteroid.position[0])**2 + 
                            (self.position[1] - asteroid.position[1])**2)
        return distance < self.radius + asteroid.radius

    def line_collision(self, asteroid):
        # Calculate vector from previous to current position
        dx = self.position[0] - self.prev_position[0]
        dy = self.position[1] - self.prev_position[1]
        
        # Calculate coefficients for line-circle intersection
        a = dx*dx + dy*dy
        
        # If bullet didn't move, use standard collision check
        if a < 0.0001:
            return self.check_collision(asteroid)
        
        b = 2 * (dx * (self.prev_position[0] - asteroid.position[0]) + 
                 dy * (self.prev_position[1] - asteroid.position[1]))
        c = (self.prev_position[0] - asteroid.position[0])**2 + \
            (self.prev_position[1] - asteroid.position[1])**2 - \
            (asteroid.radius + self.radius)**2
        
        discriminant = b*b - 4*a*c
        
        if discriminant < 0:
            return False  # No intersection
        
        # Find the values of t where the line intersects the circle
        t1 = (-b + math.sqrt(discriminant)) / (2*a)
        t2 = (-b - math.sqrt(discriminant)) / (2*a)
        
        # Check if intersection is within the current frame's movement
        return (0 <= t1 <= 1) or (0 <= t2 <= 1)

class LaserBeam:
    def __init__(self, player):
        self.player = player
        self.duration = 180  # 3 seconds at 60 FPS
        self.width = 10
        self.length = 3000  # Long enough to reach across the screen
        self.color = YELLOW if player.player_id == 0 else CYAN
        
        # Calculate and store beam line segment for collision detection
        angle = math.radians(player.rotation)
        self.start_x = player.position[0]
        self.start_y = player.position[1]
        self.dx = math.cos(angle)
        self.dy = math.sin(angle)
        self.end_x = self.start_x + self.length * self.dx
        self.end_y = self.start_y + self.length * self.dy
        self.player_id = player.player_id  # Track which player fired the laser
        
    def draw(self):
        angle = math.radians(self.player.rotation)
        start_x = self.player.position[0] + self.player.radius * math.cos(angle)
        start_y = self.player.position[1] + self.player.radius * math.sin(angle)
        
        end_x = start_x + self.length * math.cos(angle)
        end_y = start_y + self.length * math.sin(angle)
        
        # Update beam position (these are used for collision detection)
        self.start_x = self.player.position[0]
        self.start_y = self.player.position[1]
        self.dx = math.cos(angle)
        self.dy = math.sin(angle)
        self.end_x = self.start_x + self.length * self.dx
        self.end_y = self.start_y + self.length * self.dy
        
        # Draw the main laser beam
        pygame.draw.line(game_surface, self.color, (start_x, start_y), (end_x, end_y), self.width)
        
        # Draw glow effect
        for i in range(1, 3):
            alpha = 150 - i * 50
            glow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(glow_surf, (self.color[0], self.color[1], self.color[2], alpha), 
                          (start_x, start_y), (end_x, end_y), self.width + i * 2)
            game_surface.blit(glow_surf, (0, 0))
            
        # Draw pulse effect along the beam
        time = pygame.time.get_ticks()
        pulse_positions = [(start_x + i * 30 * math.cos(angle), 
                          start_y + i * 30 * math.sin(angle)) 
                         for i in range(10)]
        
        for i, pos in enumerate(pulse_positions):
            if (i + time // 100) % 3 == 0:  # Makes the pulses move along the beam
                pygame.draw.circle(game_surface, WHITE, (int(pos[0]), int(pos[1])), 3)
        
    def update(self):
        self.duration -= 1
        return self.duration <= 0  # Return True when laser is finished
    
    def point_to_line_distance(self, point_x, point_y, line_x1, line_y1, line_x2, line_y2):
        """Calculate shortest distance from a point to a line segment"""
        # Line length squared
        line_length_sq = (line_x2 - line_x1)**2 + (line_y2 - line_y1)**2
        
        # If line has zero length, return distance to one endpoint
        if line_length_sq == 0:
            return math.sqrt((point_x - line_x1)**2 + (point_y - line_y1)**2)
        
        # Calculate projection of point onto line
        t = max(0, min(1, ((point_x - line_x1) * (line_x2 - line_x1) + 
                           (point_y - line_y1) * (line_y2 - line_y1)) / line_length_sq))
        
        # Find closest point on line
        proj_x = line_x1 + t * (line_x2 - line_x1)
        proj_y = line_y1 + t * (line_y2 - line_y1)
        
        # Return distance to closest point
        return math.sqrt((point_x - proj_x)**2 + (point_y - proj_y)**2)
        
    def check_collision(self, obj):
        # Get adjustment factor for small asteroids (wider collision area)
        width_factor = 2.0 if isinstance(obj, Asteroid) and obj.size == 1 else 1.0
        effective_width = self.width * width_factor
        
        # Check direct collision
        if self.point_to_line_distance(obj.position[0], obj.position[1], 
                                      self.start_x, self.start_y, 
                                      self.end_x, self.end_y) <= (obj.radius + effective_width):
            return True
            
        # For small asteroids, we need to handle screen wrapping
        if isinstance(obj, Asteroid) and obj.size == 1:
            # Create "phantom" positions for screen wrapping cases
            wrap_positions = []
            
            # Check if near screen edges
            if obj.position[0] < obj.radius * 2:
                wrap_positions.append((obj.position[0] + WIDTH, obj.position[1]))
            elif obj.position[0] > WIDTH - obj.radius * 2:
                wrap_positions.append((obj.position[0] - WIDTH, obj.position[1]))
                
            if obj.position[1] < obj.radius * 2:
                wrap_positions.append((obj.position[0], obj.position[1] + HEIGHT))
            elif obj.position[1] > HEIGHT - obj.radius * 2:
                wrap_positions.append((obj.position[0], obj.position[1] - HEIGHT))
                
            # Add diagonal wrapping cases
            if obj.position[0] < obj.radius * 2 and obj.position[1] < obj.radius * 2:
                wrap_positions.append((obj.position[0] + WIDTH, obj.position[1] + HEIGHT))
            elif obj.position[0] < obj.radius * 2 and obj.position[1] > HEIGHT - obj.radius * 2:
                wrap_positions.append((obj.position[0] + WIDTH, obj.position[1] - HEIGHT))
            elif obj.position[0] > WIDTH - obj.radius * 2 and obj.position[1] < obj.radius * 2:
                wrap_positions.append((obj.position[0] - WIDTH, obj.position[1] + HEIGHT))
            elif obj.position[0] > WIDTH - obj.radius * 2 and obj.position[1] > HEIGHT - obj.radius * 2:
                wrap_positions.append((obj.position[0] - WIDTH, obj.position[1] - HEIGHT))
                
            # Check all wrap positions
            for pos_x, pos_y in wrap_positions:
                if self.point_to_line_distance(pos_x, pos_y, 
                                             self.start_x, self.start_y, 
                                             self.end_x, self.end_y) <= (obj.radius + effective_width):
                    return True
                    
        return False

class Player:
    def __init__(self, player_id=0):
        self.position = [WIDTH // 2, HEIGHT // 2]
        self.velocity = [0, 0]
        self.acceleration = 0.2
        self.friction = 0.98
        self.max_speed = 8
        self.rotation = 0
        self.rotation_speed = 5
        self.radius = 15
        self.lives = 3
        self.is_thrusting = False
        self.player_id = player_id  # 0 = first player, 1 = second player
        self.score = 0  # Individual score for each player
        
        # Different starting positions for coop mode
        if player_id == 0:
            self.position = [WIDTH // 3, HEIGHT // 2]
        else:
            self.position = [2 * WIDTH // 3, HEIGHT // 2]
        
        # Respawn invulnerability
        self.invulnerable = False
        self.invulnerable_timer = 0
        self.respawn_invulnerable_duration = 2000  # 2 seconds
        
        # Power-up state
        self.active_powerup = None
        self.is_invincible = False  # Separate flag for invincibility
        self.powerup_timer = 0
        self.invincible_timer = 0
        self.rapid_fire_ammo = 0
        
        # After-images for invincibility
        self.after_images = []
        self.afterimage_counter = 0
        
        # Flags for one-time-use powerups
        self.has_nuke = False
        self.has_laser = False
        
    def get_ship_points(self):
        # Calculate the points of the triangle representing the ship
        angle = math.radians(self.rotation)
        cos_val = math.cos(angle)
        sin_val = math.sin(angle)
        
        # Ship points (front, back right, back left)
        points = [
            (self.radius * cos_val, self.radius * sin_val),
            (-self.radius * cos_val + self.radius/2 * math.cos(angle + math.pi/2), 
             -self.radius * sin_val + self.radius/2 * math.sin(angle + math.pi/2)),
            (-self.radius * cos_val + self.radius/2 * math.cos(angle - math.pi/2), 
             -self.radius * sin_val + self.radius/2 * math.sin(angle - math.pi/2))
        ]
        
        return points
        
    def draw(self):
        # Don't draw if respawn invulnerable and should be "blinking"
        if self.invulnerable and not self.is_invincible and pygame.time.get_ticks() % 200 < 100:
            return
            
        # Determine ship base color based on player ID
        base_color = WHITE if self.player_id == 0 else CYAN
            
        # Determine ship color based on active powerup
        if self.is_invincible:
            color = PURPLE
        elif self.has_laser:
            color = YELLOW
        elif self.has_nuke:
            # Flash grey for nuclear bomb
            if pygame.time.get_ticks() % 800 < 400:
                color = GREY
            else:
                color = base_color
        elif self.active_powerup == 'rapid_fire':
            color = RED
        else:
            color = base_color
        
        # Draw all after-images
        for after_image in self.after_images:
            after_image.draw()
            
        # Create the points of the triangle representing the ship
        angle = math.radians(self.rotation)
        cos_val = math.cos(angle)
        sin_val = math.sin(angle)
        
        # Ship points (front, back right, back left)
        ship_points = [
            (self.position[0] + self.radius * cos_val, 
             self.position[1] + self.radius * sin_val),
            (self.position[0] - self.radius * cos_val + self.radius/2 * math.cos(angle + math.pi/2), 
             self.position[1] - self.radius * sin_val + self.radius/2 * math.sin(angle + math.pi/2)),
            (self.position[0] - self.radius * cos_val + self.radius/2 * math.cos(angle - math.pi/2), 
             self.position[1] - self.radius * sin_val + self.radius/2 * math.sin(angle - math.pi/2))
        ]
        
        # Draw the ship
        pygame.draw.polygon(game_surface, color, ship_points)
        
        # Draw thrust flame if thrusting
        if self.is_thrusting:
            flame_color = BLUE if self.player_id == 0 else GREEN
            flame_points = [
                (self.position[0] - self.radius * 1.5 * cos_val, 
                 self.position[1] - self.radius * 1.5 * sin_val),
                (self.position[0] - self.radius * cos_val + self.radius/2 * math.cos(angle + math.pi/2), 
                 self.position[1] - self.radius * sin_val + self.radius/2 * math.sin(angle + math.pi/2)),
                (self.position[0] - self.radius * cos_val + self.radius/2 * math.cos(angle - math.pi/2), 
                 self.position[1] - self.radius * sin_val + self.radius/2 * math.sin(angle - math.pi/2))
            ]
            pygame.draw.polygon(game_surface, flame_color, flame_points)
        
    def rotate(self, direction):
        self.rotation += direction * self.rotation_speed
        # Keep rotation between 0 and 360
        self.rotation %= 360
        
    def thrust(self):
        self.is_thrusting = True
        # Calculate acceleration components based on ship's orientation
        angle = math.radians(self.rotation)
        self.velocity[0] += self.acceleration * math.cos(angle)
        self.velocity[1] += self.acceleration * math.sin(angle)
        
        # Limit speed
        speed = math.sqrt(self.velocity[0]**2 + self.velocity[1]**2)
        if speed > self.max_speed:
            self.velocity[0] = (self.velocity[0] / speed) * self.max_speed
            self.velocity[1] = (self.velocity[1] / speed) * self.max_speed
    
    def update(self):
        # Apply friction to slow down gradually when not thrusting
        self.velocity[0] *= self.friction
        self.velocity[1] *= self.friction
        
        # Update position based on velocity
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        
        # Wrap around the screen edges
        if self.position[0] < 0:
            self.position[0] = WIDTH
        elif self.position[0] > WIDTH:
            self.position[0] = 0
            
        if self.position[1] < 0:
            self.position[1] = HEIGHT
        elif self.position[1] > HEIGHT:
            self.position[1] = 0
        
        # Update after-image counter for invincibility effect
        if self.is_invincible:
            self.afterimage_counter += 1
            if self.afterimage_counter >= AFTERIMAGE_FREQUENCY:
                # Create a new after-image at the current position
                ship_points = self.get_ship_points()
                self.after_images.append(AfterImage(ship_points, self.position, self.rotation))
                self.afterimage_counter = 0
                
        # Update after-images
        for after_image in self.after_images[:]:
            if after_image.update():
                self.after_images.remove(after_image)
        
        # Update respawn invulnerability timer
        if self.invulnerable and not self.is_invincible:
            current_time = pygame.time.get_ticks()
            if current_time - self.invulnerable_timer > self.respawn_invulnerable_duration:
                self.invulnerable = False
                
        # Update invincibility power-up timer
        current_time = pygame.time.get_ticks()
        if self.is_invincible and current_time - self.invincible_timer > 10000:
            self.is_invincible = False
                
        # Reset thrust status (for rendering flame)
        self.is_thrusting = False
                
    def shoot(self):
        if self.has_nuke:
            # Fire nuclear bomb
            angle = math.radians(self.rotation)
            bullet_x = self.position[0] + self.radius * math.cos(angle)
            bullet_y = self.position[1] + self.radius * math.sin(angle)
            bullet_vx = 5 * math.cos(angle) + self.velocity[0] * 0.5  # Slower than regular bullets
            bullet_vy = 5 * math.sin(angle) + self.velocity[1] * 0.5
            self.has_nuke = False  # Use up the nuke
            return Bullet(bullet_x, bullet_y, bullet_vx, bullet_vy, is_nuke=True, player_id=self.player_id)
            
        elif self.has_laser:
            # Activate laser beam
            self.has_laser = False
            return "laser"  # Return a signal that we need to create a laser beam
            
        elif self.active_powerup == 'rapid_fire' and self.rapid_fire_ammo > 0:
            # Rapid fire mode
            angle = math.radians(self.rotation)
            bullet_x = self.position[0] + self.radius * math.cos(angle)
            bullet_y = self.position[1] + self.radius * math.sin(angle)
            bullet_vx = 12 * math.cos(angle) + self.velocity[0] * 0.5  # Faster than regular bullets
            bullet_vy = 12 * math.sin(angle) + self.velocity[1] * 0.5
            self.rapid_fire_ammo -= 1
            
            # If out of ammo, deactivate power-up
            if self.rapid_fire_ammo <= 0:
                self.active_powerup = None
                
            return Bullet(bullet_x, bullet_y, bullet_vx, bullet_vy, player_id=self.player_id)
        else:
            # Regular shot
            angle = math.radians(self.rotation)
            bullet_x = self.position[0] + self.radius * math.cos(angle)
            bullet_y = self.position[1] + self.radius * math.sin(angle)
            bullet_vx = 10 * math.cos(angle) + self.velocity[0] * 0.5
            bullet_vy = 10 * math.sin(angle) + self.velocity[1] * 0.5
            return Bullet(bullet_x, bullet_y, bullet_vx, bullet_vy, player_id=self.player_id)
        
    def check_collision(self, asteroid):
        # Skip collision check if invulnerable
        if self.invulnerable or self.is_invincible:
            return False
            
        # Basic circle collision
        distance = math.sqrt((self.position[0] - asteroid.position[0])**2 + 
                            (self.position[1] - asteroid.position[1])**2)
        return distance < self.radius + asteroid.radius
        
    def respawn(self):
        # Different respawn positions for coop mode
        if self.player_id == 0:
            self.position = [WIDTH // 3, HEIGHT // 2]
        else:
            self.position = [2 * WIDTH // 3, HEIGHT // 2]
            
        self.velocity = [0, 0]
        self.rotation = 0
        self.invulnerable = True
        self.invulnerable_timer = pygame.time.get_ticks()
        
    def collect_powerup(self, powerup_type):
        play_sound('powerup')
        current_time = pygame.time.get_ticks()
        
        if powerup_type == 'invincibility':
            # Invincibility can coexist with other powerups
            self.is_invincible = True
            self.invincible_timer = current_time
            self.after_images = []  # Clear previous after-images
            
        else:
            # Reset any active powerup that's not invincibility
            if self.active_powerup == 'rapid_fire':
                self.active_powerup = None
                self.rapid_fire_ammo = 0
                
            # Clear one-time use powerups
            self.has_nuke = False
            self.has_laser = False
            
            # Set the new powerup
            if powerup_type == 'laser_beam':
                self.has_laser = True
                
            elif powerup_type == 'nuclear_bomb':
                self.has_nuke = True
                
            elif powerup_type == 'rapid_fire':
                self.active_powerup = 'rapid_fire'
                self.rapid_fire_ammo = 200

class Asteroid:
    def __init__(self, x=None, y=None, size=3):
        # Size: 3 = large, 2 = medium, 1 = small
        self.size = size
        
        if size == 3:
            self.radius = 40
        elif size == 2:
            self.radius = 20
        else:
            self.radius = 10
            
        # Initialize position - if not provided, place at random edge location
        if x is None or y is None:
            # Pick a random edge
            edge = random.randint(0, 3)
            if edge == 0:  # Top
                self.position = [random.randint(0, WIDTH), 0]
            elif edge == 1:  # Right
                self.position = [WIDTH, random.randint(0, HEIGHT)]
            elif edge == 2:  # Bottom
                self.position = [random.randint(0, WIDTH), HEIGHT]
            else:  # Left
                self.position = [0, random.randint(0, HEIGHT)]
        else:
            self.position = [x, y]
        
        # Random velocity based on size (smaller asteroids move faster)
        speed_factor = 4 - size  # 1 for large, 2 for medium, 3 for small
        angle = random.uniform(0, 2 * math.pi)
        self.velocity = [
            random.uniform(0.5, 2) * speed_factor * math.cos(angle),
            random.uniform(0.5, 2) * speed_factor * math.sin(angle)
        ]
        
        # Create a jagged shape for the asteroid
        self.vertices = []
        num_vertices = random.randint(8, 12)
        for i in range(num_vertices):
            angle = 2 * math.pi * i / num_vertices
            # Random radius variation for jagged look
            rand_radius = self.radius * random.uniform(0.8, 1.2)
            x = rand_radius * math.cos(angle)
            y = rand_radius * math.sin(angle)
            self.vertices.append((x, y))
        
    def draw(self):
        # Transform relative vertices to screen coordinates
        transformed_vertices = []
        for vertex in self.vertices:
            transformed_vertices.append((
                self.position[0] + vertex[0],
                self.position[1] + vertex[1]
            ))
        pygame.draw.polygon(game_surface, WHITE, transformed_vertices, 1)
        
    def update(self):
        # Update position
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        
        # Wrap around screen edges
        if self.position[0] < -self.radius:
            self.position[0] = WIDTH + self.radius
        elif self.position[0] > WIDTH + self.radius:
            self.position[0] = -self.radius
            
        if self.position[1] < -self.radius:
            self.position[1] = HEIGHT + self.radius
        elif self.position[1] > HEIGHT + self.radius:
            self.position[1] = -self.radius
            
    def break_apart(self):
        # Return a list of smaller asteroids
        if self.size <= 1:  # Already the smallest
            return []
            
        fragments = []
        for _ in range(2):  # Create two smaller fragments
            fragments.append(Asteroid(
                self.position[0] + random.uniform(-10, 10), 
                self.position[1] + random.uniform(-10, 10),
                self.size - 1
            ))
        return fragments

class UFO:
    def __init__(self):
        # Randomly decide to start from left or right
        if random.choice([True, False]):
            self.position = [-20, random.randint(50, HEIGHT - 50)]
            self.velocity = [random.uniform(2, 4), random.uniform(-1, 1)]
        else:
            self.position = [WIDTH + 20, random.randint(50, HEIGHT - 50)]
            self.velocity = [random.uniform(-4, -2), random.uniform(-1, 1)]
            
        self.radius = 15
        self.shoot_timer = 0
        self.shoot_delay = random.randint(60, 120)  # Frames between shots
        
    def draw(self):
        # Draw UFO
        pygame.draw.ellipse(game_surface, RED, (self.position[0] - self.radius, 
                                         self.position[1] - self.radius/2,
                                         self.radius*2, self.radius))
        # Draw top dome
        pygame.draw.ellipse(game_surface, RED, (self.position[0] - self.radius/2, 
                                         self.position[1] - self.radius,
                                         self.radius, self.radius/2))
        
    def update(self, players):
        # Update position
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        
        # Bounce off top and bottom
        if self.position[1] < self.radius or self.position[1] > HEIGHT - self.radius:
            self.velocity[1] = -self.velocity[1]
            
        # Randomly adjust vertical movement occasionally
        if random.random() < 0.02:
            self.velocity[1] = random.uniform(-1, 1)
            
        # Update shoot timer
        self.shoot_timer += 1
        
        # Return None if it's not time to shoot yet
        if self.shoot_timer < self.shoot_delay:
            return None
            
        # Reset the timer
        self.shoot_timer = 0
        self.shoot_delay = random.randint(60, 120)
        
        # Pick the closest player to target
        if len(players) > 1 and all(player.lives > 0 for player in players):
            # Calculate distances to each player
            dist1 = math.sqrt((players[0].position[0] - self.position[0])**2 + 
                             (players[0].position[1] - self.position[1])**2)
            dist2 = math.sqrt((players[1].position[0] - self.position[0])**2 + 
                             (players[1].position[1] - self.position[1])**2)
            # Target the closest player
            target = players[0] if dist1 < dist2 else players[1]
        else:
            # Target the first active player or the only player
            target = next((p for p in players if p.lives > 0), players[0])
        
        # Target the player
        dx = target.position[0] - self.position[0]
        dy = target.position[1] - self.position[1]
        angle = math.atan2(dy, dx)
        
        # Add some inaccuracy
        angle += random.uniform(-0.5, 0.5)
        
        bullet_vx = 5 * math.cos(angle)
        bullet_vy = 5 * math.sin(angle)
        
        return Bullet(self.position[0], self.position[1], bullet_vx, bullet_vy)
        
    def is_off_screen(self):
        return (self.position[0] < -50 or self.position[0] > WIDTH + 50 or
                self.position[1] < -50 or self.position[1] > HEIGHT + 50)
                
    def check_collision(self, obj):
        distance = math.sqrt((self.position[0] - obj.position[0])**2 + 
                            (self.position[1] - obj.position[1])**2)
        return distance < self.radius + obj.radius

class Particle:
    def __init__(self, x, y, color=WHITE):
        self.position = [x, y]
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1, 3)
        self.velocity = [speed * math.cos(angle), speed * math.sin(angle)]
        self.lifetime = random.randint(10, 30)
        self.size = random.randint(1, 3)
        self.color = color
        
    def update(self):
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        self.lifetime -= 1
        self.velocity[0] *= 0.95
        self.velocity[1] *= 0.95
        
    def draw(self):
        alpha = int(255 * (self.lifetime / 30.0))
        color = (*self.color, alpha) if len(self.color) == 3 else (self.color[0], self.color[1], self.color[2], alpha)
        surf = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, color, (self.size, self.size), self.size)
        game_surface.blit(surf, (int(self.position[0] - self.size), int(self.position[1] - self.size)))
        
    def is_dead(self):
        return self.lifetime <= 0

def create_explosion(x, y, size, color=WHITE):
    particles = []
    num_particles = 10 if size == 1 else (20 if size == 2 else 30)
    
    for _ in range(num_particles):
        particles.append(Particle(x, y, color))
        
    return particles

def draw_title_screen(background_asteroids, selected_button_index=0):
    # Clear screen
    game_surface.fill(BLACK)
    
    # Draw background asteroids
    for asteroid in background_asteroids:
        asteroid.draw()
    
    # Draw title
    title_text = title_font.render("aSteroids", True, WHITE)
    game_surface.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, HEIGHT // 4))
    
    # Create menu buttons
    single_button = Button(WIDTH // 2 - 100, HEIGHT // 2 - 35, 200, 50, "Single Player", font)
    coop_button = Button(WIDTH // 2 - 100, HEIGHT // 2 + 35, 200, 50, "Co-op Mode", font)
    scores_button = Button(WIDTH // 2 - 100, HEIGHT // 2 + 105, 200, 50, "High Scores", font)
    
    # Set which button is selected based on the index
    single_button.is_selected = selected_button_index == 0
    coop_button.is_selected = selected_button_index == 1
    scores_button.is_selected = selected_button_index == 2
    
    # Check for mouse hover
    mouse_pos = pygame.mouse.get_pos()
    single_button.check_hover(mouse_pos)
    coop_button.check_hover(mouse_pos)
    scores_button.check_hover(mouse_pos)
    
    # Draw buttons
    single_button.draw()
    coop_button.draw()
    scores_button.draw()
    
    # Draw version number in bottom left corner
    version_text = pygame.font.Font(None, 24).render("v0.61", True, GREY)
    game_surface.blit(version_text, (10, HEIGHT - version_text.get_height() - 10))
    
    # Draw controller instructions if controllers are available
    if joystick.get_count() > 0:
        controls_text = pygame.font.Font(None, 24).render("Controller Ready", True, GREEN)
        game_surface.blit(controls_text, (WIDTH - controls_text.get_width() - 10, HEIGHT - controls_text.get_height() - 10))
    
    # Return button objects for event handling
    return single_button, coop_button, scores_button

def draw_high_scores_screen(scores, background_asteroids):
    # Clear screen
    game_surface.fill(BLACK)
    
    # Draw background asteroids
    for asteroid in background_asteroids:
        asteroid.draw()
    
    # Draw title
    title_text = big_font.render("High Scores", True, WHITE)
    game_surface.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, HEIGHT // 8))
    
    # Draw scores
    y_pos = HEIGHT // 4
    for i, (name, score, date, game_mode) in enumerate(scores):
        # Add (Coop) indicator for cooperative mode scores
        mode_indicator = " (Coop)" if game_mode == 'coop' else ""
        score_text = font.render(f"{i+1}. {name}: {score}{mode_indicator}", True, WHITE)
        date_text = font.render(date, True, GREY)
        
        game_surface.blit(score_text, (WIDTH // 2 - 150, y_pos))
        game_surface.blit(date_text, (WIDTH // 2 + 100, y_pos))
        
        y_pos += 40
    
    # Draw back button
    back_button = Button(WIDTH // 2 - 100, HEIGHT * 3 // 4, 200, 50, "Back to Menu", font)
    back_button.is_selected = True  # Always selected since it's the only button
    mouse_pos = pygame.mouse.get_pos()
    back_button.check_hover(mouse_pos)
    back_button.draw()
    
    return back_button

def draw_name_input_screen(scores, text_inputs, background_asteroids, game_mode):
    # Clear screen
    game_surface.fill(BLACK)
    
    # Draw background asteroids
    for asteroid in background_asteroids:
        asteroid.draw()
    
    # Draw title
    title_text = big_font.render("Game Over", True, RED)
    game_surface.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, HEIGHT // 6))
    
    # Draw scores
    if game_mode == SINGLE_PLAYER:
        # Single player score
        score_text = font.render(f"Your Score: {scores[0]}", True, WHITE)
        game_surface.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, HEIGHT // 3))
        
        # Draw name input prompt
        prompt_text = font.render("Enter your name:", True, WHITE)
        game_surface.blit(prompt_text, (WIDTH // 2 - prompt_text.get_width() // 2, HEIGHT // 2 - 60))
        
        # Draw text input
        text_inputs[0].update()
        text_inputs[0].draw()
    else:
        # Co-op mode, show both scores
        p1_score_text = font.render(f"Player 1 Score: {scores[0]}", True, WHITE)
        p2_score_text = font.render(f"Player 2 Score: {scores[1]}", True, CYAN)
        
        game_surface.blit(p1_score_text, (WIDTH // 2 - p1_score_text.get_width() // 2, HEIGHT // 4))
        game_surface.blit(p2_score_text, (WIDTH // 2 - p2_score_text.get_width() // 2, HEIGHT // 3))
        
        # Draw name input prompts
        p1_prompt = font.render("Player 1 name:", True, WHITE)
        p2_prompt = font.render("Player 2 name:", True, CYAN)
        
        # Position the prompts and text inputs
        game_surface.blit(p1_prompt, (WIDTH // 2 - 150, HEIGHT // 2 - 60))
        game_surface.blit(p2_prompt, (WIDTH // 2 - 150, HEIGHT // 2))
        
        # Update and draw text inputs
        text_inputs[0].update()
        text_inputs[0].draw()
        
        text_inputs[1].update()
        text_inputs[1].draw()
    
    # Draw submit button
    submit_button = Button(WIDTH // 2 - 100, HEIGHT * 2 // 3, 200, 50, "Submit Score", font)
    submit_button.is_selected = True  # Always selected since it's the only button
    mouse_pos = pygame.mouse.get_pos()
    submit_button.check_hover(mouse_pos)
    submit_button.draw()
    
    # Draw controller info
    if joystick.get_count() > 0:
        controls_text = pygame.font.Font(None, 24).render("Press START to submit", True, GREEN)
        game_surface.blit(controls_text, (WIDTH - controls_text.get_width() - 10, HEIGHT - controls_text.get_height() - 10))
    
    return submit_button

def main():
    # Initialize database
    db_path = init_database()
    
    # Create background asteroids for menus
    background_asteroids = []
    for _ in range(8):
        asteroid = Asteroid()
        asteroid.velocity = [asteroid.velocity[0] * 0.3, asteroid.velocity[1] * 0.3]  # Slower movement
        background_asteroids.append(asteroid)
    
    # Initialize controllers
    controllers = init_controllers()
    
    # Controller button press tracking
    controller_button_states = [{} for _ in range(max(1, len(controllers)))]
    controller_button_times = [{} for _ in range(max(1, len(controllers)))]
    
    # Game objects
    players = []  # Will contain Player objects
    asteroids = []
    bullets = []
    ufos = []
    particles = []
    powerups = []
    laser_beams = []  # Now a list to support multiple laser beams
    
    # Game state and variables
    game_state = TITLE_SCREEN
    game_mode = SINGLE_PLAYER  # Default to single player
    scores = [0, 0]  # Player scores
    level = 1
    selected_button_index = 0  # 0 = Single Player, 1 = Co-op, 2 = High Scores
    
    # Create text inputs for name entry
    text_input1 = TextInput(WIDTH // 2 - 150, HEIGHT // 2, 300, font)
    text_input2 = TextInput(WIDTH // 2 - 150, HEIGHT // 2 + 60, 300, font)
    text_inputs = [text_input1, text_input2]
    
    # Game timing variables
    last_shot_times = [0, 0]  # One for each player
    shot_cooldown = 250  # 250 ms between shots
    ufo_spawn_timer = pygame.time.get_ticks()
    ufo_spawn_delay = random.randint(10000, 20000)  # 10-20 seconds
    powerup_spawn_timer = pygame.time.get_ticks()
    powerup_spawn_delay = POWERUP_SPAWN_RATE * 1000  # Convert to milliseconds
    
    # Print debug info
    print(f"Screen resolution: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
    print(f"Game resolution: {WIDTH}x{HEIGHT}")
    print(f"Offset: ({OFFSET_X}, {OFFSET_Y})")
    
    # Main game loop
    running = True
    while running:
        current_time = pygame.time.get_ticks()
        mouse_pos = pygame.mouse.get_pos()
        
        # FIX 2: Always update background asteroids for menu states
        if game_state in [TITLE_SCREEN, HIGH_SCORES, NAME_INPUT]:
            for asteroid in background_asteroids:
                asteroid.update()
        
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # Handle controller connections/disconnections
            if event.type == pygame.JOYDEVICEADDED:
                print("Controller connected!")
                controllers = init_controllers()
                controller_button_states = [{} for _ in range(max(1, len(controllers)))]
                controller_button_times = [{} for _ in range(max(1, len(controllers)))]

            if event.type == pygame.JOYDEVICEREMOVED:
                print("Controller disconnected!")
                controllers = init_controllers()
                controller_button_states = [{} for _ in range(max(1, len(controllers)))]
                controller_button_times = [{} for _ in range(max(1, len(controllers)))]
                
            # Handle title screen events
            if game_state == TITLE_SCREEN:
                # Check controller input for menu navigation
                for i, controller in enumerate(controllers):
                    # Only check once per frame
                    if i == 0:  # Use first controller for menu navigation
                        # D-pad or analog stick for menu navigation
                        v_axis = controller.get_axis(1)  # Left stick vertical
                        
                        # Use a timer to avoid rapid scrolling
                        current_time = pygame.time.get_ticks()
                        if (abs(v_axis) > CONTROLLER_DEADZONE or controller.get_hat(0)[1] != 0) and (
                                'menu_nav' not in controller_button_times[i] or 
                                current_time - controller_button_times[i].get('menu_nav', 0) > CONTROLLER_REPEAT_DELAY):
                            
                            controller_button_times[i]['menu_nav'] = current_time
                            
                            # Check direction
                            if v_axis < -CONTROLLER_DEADZONE or controller.get_hat(0)[1] > 0:
                                # Move up
                                selected_button_index = (selected_button_index - 1) % 3
                                play_sound('menu_change')
                            elif v_axis > CONTROLLER_DEADZONE or controller.get_hat(0)[1] < 0:
                                # Move down
                                selected_button_index = (selected_button_index + 1) % 3
                                play_sound('menu_change')                        

                        # A or Start button to select
                        if (controller.get_button(0) or controller.get_button(7)) and (
                                'select' not in controller_button_states[i] or 
                                not controller_button_states[i]['select']):
                            
                            controller_button_states[i]['select'] = True
                            play_sound('menu_select')                            

                            # Single Player button
                            if selected_button_index == 0:
                                players = [Player()]
                                game_mode = SINGLE_PLAYER
                                
                                asteroids = []
                                bullets = []
                                ufos = []
                                particles = []
                                powerups = []
                                laser_beams = []
                                scores = [0, 0]
                                level = 1
                                game_state = GAME_PLAYING
                                
                                # Create initial asteroids
                                for _ in range(4):
                                    asteroids.append(Asteroid())
                                    
                                ufo_spawn_timer = pygame.time.get_ticks()
                                ufo_spawn_delay = random.randint(10000, 20000)
                                powerup_spawn_timer = current_time
                                
                            # Co-op Mode button
                            elif selected_button_index == 1:
                                players = [Player(0), Player(1)]
                                game_mode = COOPERATIVE
                                
                                asteroids = []
                                bullets = []
                                ufos = []
                                particles = []
                                powerups = []
                                laser_beams = []
                                scores = [0, 0]
                                level = 1
                                game_state = GAME_PLAYING
                                
                                # Create initial asteroids
                                for _ in range(4):
                                    asteroids.append(Asteroid())
                                    
                                ufo_spawn_timer = pygame.time.get_ticks()
                                ufo_spawn_delay = random.randint(10000, 20000)
                                powerup_spawn_timer = current_time
                                
                            # High Scores button
                            else:
                                game_state = HIGH_SCORES
                        
                        # Track button release
                        elif not (controller.get_button(0) or controller.get_button(7)):
                            controller_button_states[i]['select'] = False
                
                # Handle keyboard events
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        # Move selection up
                        selected_button_index = (selected_button_index - 1) % 3
                        play_sound('menu_change')
                    elif event.key == pygame.K_DOWN:
                        # Move selection down
                        selected_button_index = (selected_button_index + 1) % 3
                        play_sound('menu_change')
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        play_sound('menu_select')
                        # Activate the selected button
                        if selected_button_index == 0:
                            # Single Player button
                            players = [Player()]
                            game_mode = SINGLE_PLAYER
                            
                            asteroids = []
                            bullets = []
                            ufos = []
                            particles = []
                            powerups = []
                            laser_beams = []
                            scores = [0, 0]
                            level = 1
                            game_state = GAME_PLAYING
                            
                            # Create initial asteroids
                            for _ in range(4):
                                asteroids.append(Asteroid())
                                
                            ufo_spawn_timer = pygame.time.get_ticks()
                            ufo_spawn_delay = random.randint(10000, 20000)
                            powerup_spawn_timer = current_time
                            
                        elif selected_button_index == 1:
                            # Co-op Mode button
                            players = [Player(0), Player(1)]
                            game_mode = COOPERATIVE
                            
                            asteroids = []
                            bullets = []
                            ufos = []
                            particles = []
                            powerups = []
                            laser_beams = []
                            scores = [0, 0]
                            level = 1
                            game_state = GAME_PLAYING
                            
                            # Create initial asteroids
                            for _ in range(4):
                                asteroids.append(Asteroid())
                            
                            ufo_spawn_timer = pygame.time.get_ticks()
                            ufo_spawn_delay = random.randint(10000, 20000)
                            powerup_spawn_timer = current_time
                            
                        else:
                            # High Scores button
                            game_state = HIGH_SCORES
                    elif event.key == pygame.K_ESCAPE:  # Exit on ESC
                        running = False
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    single_button, coop_button, scores_button = draw_title_screen(background_asteroids, selected_button_index)
                    
                    if single_button.is_clicked(mouse_pos, event):
                        # Start a new single player game
                        players = [Player()]
                        game_mode = SINGLE_PLAYER
                        
                        asteroids = []
                        bullets = []
                        ufos = []
                        particles = []
                        powerups = []
                        laser_beams = []
                        scores = [0, 0]
                        level = 1
                        game_state = GAME_PLAYING
                        
                        # Create initial asteroids
                        for _ in range(4):
                            asteroids.append(Asteroid())
                            
                        ufo_spawn_timer = pygame.time.get_ticks()
                        ufo_spawn_delay = random.randint(10000, 20000)
                        powerup_spawn_timer = current_time
                    
                    elif coop_button.is_clicked(mouse_pos, event):
                        # Start a new co-op game
                        players = [Player(0), Player(1)]
                        game_mode = COOPERATIVE
                        
                        asteroids = []
                        bullets = []
                        ufos = []
                        particles = []
                        powerups = []
                        laser_beams = []
                        scores = [0, 0]
                        level = 1
                        game_state = GAME_PLAYING
                        
                        # Create initial asteroids
                        for _ in range(4):
                            asteroids.append(Asteroid())
                            
                        ufo_spawn_timer = pygame.time.get_ticks()
                        ufo_spawn_delay = random.randint(10000, 20000)
                        powerup_spawn_timer = current_time
                        
                    elif scores_button.is_clicked(mouse_pos, event):
                        # Show high scores
                        game_state = HIGH_SCORES
            
            # Handle high scores screen events
            elif game_state == HIGH_SCORES:
                # Check controller input
                for i, controller in enumerate(controllers):
                    # Only check once per frame
                    if i == 0:  # Use first controller for menu navigation
                        # A, B or Start button to return to title
                        if (controller.get_button(0) or controller.get_button(1) or controller.get_button(7)) and (
                                'back' not in controller_button_states[i] or 
                                not controller_button_states[i]['back']):
                            
                            controller_button_states[i]['back'] = True
                            game_state = TITLE_SCREEN
                            selected_button_index = 0  # Reset to Single Player being selected
                        
                        # Track button release
                        elif not (controller.get_button(0) or controller.get_button(1) or controller.get_button(7)):
                            controller_button_states[i]['back'] = False
                
                # Handle keyboard events
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE or event.key == pygame.K_ESCAPE:
                        game_state = TITLE_SCREEN
                        selected_button_index = 0  # Reset to Single Player being selected
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    high_scores = get_high_scores(db_path)
                    back_button = draw_high_scores_screen(high_scores, background_asteroids)
                    if back_button.is_clicked(mouse_pos, event):
                        game_state = TITLE_SCREEN
                        selected_button_index = 0  # Reset to Single Player being selected
            
            # Handle name input screen events
            elif game_state == NAME_INPUT:
                # Controller input for submitting scores
                for i, controller in enumerate(controllers):
                    # Only check once per frame
                    if i == 0:  # Use first controller for menu interaction
                        # Start button to submit if names are provided
                        if controller.get_button(7) and (
                                'submit' not in controller_button_states[i] or 
                                not controller_button_states[i]['submit']):
                            
                            controller_button_states[i]['submit'] = True
                            
                            # Check that names are provided
                            if game_mode == SINGLE_PLAYER:
                                if text_inputs[0].text.strip():
                                    save_score(db_path, text_inputs[0].text, scores[0], 'single')
                                    game_state = HIGH_SCORES
                            else:  # COOPERATIVE
                                if text_inputs[0].text.strip() and text_inputs[1].text.strip():
                                    # Save both scores with coop mode indicator
                                    save_score(db_path, text_inputs[0].text, scores[0], 'coop')
                                    save_score(db_path, text_inputs[1].text, scores[1], 'coop')
                                    game_state = HIGH_SCORES
                        
                        # Track button release
                        elif not controller.get_button(7):
                            controller_button_states[i]['submit'] = False
                        
                        # Handle tab key functionality with controller
                        if game_mode == COOPERATIVE and (controller.get_button(6) or controller.get_button(4)) and (
                                'tab' not in controller_button_states[i] or 
                                not controller_button_states[i]['tab']):
                            controller_button_states[i]['tab'] = True
                            # Toggle between text inputs
                            text_inputs[0].active = not text_inputs[0].active
                            text_inputs[1].active = not text_inputs[1].active
                        
                        # Track button release
                        elif not (controller.get_button(6) or controller.get_button(4)):
                            controller_button_states[i]['tab'] = False
                
                # Check for text input events for both inputs
                for i, text_input in enumerate(text_inputs):
                    if i < (2 if game_mode == COOPERATIVE else 1):  # Only check relevant inputs
                        name_submitted = text_input.handle_event(event)
                        if name_submitted and name_submitted.strip():
                            # Just store the name, we'll save all scores when submit button is clicked
                            pass
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:  # ESC to skip and go to high scores
                        game_state = HIGH_SCORES
                    
                    # Tab key to switch between text inputs in coop mode
                    if game_mode == COOPERATIVE and event.key == pygame.K_TAB:
                        text_inputs[0].active = not text_inputs[0].active
                        text_inputs[1].active = not text_inputs[1].active
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    submit_button = draw_name_input_screen(scores, text_inputs, background_asteroids, game_mode)
                    if submit_button.is_clicked(mouse_pos, event):
                        # Check that names are provided
                        if game_mode == SINGLE_PLAYER:
                            if text_inputs[0].text.strip():
                                save_score(db_path, text_inputs[0].text, scores[0], 'single')
                                game_state = HIGH_SCORES
                        else:  # COOPERATIVE
                            if text_inputs[0].text.strip() and text_inputs[1].text.strip():
                                # Save both scores with coop mode indicator
                                save_score(db_path, text_inputs[0].text, scores[0], 'coop')
                                save_score(db_path, text_inputs[1].text, scores[1], 'coop')
                                game_state = HIGH_SCORES
            
            # Handle gameplay events
            elif game_state == GAME_PLAYING:
                if event.type == pygame.KEYDOWN:
                    # Player 1 shooting
                    if event.key == pygame.K_SPACE:
                        if len(players) > 0 and players[0].lives > 0:
                            # Only handle shooting if no laser beam is active for this player
                            if not any(beam.player_id == 0 for beam in laser_beams):
                                # If rapid fire is active, don't apply cooldown
                                if players[0].active_powerup == 'rapid_fire' and players[0].rapid_fire_ammo > 0:
                                    result = players[0].shoot()
                                    if isinstance(result, Bullet):
                                        bullets.append(result)
                                        if hasattr(result, 'is_nuke') and result.is_nuke:
                                            play_sound('nuke')
                                        else:
                                            play_sound('shoot')
                                    elif result == "laser":
                                        laser_beams.append(LaserBeam(players[0]))
                                        play_sound('laser')
                                # Handle shooting with cooldown for other weapons
                                elif current_time - last_shot_times[0] > shot_cooldown:
                                    result = players[0].shoot()
                                    
                                    # Handle different return types
                                    if result == "laser":
                                        laser_beams.append(LaserBeam(players[0]))
                                    elif isinstance(result, Bullet):
                                        bullets.append(result)
                                        last_shot_times[0] = current_time
                                        sounds['shoot'].play()  # Add this line
					                    
                    # Player 2 shooting (numpad 0)
                    elif event.key == pygame.K_KP0:
                        if game_mode == COOPERATIVE and len(players) > 1 and players[1].lives > 0:
                            # Only handle shooting if no laser beam is active for this player
                            if not any(beam.player_id == 1 for beam in laser_beams):
                                # If rapid fire is active, don't apply cooldown
                                if players[1].active_powerup == 'rapid_fire' and players[1].rapid_fire_ammo > 0:
                                    result = players[1].shoot()
                                    if isinstance(result, Bullet):
                                        bullets.append(result)
                                        
                                # Handle shooting with cooldown for other weapons
                                elif current_time - last_shot_times[1] > shot_cooldown:
                                    result = players[1].shoot()
                                    
                                    # Handle different return types
                                    if result == "laser":
                                        laser_beams.append(LaserBeam(players[1]))
                                    elif isinstance(result, Bullet):
                                        bullets.append(result)
                                        last_shot_times[1] = current_time
                    
                    # Escape key to return to title
                    elif event.key == pygame.K_ESCAPE:
                        stop_all_sounds()
                        game_state = TITLE_SCREEN
                        selected_button_index = 0
        
        # Draw appropriate screen based on game state
        if game_state == TITLE_SCREEN:
            single_button, coop_button, scores_button = draw_title_screen(background_asteroids, selected_button_index)
        elif game_state == HIGH_SCORES:
            high_scores = get_high_scores(db_path)
            back_button = draw_high_scores_screen(high_scores, background_asteroids)
        elif game_state == NAME_INPUT:
            submit_button = draw_name_input_screen(scores, text_inputs, background_asteroids, game_mode)
        
        # Only update the game if playing
        elif game_state == GAME_PLAYING:
            # Clear the surface
            game_surface.fill(BLACK)
            
            # Get keys pressed
            keys = pygame.key.get_pressed()
            
            # Player 1 controls
            if players[0].lives > 0:
                # Keyboard controls
                if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                    players[0].rotate(-1)
                if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                    players[0].rotate(1)
                if keys[pygame.K_UP] or keys[pygame.K_w]:
                    players[0].thrust()
                    if random.random() < 0.1:
                        play_sound('thrust')
                
                # Controller controls for player 1 (first available controller or assigned controller)
                if len(controllers) > 0:
                    controller = controllers[0]
                    
                    # Left/Right with left analog stick or D-pad
                    h_axis = controller.get_axis(0)  # Left stick horizontal
                    if abs(h_axis) > CONTROLLER_DEADZONE:
                        players[0].rotate(-1 if h_axis < 0 else 1)
                    
                    # D-pad for rotation
                    if controller.get_hat(0)[0] < 0:  # D-pad left
                        players[0].rotate(-1)
                    elif controller.get_hat(0)[0] > 0:  # D-pad right
                        players[0].rotate(1)
                    
                    # Thrust with up on D-pad or forward on left analog stick
                    v_axis = controller.get_axis(1)  # Left stick vertical
                    if controller.get_hat(0)[1] > 0 or v_axis < -CONTROLLER_DEADZONE:  # Up on D-pad or up on stick
                        players[0].thrust()
                    
                    # Shoot with A button or right bumper
                    button_idx = 0  # A button
                    if (controller.get_button(button_idx) and 
                            ('fire_p1' not in controller_button_states[0] or 
                             not controller_button_states[0]['fire_p1'])):
                        
                        controller_button_states[0]['fire_p1'] = True
                        
                        # Only handle shooting if no laser beam is active for this player
                        if not any(beam.player_id == 0 for beam in laser_beams):
                            # If rapid fire is active, don't apply cooldown
                            if players[0].active_powerup == 'rapid_fire' and players[0].rapid_fire_ammo > 0:
                                result = players[0].shoot()
                                if isinstance(result, Bullet):
                                    bullets.append(result)
                                    play_sound('shoot')
                                    
                            # Handle shooting with cooldown for other weapons
                            elif current_time - last_shot_times[0] > shot_cooldown:
                                result = players[0].shoot()
                                
                                # Handle different return types
                                if result == "laser":
                                    laser_beams.append(LaserBeam(players[0]))
                                    play_sound('laser')
                                elif isinstance(result, Bullet):
                                    bullets.append(result)
                                    
                                    # Play sound BEFORE updating shot time
                                    if hasattr(result, 'is_nuke') and result.is_nuke:
                                        play_sound('nuke')
                                    else:
                                        # Play sound directly to ensure it works
                                        sounds['shoot'].play()
                                        
                                    # Update time AFTER playing sound
                                    last_shot_times[0] = current_time
                    
                    # Track button release
                    elif not controller.get_button(button_idx):
                        controller_button_states[0]['fire_p1'] = False
                    
                    # Rapid fire handling for controller
                    if players[0].active_powerup == 'rapid_fire' and players[0].rapid_fire_ammo > 0:
                        # Use different button (X button) for consistent fire
                        if controller.get_button(2):  # X button
                            if current_time - last_shot_times[0] > 100:  # Faster firing rate
                                result = players[0].shoot()
                                if isinstance(result, Bullet):
                                    bullets.append(result)
                                    play_sound('shoot')
                                    last_shot_times[0] = current_time
                
                # Rapid fire shooting for player 1 (keyboard)
                if players[0].active_powerup == 'rapid_fire' and keys[pygame.K_SPACE] and players[0].rapid_fire_ammo > 0:
                    if current_time - last_shot_times[0] > 100:  # Faster firing rate
                        result = players[0].shoot()
                        if isinstance(result, Bullet):
                            bullets.append(result)
                            last_shot_times[0] = current_time
            
            # Player 2 controls (numpad or second controller) - only in co-op mode
            if game_mode == COOPERATIVE and len(players) > 1 and players[1].lives > 0:
                # Keyboard controls
                if keys[pygame.K_KP4]:  # Left
                    players[1].rotate(-1)
                if keys[pygame.K_KP6]:  # Right
                    players[1].rotate(1)
                if keys[pygame.K_KP8]:  # Up/Thrust
                    players[1].thrust()
                
                # Controller controls for player 2 (second controller if available)
                controller_idx = min(1, len(controllers) - 1) if len(controllers) > 0 else 0
                if len(controllers) > 0:
                    controller = controllers[controller_idx]
                    
                    # Left/Right with left analog stick or D-pad
                    h_axis = controller.get_axis(0)  # Left stick horizontal
                    if abs(h_axis) > CONTROLLER_DEADZONE:
                        players[1].rotate(-1 if h_axis < 0 else 1)
                    
                    # D-pad for rotation
                    if controller.get_hat(0)[0] < 0:  # D-pad left
                        players[1].rotate(-1)
                    elif controller.get_hat(0)[0] > 0:  # D-pad right
                        players[1].rotate(1)
                    
                    # Thrust with up on D-pad or forward on left analog stick
                    v_axis = controller.get_axis(1)  # Left stick vertical
                    if controller.get_hat(0)[1] > 0 or v_axis < -CONTROLLER_DEADZONE:  # Up on D-pad or up on stick
                        players[1].thrust()
                    
                    # Shoot with A button
                    button_idx = 0  # A button
                    if (controller.get_button(button_idx) and 
                            ('fire_p2' not in controller_button_states[controller_idx] or 
                             not controller_button_states[controller_idx]['fire_p2'])):
                        
                        controller_button_states[controller_idx]['fire_p2'] = True
                        
                        # Only handle shooting if no laser beam is active for this player
                        if not any(beam.player_id == 1 for beam in laser_beams):
                            # If rapid fire is active, don't apply cooldown
                            if players[1].active_powerup == 'rapid_fire' and players[1].rapid_fire_ammo > 0:
                                result = players[1].shoot()
                                if isinstance(result, Bullet):
                                    bullets.append(result)
                                    play_sound('shoot')
                                    
                            # Handle shooting with cooldown for other weapons
                            elif current_time - last_shot_times[1] > shot_cooldown:
                                result = players[1].shoot()
                                
                                # Handle different return types
                                if result == "laser":
                                    laser_beams.append(LaserBeam(players[1]))
                                    play_sound('laser')
                                elif isinstance(result, Bullet):
                                    bullets.append(result)
                                    
                                    # Play sound BEFORE updating shot time
                                    if hasattr(result, 'is_nuke') and result.is_nuke:
                                        play_sound('nuke')
                                    else:
                                        # Play sound directly to ensure it works
                                        sounds['shoot'].play()
                                        
                                    # Update time AFTER playing sound
                                    last_shot_times[1] = current_time
                    
                    # Track button release
                    elif not controller.get_button(button_idx):
                        controller_button_states[controller_idx]['fire_p2'] = False
                    
                    # Rapid fire handling for controller
                    if players[1].active_powerup == 'rapid_fire' and players[1].rapid_fire_ammo > 0:
                        # Use different button (X button) for consistent fire
                        if controller.get_button(2):  # X button
                            if current_time - last_shot_times[1] > 100:  # Faster firing rate
                                result = players[1].shoot()
                                if isinstance(result, Bullet):
                                    bullets.append(result)
                                    play_sound('shoot')
                                    last_shot_times[1] = current_time
                
                # Rapid fire shooting for player 2 (keyboard)
                if players[1].active_powerup == 'rapid_fire' and keys[pygame.K_KP0] and players[1].rapid_fire_ammo > 0:
                    if current_time - last_shot_times[1] > 100:  # Faster firing rate
                        result = players[1].shoot()
                        if isinstance(result, Bullet):
                            bullets.append(result)
                            last_shot_times[1] = current_time
                
            # Update players
            for player in players:
                if player.lives > 0:
                    player.update()
            
            # Update bullets
            for bullet in bullets[:]:
                bullet.update()
                
                # Check for nuclear bomb impact
                if bullet.is_nuke and bullet.lifetime < 56:  # Give a bit of time before nuke can explode
                    exploded = False
                    
                    # Check collision with any asteroid
                    for asteroid in asteroids[:]:
                        if bullet.check_collision(asteroid):
                            exploded = True
                            break
                            
                    # Check collision with any UFO
                    for ufo in ufos[:]:
                        if ufo.check_collision(bullet):
                            if len(ufos) == 1:
                                stop_sound('ufo')
                            exploded = True
                            play_sound('explosion_medium')
                            break
                            
                    # If nuke exploded or lifetime is almost over, trigger nuclear explosion
                    if exploded or bullet.lifetime < 4:
                        # Flash screen
                        white_surface = pygame.Surface((WIDTH, HEIGHT))
                        white_surface.fill(WHITE)
                        game_surface.blit(white_surface, (0, 0))
                        
                        # Play the nuke explosion sound
                        play_sound('nuke')
                        
                        # Scale and display for the flash effect
                        screen.fill(BLACK)
                        screen.blit(game_surface, (OFFSET_X, OFFSET_Y))
                        pygame.display.flip()
                        pygame.time.delay(50)  # Flash duration
                        
                        # Generate explosion particles
                        for _ in range(100):
                            particles.append(Particle(
                                random.randint(0, WIDTH),
                                random.randint(0, HEIGHT),
                                random.choice([RED, YELLOW, WHITE])
                            ))
                        
                        # Credit points to the player who fired the bullet
                        player_id = bullet.player_id
                        
                        # Destroy all asteroids and UFOs on screen
                        for asteroid in asteroids[:]:
                            # Add score to the appropriate player
                            players[player_id].score += (4 - asteroid.size) * 100
                            scores[player_id] += (4 - asteroid.size) * 100
                            
                            particles.extend(create_explosion(asteroid.position[0], asteroid.position[1], asteroid.size))
                        asteroids.clear()
                        
                        for ufo in ufos[:]:
                            # Add score to the appropriate player
                            players[player_id].score += 1000
                            scores[player_id] += 1000
                            
                            particles.extend(create_explosion(ufo.position[0], ufo.position[1], 2))
                        ufos.clear()
                        
                        # Remove all bullets except the nuke
                        for b in bullets[:]:
                            if b != bullet:
                                bullets.remove(b)
                        
                        # Remove the nuke
                        bullets.remove(bullet)
                        break
                    
                if bullet.is_dead():
                    bullets.remove(bullet)
            
            # Update laser beams
            for laser_beam in laser_beams[:]:
                player_id = laser_beam.player_id
                
                # Check for asteroid destruction by laser
                for asteroid in asteroids[:]:
                    if laser_beam.check_collision(asteroid):
                        # Play the appropriate explosion sound based on asteroid size
                        if asteroid.size == 3:  # Large
                            play_sound('explosion_large')
                        elif asteroid.size == 2:  # Medium
                            play_sound('explosion_medium')
                        else:  # Small
                            play_sound('explosion_small')
                            
                        # Add score to the appropriate player
                        players[player_id].score += (4 - asteroid.size) * 100
                        scores[player_id] += (4 - asteroid.size) * 100
                        
                        # Create an explosion effect
                        particles.extend(create_explosion(
                            asteroid.position[0], asteroid.position[1], asteroid.size,
                            YELLOW if player_id == 0 else CYAN
                        ))
                        
                        # Break the asteroid
                        fragments = asteroid.break_apart()
                        asteroids.extend(fragments)
                        
                        # Remove the asteroid
                        asteroids.remove(asteroid)
                                        
                # Check for UFO destruction by laser
                for ufo in ufos[:]:
                    if laser_beam.check_collision(ufo):
                        # Add score to the appropriate player
                        players[player_id].score += 1000
                        scores[player_id] += 1000
                        
                        # Create an explosion effect
                        particles.extend(create_explosion(
                            ufo.position[0], ufo.position[1], 2,
                            YELLOW if player_id == 0 else CYAN
                        ))
                        
                        # Remove the UFO
                        ufos.remove(ufo)
                
                # Update laser beam
                if laser_beam.update():
                    laser_beams.remove(laser_beam)
                    
            # Update powerups
            for powerup in powerups[:]:
                powerup_collected = False
                
                if powerup.update():
                    powerups.remove(powerup)
                    continue
                    
                # Check if any player collected the powerup
                for player in players:
                    if player.lives > 0 and powerup.check_collision(player):
                        # Player collected the powerup
                        player.collect_powerup(powerup.type)
                        # Create particle effect
                        particles.extend(create_explosion(
                            powerup.x, powerup.y, 2, 
                            PowerUp.COLORS[powerup.type]
                        ))
                        powerup_collected = True
                        break
                        
                if powerup_collected:
                    powerups.remove(powerup)
                    
            # Update asteroids
            for asteroid in asteroids[:]:
                asteroid.update()
                
                # Check collision with players
                for p_idx, player in enumerate(players):
                    if player.lives <= 0:
                        continue
                        
                    if player.check_collision(asteroid):
                        player.lives -= 1
                        play_sound('player_explosion')  # Player explosion sound
                        particles.extend(create_explosion(player.position[0], player.position[1], 2))
                        
                        # Check for game over - only if lives reach zero
                        if (game_mode == SINGLE_PLAYER and player.lives <= 0) or all(p.lives <= 0 for p in players):
                            game_state = NAME_INPUT
                            text_inputs[0].text = ""
                            text_inputs[0].active = True
                            if game_mode == COOPERATIVE:
                                text_inputs[1].text = ""
                                text_inputs[1].active = False  # Start with player 1 active
                        else:
                            # Only respawn if the player still has lives
                            if player.lives > 0:
                                player.respawn()
                        
                        # Play explosion sound for asteroid
                        if asteroid.size == 3:  # Large
                            play_sound('explosion_large')
                        elif asteroid.size == 2:  # Medium
                            play_sound('explosion_medium')
                        else:  # Small
                            play_sound('explosion_small')
                            
                        # Create an explosion effect
                        particles.extend(create_explosion(asteroid.position[0], asteroid.position[1], asteroid.size))
                            
                        # Remove the asteroid
                        asteroids.remove(asteroid)
                        break
                
                    # Check if invincible player rammed into asteroid
                    elif player.is_invincible:
                        # Calculate distance
                        distance = math.sqrt((player.position[0] - asteroid.position[0])**2 + 
                                            (player.position[1] - asteroid.position[1])**2)
                        if distance < player.radius + asteroid.radius:
                            # Play the appropriate explosion sound based on asteroid size
                            if asteroid.size == 3:  # Large
                                sounds['explosion_large'].play()
                            elif asteroid.size == 2:  # Medium
                                sounds['explosion_medium'].play()
                            else:  # Small
                                sounds['explosion_small'].play()
                                
                            # Add score to the player
                            player.score += (4 - asteroid.size) * 100
                            scores[p_idx] += (4 - asteroid.size) * 100
                            
                            # Create an explosion effect with player color
                            color = PURPLE  # Base invincibility color
                            if p_idx == 1:  # Blend with player 2 color for more distinct effect
                                color = (128, 0, 255)  # Blend of purple and cyan
                                
                            particles.extend(create_explosion(asteroid.position[0], asteroid.position[1], asteroid.size, color))
                            
                            # Break the asteroid
                            fragments = asteroid.break_apart()
                            asteroids.extend(fragments)
                            
                            # Remove the asteroid
                            asteroids.remove(asteroid)
                            break
                
                # Skip further checks if asteroid was removed
                if asteroid not in asteroids:
                    continue
                    
                # FIX 3: Check bullet collisions with enhanced collision detection 
                for bullet in bullets[:]:
                    # Use continuous collision detection for small asteroids
                    collides = False
                    if asteroid.size == 1:  # Small asteroid
                        collides = bullet.line_collision(asteroid)
                    else:  # Medium or large asteroid
                        collides = bullet.check_collision(asteroid)
                        
                    if collides:
                        # Get player who fired the bullet
                        player_id = bullet.player_id
                        
                        # Add score to the appropriate player
                        players[player_id].score += (4 - asteroid.size) * 100
                        scores[player_id] += (4 - asteroid.size) * 100
                        
                        # Create an explosion effect
                        particles.extend(create_explosion(asteroid.position[0], asteroid.position[1], asteroid.size))

                        play_sound('explosion_medium')
                        
                        # Break the asteroid
                        fragments = asteroid.break_apart()
                        asteroids.extend(fragments)
                        
                        # Remove the bullet and asteroid
                        if bullet in bullets:
                            bullets.remove(bullet)
                        asteroids.remove(asteroid)
                        break

            # Update UFOs
            for ufo in ufos[:]:
                ufo_bullet = ufo.update(players)  # Pass all players for UFO targeting
                
                # Check if the UFO is off-screen
                if ufo.is_off_screen():
                    ufos.remove(ufo)
                    continue
                    
                # Check collision with players
                for p_idx, player in enumerate(players):
                    if player.lives <= 0:
                        continue
                        
                    if ufo.check_collision(player) and not player.is_invincible:
                        player.lives -= 1
                        particles.extend(create_explosion(player.position[0], player.position[1], 2))
                        particles.extend(create_explosion(ufo.position[0], ufo.position[1], 2))
                        
                        # Check for game over - only if lives reach zero
                        if (game_mode == SINGLE_PLAYER and player.lives <= 0) or all(p.lives <= 0 for p in players):
                            game_state = NAME_INPUT
                            text_inputs[0].text = ""
                            text_inputs[0].active = True
                            if game_mode == COOPERATIVE:
                                text_inputs[1].text = ""
                                text_inputs[1].active = False  # Start with player 1 active
                        else:
                            # Only respawn if the player still has lives
                            if player.lives > 0:
                                player.respawn()
                        
                        ufos.remove(ufo)
                        break
                    
                    # Check if invincible player rammed into UFO
                    elif player.is_invincible:
                        distance = math.sqrt((player.position[0] - ufo.position[0])**2 + 
                                            (player.position[1] - ufo.position[1])**2)
                        if distance < player.radius + ufo.radius:
                            # Add score to the player
                            player.score += 1000
                            scores[p_idx] += 1000
                            
                            # Create an explosion effect
                            color = PURPLE
                            if p_idx == 1:  # Player 2
                                color = (128, 0, 255)  # Blend of purple and cyan
                                
                            particles.extend(create_explosion(ufo.position[0], ufo.position[1], 2, color))
                            
                            # Remove the UFO
                            ufos.remove(ufo)
                            break
                
                # Skip if UFO was removed
                if ufo not in ufos:
                    continue
                    
                # Check bullet collisions
                for bullet in bullets[:]:
                    if ufo.check_collision(bullet):
                        # Get player who fired the bullet
                        player_id = bullet.player_id
                        
                        # Add score to the appropriate player
                        players[player_id].score += 1000
                        scores[player_id] += 1000
                        
                        # Create an explosion effect
                        particles.extend(create_explosion(ufo.position[0], ufo.position[1], 2))
                        
                        # Remove the bullet and UFO
                        if bullet in bullets:
                            bullets.remove(bullet)
                        ufos.remove(ufo)
                        break
                        
                # UFO shooting
                if ufo in ufos and ufo_bullet:  # Make sure it wasn't removed
                    bullets.append(ufo_bullet)
                    play_sound('ufo_shoot')
            
            # Update particles
            for particle in particles[:]:
                particle.update()
                if particle.is_dead():
                    particles.remove(particle)
                    
            # Check if level is complete
            if len(asteroids) == 0:
                stop_sound('ufo')
                play_sound('menu_select')
                level += 1
                
                # In co-op mode, if a player was dead but at least one player survived
                if game_mode == COOPERATIVE:
                    for player in players:
                        if player.lives <= 0:
                            # Revive them with 1 life at the start of the new level
                            player.lives = 1
                            player.respawn()
                
                # Spawn more asteroids each level
                for _ in range(4 + level):
                    # Make sure asteroids don't spawn directly on the player
                    while True:
                        asteroid = Asteroid()
                        # Check distance to all active players
                        safe = True
                        for player in players:
                            if player.lives > 0:
                                dx = asteroid.position[0] - player.position[0]
                                dy = asteroid.position[1] - player.position[1]
                                dist = math.sqrt(dx*dx + dy*dy)
                                if dist < 100:  # Safe distance
                                    safe = False
                                    break
                        if safe:
                            break
                    asteroids.append(asteroid)
            
            # Spawn UFO if it's time
            if current_time - ufo_spawn_timer > ufo_spawn_delay and len(ufos) < 1:
                ufos.append(UFO())
                play_sound('ufo', -1)
                ufo_spawn_timer = current_time
                ufo_spawn_delay = random.randint(10000, 20000)  # 10-20 seconds
                
            # Spawn power-up if it's time
            if current_time - powerup_spawn_timer > powerup_spawn_delay and len(powerups) < 2:
                # Choose a location away from all players
                while True:
                    x = random.randint(50, WIDTH - 50)
                    y = random.randint(50, HEIGHT - 50)
                    
                    # Check distance to all active players
                    safe = True
                    for player in players:
                        if player.lives > 0:
                            dx = x - player.position[0]
                            dy = y - player.position[1]
                            dist = math.sqrt(dx*dx + dy*dy)
                            if dist < 100:  # Safe distance
                                safe = False
                                break
                    if safe:
                        break
                        
                powerups.append(PowerUp(x, y))
                powerup_spawn_timer = current_time
                powerup_spawn_delay = POWERUP_SPAWN_RATE * 1000  # Convert to milliseconds

            # Draw everything
            for player in players:
                if player.lives > 0:
                    player.draw()

            # Draw laser beams if active
            for laser_beam in laser_beams:
                laser_beam.draw()
                
            # Draw bullets
            for bullet in bullets:
                bullet.draw()
                
            # Draw asteroids
            for asteroid in asteroids:
                asteroid.draw()
                
            # Draw UFOs
            for ufo in ufos:
                ufo.draw()
                
            # Draw powerups
            for powerup in powerups:
                powerup.draw()
                
            # Draw particles
            for particle in particles:
                particle.draw()

            # Draw UI based on game mode
            if game_mode == SINGLE_PLAYER:
                # Draw score centered at top
                score_text = font.render(f"Score: {scores[0]}", True, WHITE)
                level_text = font.render(f"Level: {level}", True, WHITE)
                lives_text = font.render(f"Lives: {players[0].lives}", True, WHITE)
                
                # Position UI elements
                game_surface.blit(score_text, (10, 10))
                game_surface.blit(level_text, (WIDTH - level_text.get_width() - 10, 10))
                game_surface.blit(lives_text, (WIDTH // 2 - lives_text.get_width() // 2, 10))
                
                # Draw power-up status
                if players[0].is_invincible:
                    remaining = 10 - (current_time - players[0].invincible_timer) // 1000
                    power_text = font.render(f"Invincibility: {max(0, remaining)}s", True, PURPLE)
                    game_surface.blit(power_text, (10, HEIGHT - 40))
                elif players[0].has_laser:
                    power_text = font.render("Laser Ready!", True, YELLOW)
                    game_surface.blit(power_text, (10, HEIGHT - 40))
                elif players[0].has_nuke:
                    power_text = font.render("Nuclear Bomb Ready!", True, GREY)
                    game_surface.blit(power_text, (10, HEIGHT - 40))
                elif players[0].active_powerup == 'rapid_fire':
                    power_text = font.render(f"Rapid Fire: {players[0].rapid_fire_ammo}", True, RED)
                    game_surface.blit(power_text, (10, HEIGHT - 40))
            else:
                # Co-op mode UI - Player 1 on left, Player 2 on right
                
                # Player 1 UI (left side)
                p1_score_text = font.render(f"P1: {scores[0]}", True, WHITE)
                p1_lives_text = font.render(f"Lives: {players[0].lives}", True, WHITE)
                
                # Player 2 UI (right side)
                p2_score_text = font.render(f"P2: {scores[1]}", True, CYAN)
                p2_lives_text = font.render(f"Lives: {players[1].lives}", True, CYAN)
                
                # Level (center)
                level_text = font.render(f"Level: {level}", True, WHITE)
                
                # Position UI elements
                game_surface.blit(p1_score_text, (10, 10))
                game_surface.blit(p1_lives_text, (10, 40))
                
                game_surface.blit(level_text, (WIDTH // 2 - level_text.get_width() // 2, 10))
                
                game_surface.blit(p2_score_text, (WIDTH - p2_score_text.get_width() - 10, 10))
                game_surface.blit(p2_lives_text, (WIDTH - p2_lives_text.get_width() - 10, 40))
                
                # Draw power-up statuses at bottom
                # Player 1 (left side)
                y_pos = HEIGHT - 40
                if players[0].is_invincible:
                    remaining = 10 - (current_time - players[0].invincible_timer) // 1000
                    p1_power_text = font.render(f"P1 Invincibility: {max(0, remaining)}s", True, PURPLE)
                    game_surface.blit(p1_power_text, (10, y_pos))
                    y_pos -= 30
                elif players[0].has_laser:
                    p1_power_text = font.render("P1 Laser Ready", True, YELLOW)
                    game_surface.blit(p1_power_text, (10, y_pos))
                    y_pos -= 30
                elif players[0].has_nuke:
                    p1_power_text = font.render("P1 Nuke Ready", True, GREY)
                    game_surface.blit(p1_power_text, (10, y_pos))
                    y_pos -= 30
                elif players[0].active_powerup == 'rapid_fire':
                    p1_power_text = font.render(f"P1 Rapid Fire: {players[0].rapid_fire_ammo}", True, RED)
                    game_surface.blit(p1_power_text, (10, y_pos))
                    y_pos -= 30
                
                # Player 2 (right side)
                y_pos = HEIGHT - 40
                if players[1].is_invincible:
                    remaining = 10 - (current_time - players[1].invincible_timer) // 1000
                    p2_power_text = font.render(f"P2 Invincibility: {max(0, remaining)}s", True, PURPLE)
                    game_surface.blit(p2_power_text, (WIDTH - p2_power_text.get_width() - 10, y_pos))
                    y_pos -= 30
                elif players[1].has_laser:
                    p2_power_text = font.render("P2 Laser Ready", True, CYAN)
                    game_surface.blit(p2_power_text, (WIDTH - p2_power_text.get_width() - 10, y_pos))
                    y_pos -= 30
                elif players[1].has_nuke:
                    p2_power_text = font.render("P2 Nuke Ready", True, GREY)
                    game_surface.blit(p2_power_text, (WIDTH - p2_power_text.get_width() - 10, y_pos))
                    y_pos -= 30
                elif players[1].active_powerup == 'rapid_fire':
                    p2_power_text = font.render(f"P2 Rapid Fire: {players[1].rapid_fire_ammo}", True, RED)
                    game_surface.blit(p2_power_text, (WIDTH - p2_power_text.get_width() - 10, y_pos))
                    y_pos -= 30

        # Blit the game surface to the screen at the correct position (no scaling)
        screen.fill(BLACK)
        screen.blit(game_surface, (OFFSET_X, OFFSET_Y))
        
        # Update the display
        pygame.display.flip()
        clock.tick(FPS)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
