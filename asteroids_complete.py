import pygame
import sys
import math
import random
import sqlite3
import os

# Initialize pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
PURPLE = (128, 0, 128)
YELLOW = (255, 255, 0)
GREY = (192, 192, 192)
FPS = 60

# Game states
TITLE_SCREEN = 0
GAME_PLAYING = 1
GAME_OVER = 2
HIGH_SCORES = 3
NAME_INPUT = 4

# Power-up spawn rate (in seconds)
POWERUP_SPAWN_RATE = 10

# After-image settings for invincibility
AFTERIMAGE_FREQUENCY = 5  # Frames between each after-image (lower = more images)
AFTERIMAGE_DURATION = 30  # How long after-images last in frames

# Set up the display
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("aSteroids")
clock = pygame.time.Clock()

# Load fonts
font = pygame.font.Font(None, 36)
title_font = pygame.font.Font(None, 72)
big_font = pygame.font.Font(None, 48)

# Database setup
def init_database():
    """Initialize the high scores database"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'asteroids_scores.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS high_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        score INTEGER NOT NULL,
        date TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()
    
    return db_path

def save_score(db_path, name, score):
    """Save a score to the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get current date and time
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("INSERT INTO high_scores (name, score, date) VALUES (?, ?, ?)",
                  (name, score, date))
    
    conn.commit()
    conn.close()

def get_high_scores(db_path, limit=10):
    """Get the top scores from the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, score, date FROM high_scores ORDER BY score DESC LIMIT ?", (limit,))
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
            # Toggle active state if clicked
            if self.rect.collidepoint(event.pos):
                self.active = True
            else:
                self.active = False
                
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
        pygame.draw.rect(screen, BLACK, self.rect)
        pygame.draw.rect(screen, self.color, self.rect, 2)
        
        # Draw text
        if self.text:
            text_surface = self.font.render(self.text, True, self.color)
            screen.blit(text_surface, (self.rect.x + 5, self.rect.y + 5))
            
        # Draw cursor
        if self.active and self.cursor_visible:
            cursor_pos = self.font.size(self.text)[0] + self.rect.x + 5
            pygame.draw.line(screen, self.color, 
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
        pygame.draw.rect(screen, BLACK, self.rect)
        pygame.draw.rect(screen, color, self.rect, 2)
        
        # Draw text
        text_surface = self.font.render(self.text, True, color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)
        
        # Draw selection indicator if selected (triangle)
        if self.is_selected:
            triangle_points = [
                (self.rect.x - 20, self.rect.centery),
                (self.rect.x - 10, self.rect.centery - 5),
                (self.rect.x - 10, self.rect.centery + 5)
            ]
            pygame.draw.polygon(screen, self.selected_color, triangle_points)
        
    def check_hover(self, pos):
        self.is_hovered = self.rect.collidepoint(pos)
        return self.is_hovered
        
    def is_clicked(self, pos, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(pos):
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
        screen.blit(surf, (0, 0))

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
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        
        # Draw pulsing outer ring
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), 
                          self.radius + self.pulse_size, 1)
        
        # Draw icon inside based on powerup type
        if self.type == 'invincibility':
            # Shield icon
            pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), self.radius-4, 1)
        elif self.type == 'laser_beam':
            # Beam icon
            pygame.draw.line(screen, WHITE, 
                           (self.x-self.radius+3, self.y), 
                           (self.x+self.radius-3, self.y), 2)
        elif self.type == 'nuclear_bomb':
            # Bomb icon
            pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), self.radius-4)
            pygame.draw.line(screen, self.color, 
                           (self.x, self.y-self.radius+3), 
                           (self.x, self.y-3), 2)
        elif self.type == 'rapid_fire':
            # Bullet icon
            for i in range(3):
                pygame.draw.circle(screen, WHITE, 
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
    def __init__(self, x, y, vx, vy, is_nuke=False):
        self.position = [x, y]
        self.velocity = [vx, vy]
        self.radius = 2
        self.lifetime = 60  # frames (about 1 second at 60 FPS)
        self.is_nuke = is_nuke
        self.color = GREY if is_nuke else WHITE
        
    def draw(self):
        if self.is_nuke:
            # Draw larger nuke bullet
            pygame.draw.circle(screen, self.color, (int(self.position[0]), int(self.position[1])), self.radius * 2)
            # Pulsing effect
            pulse = int(pygame.time.get_ticks() / 100) % 3
            pygame.draw.circle(screen, RED, (int(self.position[0]), int(self.position[1])), 
                              self.radius * 2 + pulse, 1)
        else:
            pygame.draw.circle(screen, self.color, (int(self.position[0]), int(self.position[1])), self.radius)
        
    def update(self):
        # Update position
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        
        # Wrap around screen edges
        if self.position[0] < 0:
            self.position[0] = WIDTH
        elif self.position[0] > WIDTH:
            self.position[0] = 0
            
        if self.position[1] < 0:
            self.position[1] = HEIGHT
        elif self.position[1] > HEIGHT:
            self.position[1] = 0
            
        # Decrease lifetime
        self.lifetime -= 1
        
    def is_dead(self):
        return self.lifetime <= 0
        
    def check_collision(self, asteroid):
        distance = math.sqrt((self.position[0] - asteroid.position[0])**2 + 
                            (self.position[1] - asteroid.position[1])**2)
        return distance < self.radius + asteroid.radius

class LaserBeam:
    def __init__(self, player):
        self.player = player
        self.duration = 180  # 3 seconds at 60 FPS
        self.width = 5
        self.length = 2000  # Very long to ensure it reaches screen edges
        self.color = YELLOW
        
    def draw(self):
        angle = math.radians(self.player.rotation)
        start_x = self.player.position[0] + self.player.radius * math.cos(angle)
        start_y = self.player.position[1] + self.player.radius * math.sin(angle)
        
        end_x = start_x + self.length * math.cos(angle)
        end_y = start_y + self.length * math.sin(angle)
        
        # Draw the main laser beam
        pygame.draw.line(screen, self.color, (start_x, start_y), (end_x, end_y), self.width)
        
        # Draw glow effect
        for i in range(1, 3):
            alpha = 150 - i * 50
            glow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(glow_surf, (self.color[0], self.color[1], self.color[2], alpha), 
                          (start_x, start_y), (end_x, end_y), self.width + i * 2)
            screen.blit(glow_surf, (0, 0))
            
        # Draw pulse effect along the beam
        time = pygame.time.get_ticks()
        pulse_positions = [(start_x + i * 30 * math.cos(angle), 
                          start_y + i * 30 * math.sin(angle)) 
                         for i in range(10)]
        
        for i, pos in enumerate(pulse_positions):
            if (i + time // 100) % 3 == 0:  # Makes the pulses move along the beam
                pygame.draw.circle(screen, WHITE, (int(pos[0]), int(pos[1])), 3)
        
    def update(self):
        self.duration -= 1
        return self.duration <= 0  # Return True when laser is finished
        
    def check_collision(self, asteroid):
        # Calculate laser line
        angle = math.radians(self.player.rotation)
        start_x = self.player.position[0]
        start_y = self.player.position[1]
        
        # Calculate distance from asteroid center to laser line
        dx = math.cos(angle)
        dy = math.sin(angle)
        
        # Vector from start to asteroid
        ax = asteroid.position[0] - start_x
        ay = asteroid.position[1] - start_y
        
        # Project asteroid vector onto laser direction
        t = ax * dx + ay * dy
        
        # Closest point on line to asteroid
        closest_x = start_x + t * dx
        closest_y = start_y + t * dy
        
        # Calculate distance from asteroid to closest point
        distance = math.sqrt((asteroid.position[0] - closest_x)**2 + 
                            (asteroid.position[1] - closest_y)**2)
        
        # Check if point is actually on the beam (not behind the ship)
        if t < 0:
            return False
            
        return distance < asteroid.radius + self.width/2

class Player:
    def __init__(self):
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
                color = WHITE
        elif self.active_powerup == 'rapid_fire':
            color = RED
        else:
            color = WHITE
        
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
        pygame.draw.polygon(screen, color, ship_points)
        
        # Draw thrust flame if thrusting
        if self.is_thrusting:
            flame_points = [
                (self.position[0] - self.radius * 1.5 * cos_val, 
                 self.position[1] - self.radius * 1.5 * sin_val),
                (self.position[0] - self.radius * cos_val + self.radius/2 * math.cos(angle + math.pi/2), 
                 self.position[1] - self.radius * sin_val + self.radius/2 * math.sin(angle + math.pi/2)),
                (self.position[0] - self.radius * cos_val + self.radius/2 * math.cos(angle - math.pi/2), 
                 self.position[1] - self.radius * sin_val + self.radius/2 * math.sin(angle - math.pi/2))
            ]
            pygame.draw.polygon(screen, BLUE, flame_points)
        
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
            return Bullet(bullet_x, bullet_y, bullet_vx, bullet_vy, is_nuke=True)
            
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
                
            return Bullet(bullet_x, bullet_y, bullet_vx, bullet_vy)
        else:
            # Regular shot
            angle = math.radians(self.rotation)
            bullet_x = self.position[0] + self.radius * math.cos(angle)
            bullet_y = self.position[1] + self.radius * math.sin(angle)
            bullet_vx = 10 * math.cos(angle) + self.velocity[0] * 0.5
            bullet_vy = 10 * math.sin(angle) + self.velocity[1] * 0.5
            return Bullet(bullet_x, bullet_y, bullet_vx, bullet_vy)
        
    def check_collision(self, asteroid):
        # Skip collision check if invulnerable
        if self.invulnerable or self.is_invincible:
            return False
            
        # Basic circle collision
        distance = math.sqrt((self.position[0] - asteroid.position[0])**2 + 
                            (self.position[1] - asteroid.position[1])**2)
        return distance < self.radius + asteroid.radius
        
    def respawn(self):
        self.position = [WIDTH // 2, HEIGHT // 2]
        self.velocity = [0, 0]
        self.rotation = 0
        self.invulnerable = True
        self.invulnerable_timer = pygame.time.get_ticks()
        
    def collect_powerup(self, powerup_type):
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
        pygame.draw.polygon(screen, WHITE, transformed_vertices, 1)
        
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
        pygame.draw.ellipse(screen, RED, (self.position[0] - self.radius, 
                                         self.position[1] - self.radius/2,
                                         self.radius*2, self.radius))
        # Draw top dome
        pygame.draw.ellipse(screen, RED, (self.position[0] - self.radius/2, 
                                         self.position[1] - self.radius,
                                         self.radius, self.radius/2))
        
    def update(self, player):
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
        
        # Target the player
        dx = player.position[0] - self.position[0]
        dy = player.position[1] - self.position[1]
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
        screen.blit(surf, (int(self.position[0] - self.size), int(self.position[1] - self.size)))
        
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
    screen.fill(BLACK)
    
    # Draw background asteroids
    for asteroid in background_asteroids:
        asteroid.draw()
    
    # Draw title
    title_text = title_font.render("aSteroids", True, WHITE)
    screen.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, 150))
    
    # Create menu buttons
    start_button = Button(WIDTH // 2 - 100, 300, 200, 50, "Start Game", font)
    scores_button = Button(WIDTH // 2 - 100, 370, 200, 50, "High Scores", font)
    
    # Set which button is selected based on the index
    if selected_button_index == 0:
        start_button.is_selected = True
        scores_button.is_selected = False
    else:
        start_button.is_selected = False
        scores_button.is_selected = True
    
    # Check for mouse hover
    mouse_pos = pygame.mouse.get_pos()
    start_button.check_hover(mouse_pos)
    scores_button.check_hover(mouse_pos)
    
    # Draw buttons
    start_button.draw()
    scores_button.draw()
    
    # Update asteroids
    for asteroid in background_asteroids:
        asteroid.update()
    
    # Return button objects for event handling
    return start_button, scores_button

def draw_high_scores_screen(scores, background_asteroids):
    # Clear screen
    screen.fill(BLACK)
    
    # Draw background asteroids
    for asteroid in background_asteroids:
        asteroid.draw()
        asteroid.update()
    
    # Draw title
    title_text = big_font.render("High Scores", True, WHITE)
    screen.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, 50))
    
    # Draw scores
    y_pos = 120
    for i, (name, score, date) in enumerate(scores):
        score_text = font.render(f"{i+1}. {name}: {score}", True, WHITE)
        date_text = font.render(date, True, GREY)
        
        screen.blit(score_text, (WIDTH // 2 - 150, y_pos))
        screen.blit(date_text, (WIDTH // 2 + 100, y_pos))
        
        y_pos += 40
    
    # Draw back button
    back_button = Button(WIDTH // 2 - 100, 500, 200, 50, "Back to Menu", font)
    back_button.is_selected = True  # Always selected since it's the only button
    mouse_pos = pygame.mouse.get_pos()
    back_button.check_hover(mouse_pos)
    back_button.draw()
    
    return back_button

def draw_name_input_screen(score, text_input, background_asteroids):
    # Clear screen
    screen.fill(BLACK)
    
    # Draw background asteroids
    for asteroid in background_asteroids:
        asteroid.draw()
        asteroid.update()
    
    # Draw title
    title_text = big_font.render("Game Over", True, RED)
    screen.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, 100))
    
    # Draw score
    score_text = font.render(f"Your Score: {score}", True, WHITE)
    screen.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, 170))
    
    # Draw name input prompt
    prompt_text = font.render("Enter your name:", True, WHITE)
    screen.blit(prompt_text, (WIDTH // 2 - prompt_text.get_width() // 2, 240))
    
    # Draw text input
    text_input.update()
    text_input.draw()
    
    # Draw submit button
    submit_button = Button(WIDTH // 2 - 100, 380, 200, 50, "Submit Score", font)
    submit_button.is_selected = True  # Always selected since it's the only button
    mouse_pos = pygame.mouse.get_pos()
    submit_button.check_hover(mouse_pos)
    submit_button.draw()
    
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
    
    # Game objects
    player = None
    asteroids = []
    bullets = []
    ufos = []
    particles = []
    powerups = []
    laser_beam = None
    
    # Game state and variables
    game_state = TITLE_SCREEN
    score = 0
    level = 1
    selected_button_index = 0  # 0 = Start Game, 1 = High Scores
    
    # Create text input for name entry
    text_input = TextInput(WIDTH // 2 - 150, 300, 300, font)
    
    # Game timing variables
    last_shot_time = 0
    shot_cooldown = 250  # 250 ms between shots
    ufo_spawn_timer = pygame.time.get_ticks()
    ufo_spawn_delay = random.randint(10000, 20000)  # 10-20 seconds
    powerup_spawn_timer = pygame.time.get_ticks()
    powerup_spawn_delay = POWERUP_SPAWN_RATE * 1000  # Convert to milliseconds
    
    # Main game loop
    running = True
    while running:
        current_time = pygame.time.get_ticks()
        mouse_pos = pygame.mouse.get_pos()
        
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            # Handle title screen events
            if game_state == TITLE_SCREEN:
                start_button, scores_button = draw_title_screen(background_asteroids, selected_button_index)
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP or event.key == pygame.K_DOWN:
                        # Toggle between buttons
                        selected_button_index = 1 - selected_button_index
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        # Activate the selected button
                        if selected_button_index == 0:
                            # Start Game button
                            player = Player()
                            asteroids = []
                            bullets = []
                            ufos = []
                            particles = []
                            powerups = []
                            laser_beam = None
                            score = 0
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
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if start_button.is_clicked(mouse_pos, event):
                        # Start a new game
                        player = Player()
                        asteroids = []
                        bullets = []
                        ufos = []
                        particles = []
                        powerups = []
                        laser_beam = None
                        score = 0
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
                high_scores = get_high_scores(db_path)
                back_button = draw_high_scores_screen(high_scores, background_asteroids)
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE or event.key == pygame.K_ESCAPE:
                        game_state = TITLE_SCREEN
                        selected_button_index = 0  # Reset to Start Game being selected
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if back_button.is_clicked(mouse_pos, event):
                        game_state = TITLE_SCREEN
                        selected_button_index = 0  # Reset to Start Game being selected
            
            # Handle name input screen events
            elif game_state == NAME_INPUT:
                submit_button = draw_name_input_screen(score, text_input, background_asteroids)
                
                # Handle text input
                name = text_input.handle_event(event)
                if name:  # Enter key was pressed
                    if name.strip():  # Name is not empty
                        save_score(db_path, name, score)
                        game_state = HIGH_SCORES
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN and text_input.text.strip():
                        save_score(db_path, text_input.text, score)
                        game_state = HIGH_SCORES
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if submit_button.is_clicked(mouse_pos, event):
                        if text_input.text.strip():  # Name is not empty
                            save_score(db_path, text_input.text, score)
                            game_state = HIGH_SCORES
            
            # Handle gameplay events
            elif game_state == GAME_PLAYING:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        # Only handle shooting if laser beam isn't active
                        if not laser_beam:
                            # If rapid fire is active, don't apply cooldown
                            if player.active_powerup == 'rapid_fire' and player.rapid_fire_ammo > 0:
                                result = player.shoot()
                                if isinstance(result, Bullet):
                                    bullets.append(result)
                                    
                            # Handle shooting with cooldown for other weapons
                            elif current_time - last_shot_time > shot_cooldown:
                                result = player.shoot()
                                
                                # Handle different return types
                                if result == "laser":
                                    laser_beam = LaserBeam(player)
                                elif isinstance(result, Bullet):
                                    bullets.append(result)
                                    last_shot_time = current_time
                    
                    # Escape key to pause/return to title
                    elif event.key == pygame.K_ESCAPE:
                        game_state = TITLE_SCREEN
                        selected_button_index = 0
        
        # Only update the game if playing
        if game_state == GAME_PLAYING:
            # Get keys pressed
            keys = pygame.key.get_pressed()
            
            # Player controls
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                player.rotate(-1)
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                player.rotate(1)
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                player.thrust()
                
            # Rapid fire shooting
            if player.active_powerup == 'rapid_fire' and keys[pygame.K_SPACE] and player.rapid_fire_ammo > 0:
                if current_time - last_shot_time > 100:  # Faster firing rate
                    result = player.shoot()
                    if isinstance(result, Bullet):
                        bullets.append(result)
                        last_shot_time = current_time
                
            # Update player
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
                            exploded = True
                            break
                            
                    # If nuke exploded or lifetime is almost over, trigger nuclear explosion
                    if exploded or bullet.lifetime < 4:
                        # Flash screen
                        white_surface = pygame.Surface((WIDTH, HEIGHT))
                        white_surface.fill(WHITE)
                        screen.blit(white_surface, (0, 0))
                        pygame.display.flip()
                        pygame.time.delay(50)  # Flash duration
                        
                        # Generate explosion particles
                        for _ in range(100):
                            particles.append(Particle(
                                random.randint(0, WIDTH),
                                random.randint(0, HEIGHT),
                                random.choice([RED, YELLOW, WHITE])
                            ))
                        
                        # Destroy all asteroids and UFOs on screen
                        for asteroid in asteroids[:]:
                            score += (4 - asteroid.size) * 100
                            particles.extend(create_explosion(asteroid.position[0], asteroid.position[1], asteroid.size))
                        asteroids.clear()
                        
                        for ufo in ufos[:]:
                            score += 1000
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
            
            # Update laser beam
            if laser_beam:
                # Check for asteroid destruction by laser
                for asteroid in asteroids[:]:
                    if laser_beam.check_collision(asteroid):
                        # Add score based on asteroid size
                        score += (4 - asteroid.size) * 100
                        
                        # Create an explosion effect
                        particles.extend(create_explosion(asteroid.position[0], asteroid.position[1], asteroid.size, YELLOW))
                        
                        # Break the asteroid
                        fragments = asteroid.break_apart()
                        asteroids.extend(fragments)
                        
                        # Remove the asteroid
                        asteroids.remove(asteroid)
                
                # Check for UFO destruction by laser
                for ufo in ufos[:]:
                    if laser_beam.check_collision(ufo):
                        # Add score
                        score += 1000
                        
                        # Create an explosion effect
                        particles.extend(create_explosion(ufo.position[0], ufo.position[1], 2, YELLOW))
                        
                        # Remove the UFO
                        ufos.remove(ufo)
                
                # Update laser beam
                if laser_beam.update():
                    laser_beam = None
                    
            # Update powerups
            for powerup in powerups[:]:
                if powerup.update() or powerup.check_collision(player):
                    if powerup.check_collision(player):
                        # Player collected the powerup
                        player.collect_powerup(powerup.type)
                        # Create particle effect
                        particles.extend(create_explosion(
                            powerup.x, powerup.y, 2, 
                            PowerUp.COLORS[powerup.type]
                        ))
                    powerups.remove(powerup)
                    
            # Update asteroids
            for asteroid in asteroids[:]:
                asteroid.update()
                
                # Check collision with player
                if player.check_collision(asteroid):
                    player.lives -= 1
                    particles.extend(create_explosion(player.position[0], player.position[1], 2))
                    
                    if player.lives <= 0:
                        game_state = NAME_INPUT
                        text_input.text = ""
                        text_input.active = True
                    else:
                        player.respawn()
                        
                    # Create an explosion effect
                    particles.extend(create_explosion(asteroid.position[0], asteroid.position[1], asteroid.size))
                        
                    # Remove the asteroid
                    asteroids.remove(asteroid)
                    continue
                
                # Check if invincible player rammed into asteroid
                elif player.is_invincible:
                    # Calculate distance
                    distance = math.sqrt((player.position[0] - asteroid.position[0])**2 + 
                                        (player.position[1] - asteroid.position[1])**2)
                    if distance < player.radius + asteroid.radius:
                        # Add score based on asteroid size
                        score += (4 - asteroid.size) * 100
                        
                        # Create an explosion effect
                        particles.extend(create_explosion(asteroid.position[0], asteroid.position[1], asteroid.size, PURPLE))
                        
                        # Break the asteroid
                        fragments = asteroid.break_apart()
                        asteroids.extend(fragments)
                        
                        # Remove the asteroid
                        asteroids.remove(asteroid)
                        continue
                    
                # Check bullet collisions
                for bullet in bullets[:]:
                    if bullet.check_collision(asteroid):
                        # Add score based on asteroid size
                        score += (4 - asteroid.size) * 100
                        
                        # Create an explosion effect
                        particles.extend(create_explosion(asteroid.position[0], asteroid.position[1], asteroid.size))
                        
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
                ufo_bullet = ufo.update(player)
                
                # Check if the UFO is off-screen
                if ufo.is_off_screen():
                    ufos.remove(ufo)
                    continue
                    
                # Check collision with player
                if ufo.check_collision(player) and not player.is_invincible:
                    player.lives -= 1
                    particles.extend(create_explosion(player.position[0], player.position[1], 2))
                    particles.extend(create_explosion(ufo.position[0], ufo.position[1], 2))
                    
                    if player.lives <= 0:
                        game_state = NAME_INPUT
                        text_input.text = ""
                        text_input.active = True
                    else:
                        player.respawn()
                        
                    ufos.remove(ufo)
                    continue
                
                # Check if invincible player rammed into UFO
                elif player.is_invincible:
                    distance = math.sqrt((player.position[0] - ufo.position[0])**2 + 
                                        (player.position[1] - ufo.position[1])**2)
                    if distance < player.radius + ufo.radius:
                        # Add score
                        score += 1000
                        
                        # Create an explosion effect
                        particles.extend(create_explosion(ufo.position[0], ufo.position[1], 2, PURPLE))
                        
                        # Remove the UFO
                        ufos.remove(ufo)
                        continue
                    
                # Check bullet collisions
                for bullet in bullets[:]:
                    if ufo.check_collision(bullet):
                        # Add score
                        score += 1000
                        
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
            
            # Update particles
            for particle in particles[:]:
                particle.update()
                if particle.is_dead():
                    particles.remove(particle)
                    
            # Check if level is complete
            if len(asteroids) == 0:
                level += 1
                
                # Spawn more asteroids each level
                for _ in range(4 + level):
                    # Make sure asteroids don't spawn directly on the player
                    while True:
                        asteroid = Asteroid()
                        dx = asteroid.position[0] - player.position[0]
                        dy = asteroid.position[1] - player.position[1]
                        dist = math.sqrt(dx*dx + dy*dy)
                        if dist > 100:  # Safe distance
                            break
                    asteroids.append(asteroid)
            
            # Spawn UFO if it's time
            if current_time - ufo_spawn_timer > ufo_spawn_delay and len(ufos) < 1:
                ufos.append(UFO())
                ufo_spawn_timer = current_time
                ufo_spawn_delay = random.randint(10000, 20000)  # 10-20 seconds
                
            # Spawn power-up if it's time
            if current_time - powerup_spawn_timer > powerup_spawn_delay and len(powerups) < 2:
                # Choose a location away from the player
                while True:
                    x = random.randint(50, WIDTH - 50)
                    y = random.randint(50, HEIGHT - 50)
                    dx = x - player.position[0]
                    dy = y - player.position[1]
                    dist = math.sqrt(dx*dx + dy*dy)
                    if dist > 100:  # Safe distance
                        break
                        
                powerups.append(PowerUp(x, y))
                powerup_spawn_timer = current_time
                powerup_spawn_delay = POWERUP_SPAWN_RATE * 1000  # Convert to milliseconds
            
            # Draw everything
            screen.fill(BLACK)
            
            # Draw player
            player.draw()
            
            # Draw laser beam if active
            if laser_beam:
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
            
            # Draw score
            score_text = font.render(f"Score: {score}", True, WHITE)
            level_text = font.render(f"Level: {level}", True, WHITE)
            
            # Draw lives
            lives_text = font.render(f"Lives: {player.lives}", True, WHITE)
            
            # Draw power-up status
            power_text = None
            if player.is_invincible:
                remaining = 10 - (current_time - player.invincible_timer) // 1000
                power_text = font.render(f"Invincibility: {max(0, remaining)}s", True, PURPLE)
            elif player.has_laser:
                power_text = font.render("Laser Ready!", True, YELLOW)
            elif player.has_nuke:
                power_text = font.render("Nuclear Bomb Ready!", True, GREY)
            elif player.active_powerup == 'rapid_fire':
                power_text = font.render(f"Rapid Fire: {player.rapid_fire_ammo}", True, RED)
                
            screen.blit(score_text, (10, 10))
            screen.blit(level_text, (WIDTH - level_text.get_width() - 10, 10))
            screen.blit(lives_text, (WIDTH // 2 - lives_text.get_width() // 2, 10))
            
            if power_text:
                screen.blit(power_text, (10, HEIGHT - 40))
        
        # Update the display
        pygame.display.flip()
        clock.tick(FPS)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()