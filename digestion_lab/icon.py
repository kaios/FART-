"""The app icon, drawn in code. Used for the window icon and by the packaging scripts."""
import pygame
import pygame.gfxdraw as gfx

BG = (11, 15, 23)
WIRE = (143, 211, 255)
BLUE = (63, 180, 255)
GREEN = (93, 255, 122)
YELLOW = (255, 216, 74)


def make_icon(size=256):
    """Render at 4x and downscale for smooth edges."""
    big = size * 4
    s = pygame.Surface((big, big), pygame.SRCALPHA)
    k = big / 512

    def P(x, y):
        return int(x * k), int(y * k)

    def W(w):
        return max(1, int(w * k))

    pygame.draw.rect(s, BG, (0, 0, big, big), border_radius=int(112 * k))
    pygame.draw.lines(s, WIRE, False, [P(196, 70), P(192, 130), P(176, 190)], W(18))
    pygame.draw.rect(s, WIRE, (*P(150, 190), W(150), W(104)), W(16), border_radius=W(10))
    pygame.draw.lines(s, WIRE, False, [P(260, 294), P(260, 320), P(330, 320), P(330, 354), P(170, 354),
                                       P(170, 388), P(330, 388), P(330, 422), P(190, 422)], W(14))
    pygame.draw.circle(s, BLUE, P(208, 246), W(22), W(10))
    pygame.draw.circle(s, BLUE, P(252, 232), W(12), W(8))
    for (cx, cy, r, w) in ((372, 420, 26, 8), (410, 380, 16, 6)):
        gfx.filled_circle(s, *P(cx, cy), W(r), (*GREEN, 90))
        pygame.draw.circle(s, GREEN, P(cx, cy), W(r), W(w))
    pygame.draw.circle(s, YELLOW, P(340, 150), W(10))
    pygame.draw.circle(s, YELLOW, P(372, 122), W(7))
    return pygame.transform.smoothscale(s, (size, size))


def write_ico(path, png_paths):
    """Write a .ico that embeds PNG images (supported since Windows Vista)."""
    import struct
    blobs = []
    for p in png_paths:
        with open(p, 'rb') as fh:
            data = fh.read()
        w, h = struct.unpack('>II', data[16:24])
        blobs.append((w, h, data))
    header = struct.pack('<HHH', 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries, body = b'', b''
    for w, h, data in blobs:
        entries += struct.pack('<BBBBHHII', w % 256, h % 256, 0, 0, 1, 32, len(data), offset + len(body))
        body += data
    with open(path, 'wb') as fh:
        fh.write(header + entries + body)
