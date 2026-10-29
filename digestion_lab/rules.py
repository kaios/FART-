"""Pure game rules: modes, scoring, streaks and speed. No pygame, fully unit-tested."""
import random
from dataclasses import dataclass
from typing import Optional

CATS = ('burp', 'fart', 'smooth')

MODE_RULES = {
    'classic': {'rounds': 8, 'step': 0.0, 'max': 1.0, 'bonus': False},
    'rush':    {'time': 60.0, 'step': 0.05, 'max': 2.0, 'bonus': True},
    'endless': {'lives': 3, 'step': 0.05, 'max': 2.2, 'bonus': True},
}

DIFFICULTY = {
    'easy':   {'speed': 0.8, 'mystery': False},
    'normal': {'speed': 1.0, 'mystery': False},
    'hard':   {'speed': 1.2, 'mystery': True},
}

BASE_POINTS = 100
STREAK_BONUS_STEP = 25
MAX_STREAK_BONUS = 200


@dataclass
class Session:
    mode: str
    difficulty: str = 'normal'
    score: int = 0
    round: int = 0
    streak: int = 0
    best_streak: int = 0
    correct: int = 0
    lives: Optional[int] = None
    time_left: Optional[float] = None


@dataclass
class Result:
    ok: bool
    points: int
    bonus: int
    late: bool
    life_lost: bool


def create_session(mode, difficulty='normal'):
    if mode not in MODE_RULES:
        raise ValueError(f'Unknown mode: {mode}')
    if difficulty not in DIFFICULTY:
        raise ValueError(f'Unknown difficulty: {difficulty}')
    r = MODE_RULES[mode]
    return Session(mode=mode, difficulty=difficulty, lives=r.get('lives'), time_left=r.get('time'))


def speed_for(s):
    """Travel-speed multiplier for the current round. Classic stays flat; Rush/Endless ramp up."""
    r = MODE_RULES[s.mode]
    return DIFFICULTY[s.difficulty]['speed'] * min(r['max'], 1 + r['step'] * max(0, s.round - 1))


def can_start_round(s):
    if s.mode == 'classic':
        return s.round < MODE_RULES['classic']['rounds']
    if s.mode == 'rush':
        return s.time_left > 0
    return s.lives > 0


def begin_round(s):
    if not can_start_round(s):
        return False
    s.round += 1
    return True


def resolve(s, choice, actual):
    """Score a prediction. choice=None means the food arrived before the player decided."""
    ok = choice == actual
    bonus = points = 0
    life_lost = False
    if ok:
        s.streak += 1
        s.correct += 1
        s.best_streak = max(s.best_streak, s.streak)
        if MODE_RULES[s.mode]['bonus']:
            bonus = min(MAX_STREAK_BONUS, STREAK_BONUS_STEP * (s.streak - 1))
        points = BASE_POINTS + bonus
        s.score += points
    else:
        s.streak = 0
        if s.lives is not None and s.lives > 0:
            s.lives -= 1
            life_lost = True
    return Result(ok=ok, points=points, bonus=bonus, late=choice is None, life_lost=life_lost)


def tick(s, dt):
    if s.time_left is not None:
        s.time_left = max(0.0, s.time_left - dt)


def is_over(s):
    return not can_start_round(s)


def accuracy(s):
    return s.correct / s.round if s.round else 0.0


def rank_index(s):
    """0 = keep chewing, 1 = solid, 2 = genius."""
    a = accuracy(s)
    return 2 if a >= 0.9 else 1 if a >= 0.6 else 0


def pick_menu(foods, rng=random, per_cat=2):
    """Two foods from each category in random order: the six items on the menu card."""
    picked = []
    for c in CATS:
        pool = [f for f in foods if f.cat == c]
        picked += rng.sample(pool, per_cat)
    rng.shuffle(picked)
    return picked


MENU_SIZE = 6
LEVEL_EVERY = 2
MAX_LEVEL = 5


def level_for(round_no):
    """Level 1..5: a new level every LEVEL_EVERY rounds. Round 0 (before the first food) is level 1."""
    return min(MAX_LEVEL, 1 + max(0, round_no - 1) // LEVEL_EVERY)


class FoodDeck:
    """Deals the menu so food doesn't repeat.

    Foods come from a shuffled pile; a food only returns after the pile runs out, and never
    within RECENT eats of being eaten. Eating a food replaces its slot with a fresh one,
    preferring a category the menu is missing, so there is always at least one burp, one fart
    and one smooth food to choose from.
    """
    RECENT = 3

    def __init__(self, foods, rng=random, size=MENU_SIZE):
        self.foods = list(foods)
        self.rng = rng
        self.pile = []
        self.eaten = []
        self.menu = []
        for _ in range(size):
            self.menu.append(self._draw())

    def _blocked(self):
        return {f.id for f in self.menu} | {f.id for f in self.eaten[-self.RECENT:]}

    def _refill(self):
        blocked = self._blocked()
        self.pile = [f for f in self.foods if f.id not in blocked]
        self.rng.shuffle(self.pile)

    def _draw(self):
        if not self.pile:
            self._refill()
        have = {f.cat for f in self.menu}
        missing = [c for c in CATS if c not in have]
        if not missing:
            return self.pile.pop(0)
        for i, f in enumerate(self.pile):
            if f.cat in missing:
                return self.pile.pop(i)
        # The pile has none of the missing category: borrow one that isn't blocked.
        blocked = self._blocked()
        spare = [f for f in self.foods if f.cat in missing and f.id not in blocked]
        return self.rng.choice(spare) if spare else self.pile.pop(0)

    def eat(self, food):
        """Mark a food eaten and refill its slot. Returns the slot index that changed."""
        i = next(k for k, f in enumerate(self.menu) if f.id == food.id)
        self.eaten.append(food)
        del self.menu[i]
        self.menu.insert(i, self._draw())
        return i
