"""Side-view body and digestive tract, in a virtual 600 x 820 coordinate space."""
import math
from bisect import bisect_left

VW, VH = 600, 820


def chaikin(pts, n):
    """Corner-cutting subdivision: turns a rough polyline into a smooth curve."""
    for _ in range(n):
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            out += [(a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25), (a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75)]
        out.append(pts[-1])
        pts = out
    return pts


class Path:
    def __init__(self, pts):
        self.pts = [tuple(map(float, p)) for p in pts]
        self.cum = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.length = self.cum[-1]

    def at(self, d):
        """(x, y, heading) at distance d along the path."""
        d = max(0.0, min(self.length, d))
        i = max(1, min(len(self.cum) - 1, bisect_left(self.cum, d)))
        a, b = self.pts[i - 1], self.pts[i]
        seg = (self.cum[i] - self.cum[i - 1]) or 1.0
        k = (d - self.cum[i - 1]) / seg
        return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, math.atan2(b[1] - a[1], b[0] - a[0])


def chaikin_closed(pts, n):
    for _ in range(n):
        out = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            out += [(a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25), (a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75)]
        pts = out
    return pts


# ---------- body: a chunky cartoon buddy, side view facing right ----------
# Big round head, bean-shaped torso with a round belly, stubby legs and a waving arm.
HEAD_C, HEAD_R = (312, 84), 100      # the head and hair poke above y=0: the renderer leaves TOP room
TOP = 44
TORSO = chaikin_closed([
    (292, 176), (352, 176), (370, 194), (400, 220), (428, 256), (446, 300), (458, 350), (468, 400), (474, 450),
    (470, 505), (456, 556), (432, 600), (404, 632), (370, 654), (330, 664), (290, 662), (258, 652), (240, 632),
    (240, 600), (252, 560), (266, 520), (272, 470), (270, 420), (266, 370), (266, 320), (272, 270), (282, 220)], 3)
LEGS = (((318, 640), (314, 768)), ((374, 640), (378, 768)))   # (hip, ankle): far leg first
LEG_W = 46
SHOULDER = (362, 240)
ARM_UPPER, ARM_FORE = 60, 52
EYES = ((352, 62, 17, 21), (390, 66, 10, 19))                  # (x, y, rx, ry): near eye, far eye
NOSE = (412, 100)
EAR = (286, 96)
HAIR = ((286, -20), (312, -27), (338, -20))

MOUTH = (390, 147)
CHEEK = (366, 122)
ANUS = (264, 632)
EYE = EYES[0][:2]

# ---------- stomach: J-shaped pouch ----------
# Oesophagus enters at the top (cardia); the bulging fundus rises to its left; the greater
# curvature sweeps round the bottom to the pylorus, which empties into the duodenum.
STOMACH = chaikin_closed([
    (344, 333), (334, 324), (320, 324), (310, 334), (306, 350), (308, 368), (315, 385), (327, 398), (343, 406),
    (361, 408), (377, 404), (389, 395), (396, 385), (399, 376), (393, 371), (384, 375), (374, 374), (366, 366),
    (362, 354), (360, 342), (357, 334)], 3)
STOM_CX, STOM_CY = 342, 372          # inside the pouch, where food collects
STOM_W, STOM_H = 64, 44              # area where bubbles form
PYLORUS = (398, 380)


def stomach_extent():
    xs, ys = [p[0] for p in STOMACH], [p[1] for p in STOMACH]
    return min(xs), min(ys), max(xs), max(ys)


_ESO = [(390, 147), (372, 152), (350, 170), (334, 205), (327, 250), (327, 290), (338, 318), (350, 334)]
P_ESO = Path(chaikin(_ESO, 3))
P_TO_STOM = Path(chaikin(_ESO + [(347, 352), (STOM_CX, STOM_CY)], 3))

# ---------- small intestine: duodenum then loose coils ----------
_SI = [PYLORUS, (404, 392), (402, 410), (390, 420)]
for _r in range(6):
    _y = 434 + 19 * _r
    xs = range(388, 318, -7) if _r % 2 == 0 else range(318, 388, 7)
    for _k, _x in enumerate(xs):   # each pass wiggles, so the loops look coiled instead of ruled
        _SI.append((_x, _y + 5.5 * math.sin(_k * 1.3 + _r * 2.1)))
_SI.append((400, 548))
P_SI = Path(chaikin(_SI, 2))

# ---------- large intestine: ascending, transverse, descending, sigmoid, rectum ----------
P_COLON = Path(chaikin([(400, 552), (406, 540), (407, 470), (405, 424), (396, 414), (360, 418), (325, 412),
                        (304, 420), (298, 445), (299, 500), (300, 556), (308, 580), (290, 604), (272, 620), ANUS], 3))
P_BYPASS = Path(chaikin([(327, 255), (321, 285), (306, 315), (297, 350), (295, 390), (299, 430)], 3))
P_BEANS = Path(chaikin([(390, 147), (372, 152), (350, 170), (334, 205), (327, 250), (321, 285), (306, 315),
                        (297, 350), (295, 390), (299, 432), (299, 500), (300, 556), (308, 580), (290, 600)], 3))

# Distance along P_BEANS where it leaves the esophagus: the moment a fart food gives itself away.
BRANCH_D = next(c for p, c in zip(P_BEANS.pts, P_BEANS.cum) if p[1] >= 262)
