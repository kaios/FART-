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


# ---------- body: smooth side profile facing right ----------
# Front line: nape -> back of head -> face -> neck -> chest -> belly -> front of leg.
BODY = chaikin([
    (300, 192), (291, 172), (284, 150), (280, 124), (283, 98), (292, 75), (308, 58), (330, 47), (352, 45),
    (371, 52), (384, 66), (391, 84), (393, 99), (397, 108), (403, 117), (410, 127), (405, 133), (397, 135),
    (398, 141), (392, 146), (397, 151), (393, 158), (394, 166), (386, 173), (372, 178), (360, 184), (354, 197),
    (353, 213), (360, 228), (377, 240), (396, 258), (408, 282), (410, 306), (403, 330), (405, 352), (414, 386),
    (422, 420), (425, 456), (421, 492), (412, 526), (400, 556), (392, 586), (390, 616), (392, 650), (390, 700),
    (384, 750), (378, 800)], 3)
# Back line: nape -> shoulder blade -> lower back (lumbar curve) -> buttocks -> back of leg.
BACK = chaikin([
    (300, 192), (298, 214), (290, 234), (283, 262), (279, 300), (281, 340), (286, 382), (289, 420), (290, 452),
    (284, 488), (272, 522), (260, 558), (254, 596), (258, 628), (268, 650), (281, 667), (286, 700), (289, 750),
    (292, 800)], 3)
ARM_BACK = chaikin([(318, 246), (321, 330), (329, 420), (336, 446), (368, 494), (388, 512)], 2)
ARM_FRONT = chaikin([(346, 250), (351, 330), (353, 412), (357, 426), (386, 478), (402, 498)], 2)
HAND = chaikin_closed([(388, 512), (402, 498), (412, 504), (414, 516), (406, 526), (393, 524)], 2)
EAR_OUTER = chaikin([(322, 100), (312, 101), (307, 112), (309, 125), (316, 133), (322, 130)], 2)
EAR_INNER = chaikin([(318, 108), (313, 113), (314, 122), (318, 125)], 1)
EYE_SHAPE = chaikin_closed([(362, 88), (369, 84), (377, 87), (370, 91)], 2)
BROW = chaikin([(359, 79), (369, 75), (381, 78)], 2)
NOSTRIL = chaikin([(399, 129), (403, 131), (406, 130)], 1)
LIPS = chaikin([(384, 146), (392, 146)], 1)
JAW = chaikin([(340, 150), (352, 166), (372, 177)], 2)
# Ribs: short arcs on the chest; spine: a dotted line just inside the back.
RIBS = [chaikin([(292 + i * 2, 262 + i * 15), (340, 254 + i * 17), (392 - i * 2, 268 + i * 15)], 2) for i in range(5)]
SPINE = chaikin([(304, 200), (298, 260), (296, 320), (299, 380), (302, 440), (296, 500), (284, 560)], 2)
NAVEL = chaikin([(421, 466), (417, 470), (421, 474)], 1)

MOUTH = (390, 147)
CHEEK = (378, 140)
ANUS = (264, 632)
EYE = (370, 88)
EAR = (316, 117)

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
