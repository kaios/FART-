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


BODY = [  # front profile, facing right
    (300, 186), (281, 140), (283, 90), (306, 55), (345, 45), (380, 60), (392, 90), (393, 108), (409, 125), (394, 132),
    (396, 142), (389, 147), (396, 153), (388, 168), (370, 178), (355, 183), (352, 215), (382, 250), (410, 300),
    (406, 350), (421, 420), (426, 500), (411, 560), (386, 620), (381, 700), (366, 800),
]
BACK = [(300, 186), (298, 225), (285, 250), (278, 320), (282, 420), (275, 520), (260, 590), (258, 630), (275, 665),
        (285, 700), (291, 800)]
ARM = [(330, 248), (338, 350), (346, 452), (388, 520)]
MOUTH = (390, 147)
CHEEK = (378, 140)
ANUS = (266, 630)
EYE = (370, 88)
EAR = (318, 112)
STOM_CX, STOM_CY, STOM_W, STOM_H = 355, 365, 80, 60

_ESO = [(390, 147), (372, 152), (350, 170), (334, 205), (327, 250), (327, 290), (334, 322), (347, 338)]
P_ESO = Path(chaikin(_ESO, 3))
P_TO_STOM = Path(chaikin(_ESO + [(STOM_CX, STOM_CY)], 3))

_SI = [(375, 395), (375, 412), (392, 424)]
for _r in range(6):
    _y = 432 + 20 * _r
    _SI += [(312, _y), (392, _y)] if _r % 2 else [(392, _y), (312, _y)]
_SI.append((404, 546))
P_SI = Path(chaikin(_SI, 2))

P_COLON = Path(chaikin([(402, 548), (410, 540), (410, 425), (402, 413), (306, 413), (297, 422), (297, 560), (306, 580),
                        (288, 602), ANUS], 2))
P_BYPASS = Path(chaikin([(327, 255), (322, 285), (306, 315), (296, 350), (294, 390), (297, 428)], 3))
P_BEANS = Path(chaikin([(390, 147), (372, 152), (350, 170), (334, 205), (327, 250), (322, 285), (306, 315), (296, 350),
                        (294, 390), (297, 430), (297, 560), (306, 580), (290, 600)], 3))

# Distance along P_BEANS where it leaves the esophagus: the moment a fart food gives itself away.
BRANCH_D = next(c for p, c in zip(P_BEANS.pts, P_BEANS.cum) if p[1] >= 262)
