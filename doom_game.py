import math
import sys
from pathlib import Path

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
    "111111",
    "1....1",
    "1....1",
    "1....1",
    "111111",
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


def main():
    pg.init()
    sc = pg.display.set_mode((WIDTH, HEIGHT))
    clock = pg.time.Clock()
    pos = [HALF_WIDTH, HALF_HEIGHT]
    angle = 0
    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
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
        sc.fill(pg.Color("black"))
        ray_casting(sc, pos, angle)
        pg.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
