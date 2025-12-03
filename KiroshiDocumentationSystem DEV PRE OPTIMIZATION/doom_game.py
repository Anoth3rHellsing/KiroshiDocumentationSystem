import math
import random
import sys

import pygame as pg

WIDTH, HEIGHT = 640, 480
HALF_WIDTH, HALF_HEIGHT = WIDTH // 2, HEIGHT // 2
TILE = 64
FOV = math.pi / 3
HALF_FOV = FOV / 2
NUM_RAYS = WIDTH // 2
MAX_DEPTH = 800
DELTA_ANGLE = FOV / NUM_RAYS
DIST = NUM_RAYS / (2 * math.tan(HALF_FOV))
PROJ_COEFF = DIST * TILE
SCALE = WIDTH // NUM_RAYS

MAP = [
    "111111111",
    "1.......1",
    "1.......1",
    "1.......1",
    "1.......1",
    "1.......1",
    "1.......1",
    "1.......1",
    "111111111",
]

WORLD_MAP = {}
for j, row in enumerate(MAP):
    for i, col in enumerate(row):
        if col == "1":
            WORLD_MAP[(i * TILE, j * TILE)] = 1


def mapping(x: float, y: float):
    return (x // TILE) * TILE, (y // TILE) * TILE


def ray_casting(sc: pg.Surface, pos, angle):
    cur_angle = angle - HALF_FOV
    for ray in range(NUM_RAYS):
        sin_a = math.sin(cur_angle)
        cos_a = math.cos(cur_angle)
        for depth in range(1, MAX_DEPTH):
            x = pos[0] + depth * cos_a
            y = pos[1] + depth * sin_a
            if mapping(x, y) in WORLD_MAP:
                depth *= math.cos(angle - cur_angle)
                proj_height = PROJ_COEFF / depth
                color = 255 / (1 + depth * depth * 0.0001)
                pg.draw.rect(
                    sc,
                    (color, color, color),
                    (ray * SCALE, HALF_HEIGHT - proj_height // 2, SCALE, proj_height),
                )
                break
        cur_angle += DELTA_ANGLE


def draw_minimap(sc: pg.Surface, pos, angle, monsters):
    map_scale = 5
    map_tile = TILE // map_scale
    for x, y in WORLD_MAP:
        pg.draw.rect(
            sc,
            pg.Color("dimgray"),
            (x // map_scale, y // map_scale, map_tile, map_tile),
        )
    pg.draw.circle(
        sc,
        pg.Color("green"),
        (int(pos[0] / map_scale), int(pos[1] / map_scale)),
        5,
    )
    pg.draw.line(
        sc,
        pg.Color("green"),
        (int(pos[0] / map_scale), int(pos[1] / map_scale)),
        (
            int((pos[0] + math.cos(angle) * 40) / map_scale),
            int((pos[1] + math.sin(angle) * 40) / map_scale),
        ),
        2,
    )
    for m in monsters:
        pg.draw.circle(
            sc,
            pg.Color("red"),
            (int(m.x / map_scale), int(m.y / map_scale)),
            3,
        )


class Monster:
    surface = pg.Surface((TILE, TILE), pg.SRCALPHA)
    pg.draw.circle(surface, pg.Color("red"), (TILE // 2, TILE // 2), TILE // 2)

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def update(self, player_pos):
        dx = player_pos[0] - self.x
        dy = player_pos[1] - self.y
        dist = math.hypot(dx, dy)
        if dist:
            self.x += dx / dist
            self.y += dy / dist

    def distance_to(self, player_pos):
        return math.hypot(self.x - player_pos[0], self.y - player_pos[1])

    def draw(self, sc: pg.Surface, player_pos, angle):
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        distance = math.hypot(dx, dy)
        sprite_angle = math.atan2(dy, dx)
        delta = sprite_angle - angle
        if dx > 0 and angle > math.pi:
            delta += math.tau
        if dx < 0 and sprite_angle < 0:
            delta += math.tau
        delta = (delta + math.pi) % (2 * math.pi) - math.pi
        if -HALF_FOV < delta < HALF_FOV and distance:
            proj_height = PROJ_COEFF / distance
            proj_width = proj_height
            sprite = pg.transform.scale(
                self.surface, (int(proj_width), int(proj_height))
            )
            x = HALF_WIDTH + delta * DIST - proj_width // 2
            sc.blit(sprite, (x, HALF_HEIGHT - proj_height // 2))


def random_spawn():
    while True:
        x = random.randint(1, len(MAP[0]) - 2) * TILE + TILE // 2
        y = random.randint(1, len(MAP) - 2) * TILE + TILE // 2
        if mapping(x, y) not in WORLD_MAP:
            return x, y


def shoot(monsters, pos, angle):
    for m in monsters[:]:
        dx = m.x - pos[0]
        dy = m.y - pos[1]
        distance = math.hypot(dx, dy)
        target_angle = math.atan2(dy, dx)
        delta = (target_angle - angle + math.pi) % (2 * math.pi) - math.pi
        if distance < 300 and abs(delta) < 0.1:
            monsters.remove(m)


class Weapon:
    def __init__(self, base_color, shot_color):
        self.base = pg.Surface((120, 80), pg.SRCALPHA)
        pg.draw.rect(self.base, base_color, (20, 20, 80, 60))
        self.shot = pg.Surface((120, 80), pg.SRCALPHA)
        pg.draw.rect(self.shot, base_color, (20, 20, 80, 60))
        pg.draw.rect(self.shot, shot_color, (80, 0, 20, 20))
        self.image = self.base
        self.cooldown = 0

    def fire(self):
        self.cooldown = 5

    def update(self):
        if self.cooldown > 0:
            self.cooldown -= 1
            self.image = self.shot
        else:
            self.image = self.base

    def draw(self, sc: pg.Surface):
        sc.blit(
            self.image,
            (HALF_WIDTH - self.image.get_width() // 2, HEIGHT - self.image.get_height()),
        )


def main():
    pg.init()
    pg.mixer.quit()
    sc = pg.display.set_mode((WIDTH, HEIGHT))
    clock = pg.time.Clock()
    pos = [TILE + TILE // 2, TILE + TILE // 2]
    angle = 0
    weapons = [
        Weapon(pg.Color("gray"), pg.Color("orange")),
        Weapon(pg.Color("blue"), pg.Color("yellow")),
    ]
    weapon_index = 0
    monsters: list[Monster] = []
    spawn_timer = 0
    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                weapons[weapon_index].fire()
                shoot(monsters, pos, angle)
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_1:
                    weapon_index = 0
                elif event.key == pg.K_2:
                    weapon_index = 1
        keys = pg.key.get_pressed()
        if keys[pg.K_LEFT]:
            angle -= 0.04
        if keys[pg.K_RIGHT]:
            angle += 0.04
        dx = dy = 0
        speed = 2
        if keys[pg.K_w]:
            dx += speed * math.cos(angle)
            dy += speed * math.sin(angle)
        if keys[pg.K_s]:
            dx -= speed * math.cos(angle)
            dy -= speed * math.sin(angle)
        if keys[pg.K_a]:
            dx += speed * math.sin(angle)
            dy -= speed * math.cos(angle)
        if keys[pg.K_d]:
            dx -= speed * math.sin(angle)
            dy += speed * math.cos(angle)
        pos[0] += dx
        pos[1] += dy

        for m in monsters:
            m.update(pos)
        spawn_timer += 1
        if spawn_timer > 120:
            spawn_timer = 0
            monsters.append(Monster(*random_spawn()))

        sc.fill(pg.Color("black"))
        ray_casting(sc, pos, angle)
        for m in sorted(monsters, key=lambda m: -m.distance_to(pos)):
            m.draw(sc, pos, angle)
        draw_minimap(sc, pos, angle, monsters)
        weapons[weapon_index].update()
        weapons[weapon_index].draw(sc)
        pg.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
