#!/usr/bin/python3
import numpy as np
import pygame

_GRID = 32
_initialized = False
_screen = None
_cell = None
_scale = 12


def init(pixel_scale: int = 12):
    global _initialized, _screen, _cell, _scale
    if _initialized:
        return
    _scale = pixel_scale
    pygame.init()
    pygame.display.set_caption("JBAZZ LED sim")
    side = _GRID * _scale
    _screen = pygame.display.set_mode((side, side))
    _cell = pygame.Surface((_GRID, _GRID))
    _initialized = True


def shutdown():
    global _initialized, _screen, _cell
    if not _initialized:
        return
    pygame.quit()
    _initialized = False
    _screen = None
    _cell = None


def show(frame: np.ndarray):
    global _initialized, _screen, _cell
    if not _initialized:
        init()
    if frame.shape != (_GRID, _GRID, 3) or frame.dtype != np.uint8:
        raise ValueError(f"expected ({_GRID}, {_GRID}, 3) uint8, got {frame.shape} {frame.dtype}")
    # framebuffer is (y, x, c); blit_array wants (width, height, 3) == (x, y, c)
    arr = np.ascontiguousarray(np.swapaxes(frame, 0, 1))
    pygame.surfarray.blit_array(_cell, arr)
    big = pygame.transform.scale(_cell, (_screen.get_width(), _screen.get_height()))
    _screen.blit(big, (0, 0))
    pygame.display.flip()
    pygame.event.pump()
