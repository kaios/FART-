"""Every food: its category, a line icon (drawn in a 24x24 grid), names and a short fact."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Food:
    id: str
    cat: str
    name: dict
    fact: dict
    icon: tuple


# Icon shape helpers. Each icon is a tuple of ('lines', points, closed) and ('circle', cx, cy, r).
def _quad(p0, p1, p2, n=10):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / n for i in range(n + 1))]


def _arc(cx, cy, r, a0, a1, n=16):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def _ellipse(cx, cy, rx, ry, rot=0.0, n=28):
    c, s = math.cos(rot), math.sin(rot)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return pts


def _rrect(x, y, w, h, r):
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -math.pi / 2), (x + w - r, y + h - r, 0),
                       (x + r, y + h - r, math.pi / 2), (x + r, y + r, math.pi)):
        pts += _arc(cx, cy, r, a0, a0 + math.pi / 2, 4)
    return pts


def _smooth_closed(pts, n=2):
    for _ in range(n):
        out = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            out += [(a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25), (a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75)]
        pts = out
    return pts


def L(points, closed=False):
    return ('lines', tuple(points), closed)


def C(cx, cy, r):
    return ('circle', cx, cy, r)


def _bowl(y):
    return L([(3, y)] + _arc(12, y, 9, 0, math.pi) + [(3, y)])


ICONS = {
    'soda': (L(_rrect(7, 3, 10, 18, 2), True), L([(7, 7), (17, 7)]), L([(7, 17), (17, 17)])),
    'sparkling': (L([(6, 3), (18, 3), (16, 21), (8, 21)], True), C(11, 15, 1), C(13.5, 10.5, 1), C(10.5, 7.5, .7)),
    'ramune': (L([(9, 21), (15, 21), (15, 11), (13.5, 9), (13.5, 5), (10.5, 5), (10.5, 9), (9, 11)], True), C(12, 9.5, 1.3)),
    'kombucha': (L(_rrect(6, 7, 12, 14, 2), True), L([(8, 7), (8, 4), (16, 4), (16, 7)]),
                 C(10, 13, .8), C(14, 16, .8), C(12.5, 10.5, .7)),
    'beans': (L(_ellipse(12, 12, 8, 5, math.radians(-30)), True), L(_quad((8.5, 13.5), (12, 14), (15, 10.5)))),
    'broccoli': (C(8, 9.5, 3.5), C(16, 9.5, 3.5), C(12, 6.5, 3.5), L([(10, 13), (11, 21), (13, 21), (14, 13)])),
    'sweetpotato': (L(_smooth_closed([(4, 15), (6, 10), (11, 7), (17, 7), (19, 11), (17, 15), (13, 17), (7, 18.5)]), True),
                    L([(17, 7), (20, 5)])),
    'cabbage': (C(12, 12, 8), L(_quad((12, 4), (8, 12), (12, 20))), L(_quad((12, 4), (16, 12), (12, 20))),
                L(_quad((4.5, 10), (12, 12), (19.5, 10)))),
    'onion': (L(_smooth_closed([(12, 3.5), (8, 8), (5, 12), (5, 15.5), (8, 19), (12, 20), (16, 19), (19, 15.5), (19, 12), (16, 8)]), True),
              L([(12, 4), (12, 2)]), L(_quad((12, 20), (9.5, 13.5), (12, 7))), L(_quad((12, 20), (14.5, 13.5), (12, 7)))),
    'rice': (_bowl(12), L(_quad((7, 12), (12, 5), (17, 12)))),
    'banana': (L([(5, 5), (5.5, 10), (8, 14), (12, 16.5), (16, 17.3), (20, 17), (18, 19.5), (13, 20.5), (8, 19),
                  (5.5, 15.5), (4.3, 11), (4.5, 7)], True), L([(5, 5), (4, 3.5)])),
    'toast': (L([(5, 20), (5, 10), (3.6, 8), (3.4, 5.5), (5, 3.6), (7, 3), (17, 3), (19, 3.6), (20.6, 5.5), (20.4, 8), (19, 10), (19, 20)], True),
              L([(8, 12), (16, 12)]), L([(8, 15), (16, 15)])),
    'okayu': (_bowl(12), L([(9, 9.5), (8, 8), (9.5, 6.8), (8.6, 5)]), L([(15, 9.5), (14, 8), (15.5, 6.8), (14.6, 5)])),
    'udon': (_bowl(13), L([(8, 13), (8, 6)]), L([(11, 13), (11, 4)]), L([(14, 13), (14, 5)]), L([(18, 3), (7, 7.5)])),
}

_DATA = [
    # burp: carbonation
    ('soda', 'burp', 'Carbonated Soda', '炭酸ソーダ',
     'The fizz is dissolved CO2. Warmed up in your stomach, it turns back into gas and escapes upward.',
     'シュワシュワの正体は二酸化炭素。胃で温まると気体に戻って上へ逃げていく。'),
    ('sparkling', 'burp', 'Sparkling Water', '炭酸水',
     'No sugar, same bubbles. It is the gas, not the sugar, that makes you burp.',
     '砂糖ゼロでも泡は同じ。ゲップの原因は糖ではなく炭酸ガス。'),
    ('ramune', 'burp', 'Ramune', 'ラムネ',
     "Japan's marble-sealed soda. Pushing the marble in releases a rush of CO2.",
     'ビー玉で栓をした日本の炭酸飲料。ビー玉を落とすと炭酸ガスが一気に出る。'),
    ('kombucha', 'burp', 'Kombucha', 'コンブチャ',
     'Fermented tea that is naturally fizzy: yeast and bacteria make the bubbles.',
     '酵母と細菌の発酵で自然に炭酸が生まれるお茶。'),
    # fart: fermentable carbs
    ('beans', 'fart', 'Beans', '豆',
     "Beans contain sugars (oligosaccharides) we can't digest. Gut bacteria ferment them into gas.",
     '豆には人が消化できない糖（オリゴ糖）が含まれ、腸内細菌がそれを発酵させてガスを作る。'),
    ('broccoli', 'fart', 'Broccoli', 'ブロッコリー',
     'Contains raffinose, a sugar that gut bacteria turn into gas.',
     'ラフィノースという糖を含み、腸内細菌がガスに変える。'),
    ('sweetpotato', 'fart', 'Sweet Potato', 'さつまいも',
     'Famous in Japan for causing farts: its fiber is a feast for gut bacteria.',
     'おならの原因として有名。食物繊維が腸内細菌のごちそうになる。'),
    ('cabbage', 'fart', 'Cabbage', 'キャベツ',
     'Like broccoli, it carries raffinose all the way to your large intestine.',
     'ブロッコリーと同じく、ラフィノースが大腸まで届く。'),
    ('onion', 'fart', 'Onions', '玉ねぎ',
     'Contains fructans, which bacteria ferment in the large intestine.',
     'フルクタンを含み、大腸で細菌が発酵させる。'),
    # smooth: easily absorbed
    ('rice', 'smooth', 'White Rice', '白ごはん',
     'Its starch is broken down and absorbed in the small intestine, leaving little for gas.',
     'でんぷんは小腸で分解・吸収され、ガスの材料がほとんど残らない。'),
    ('banana', 'smooth', 'Bananas', 'バナナ',
     'Ripe bananas are soft and gentle on the stomach.',
     '熟したバナナはやわらかく、胃にやさしい。'),
    ('toast', 'smooth', 'Plain Toast', 'トースト',
     'Plain toast is a classic gentle food when your stomach is upset.',
     'プレーンなトーストは、おなかの調子が悪いときの定番。'),
    ('okayu', 'smooth', 'Okayu (Rice Porridge)', 'おかゆ',
     "Japanese rice porridge: the go-to meal when you're feeling unwell.",
     '体調が悪いときの定番、日本のおかゆ。'),
    ('udon', 'smooth', 'Udon Noodles', 'うどん',
     'Soft wheat noodles that are easy on the tummy.',
     'やわらかい小麦の麺で、おなかにやさしい。'),
]

FOODS = [Food(id=i, cat=c, name={'en': ne, 'ja': nj}, fact={'en': fe, 'ja': fj}, icon=ICONS[i])
         for i, c, ne, nj, fe, fj in _DATA]
FOOD_BY_ID = {f.id: f for f in FOODS}
