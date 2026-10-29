import random
import unittest

from digestion_lab.achievements import evaluate
from digestion_lab.foods import FOODS
from digestion_lab.rules import (CATS, begin_round, can_start_round, create_session, is_over, pick_menu,
                                 rank_index, resolve, speed_for, tick)


class RulesTest(unittest.TestCase):
    def test_classic_scores_100_per_correct_and_ends_after_8(self):
        s = create_session('classic')
        for i in range(8):
            self.assertTrue(begin_round(s))
            resolve(s, 'fart' if i % 2 else 'burp', 'burp')
        self.assertEqual(s.score, 400)
        self.assertEqual(s.correct, 4)
        self.assertTrue(is_over(s))
        self.assertFalse(begin_round(s))

    def test_classic_has_no_streak_bonus(self):
        s = create_session('classic')
        for _ in range(5):
            begin_round(s)
            resolve(s, 'smooth', 'smooth')
        self.assertEqual(s.score, 500)
        self.assertEqual(s.best_streak, 5)

    def test_late_scores_zero_and_resets_streak(self):
        s = create_session('rush')
        begin_round(s)
        resolve(s, 'burp', 'burp')
        begin_round(s)
        r = resolve(s, None, 'burp')
        self.assertFalse(r.ok)
        self.assertTrue(r.late)
        self.assertEqual(s.streak, 0)
        self.assertEqual(s.score, 100)

    def test_rush_streak_bonus_grows_and_caps(self):
        s = create_session('rush')
        pts = []
        for _ in range(12):
            begin_round(s)
            pts.append(resolve(s, 'fart', 'fart').points)
        self.assertEqual(pts[:4], [100, 125, 150, 175])
        self.assertEqual(max(pts), 300)

    def test_rush_ends_when_time_runs_out(self):
        s = create_session('rush')
        tick(s, 59.5)
        self.assertTrue(can_start_round(s))
        tick(s, 1)
        self.assertEqual(s.time_left, 0)
        self.assertTrue(is_over(s))

    def test_endless_loses_lives(self):
        s = create_session('endless')
        for _ in range(3):
            begin_round(s)
            self.assertTrue(resolve(s, 'burp', 'fart').life_lost)
        self.assertEqual(s.lives, 0)
        self.assertTrue(is_over(s))

    def test_speed_ramp_and_cap(self):
        e = create_session('endless', 'normal')
        e.round = 1
        self.assertEqual(speed_for(e), 1)
        e.round = 11
        self.assertAlmostEqual(speed_for(e), 1.5)
        e.round = 500
        self.assertEqual(speed_for(e), 2.2)
        c = create_session('classic', 'easy')
        c.round = 8
        self.assertEqual(speed_for(c), 0.8)

    def test_pick_menu_two_per_category(self):
        rng = random.Random(1)
        for _ in range(50):
            m = pick_menu(FOODS, rng)
            self.assertEqual(len(m), 6)
            self.assertEqual(len({f.id for f in m}), 6)
            for c in CATS:
                self.assertEqual(sum(f.cat == c for f in m), 2)

    def test_rank_thresholds(self):
        s = create_session('classic')
        s.round, s.correct = 8, 8
        self.assertEqual(rank_index(s), 2)
        s.correct = 5
        self.assertEqual(rank_index(s), 1)
        s.correct = 2
        self.assertEqual(rank_index(s), 0)

    def test_achievements_unlock_once(self):
        s = create_session('classic')
        ctx = {'event': 'predict', 'ok': True, 'cat': 'burp', 'session': s, 'tried': {}, 'total_foods': len(FOODS)}
        self.assertEqual(evaluate(ctx, {}), ['first_burp'])
        self.assertEqual(evaluate(ctx, {'first_burp': 1}), [])

    def test_foods_have_both_languages(self):
        for f in FOODS:
            self.assertIn(f.cat, CATS)
            for d in (f.name, f.fact):
                self.assertTrue(d['en'] and d['ja'], f.id)


class SimTest(unittest.TestCase):
    """Drive the simulation headlessly and check the event timeline."""

    def run_food(self, food_id, speed=1.0):
        from digestion_lab.foods import FOOD_BY_ID
        from digestion_lab.sim import Sim
        sim = Sim()
        sim.start_run(FOOD_BY_ID[food_id], speed)
        events, t = [], 0.0
        while sim.run or not events:
            for kind, _ in sim.update(1 / 120):
                events.append((kind, round(t, 2)))
            t += 1 / 120
            self.assertLess(t, 20)
        return events

    def test_burp_fires_2s_after_arrival(self):
        ev = dict(self.run_food('soda'))
        self.assertAlmostEqual(ev['fire'] - ev['arrive'], 2.0, delta=0.02)

    def test_fart_fires_4s_after_arrival_with_rumbles(self):
        events = self.run_food('beans')
        ev = dict((k, v) for k, v in events if k != 'rumble')
        self.assertAlmostEqual(ev['fire'] - ev['arrive'], 4.0, delta=0.02)
        self.assertGreaterEqual(sum(k == 'rumble' for k, _ in events), 3)

    def test_smooth_finishes(self):
        kinds = [k for k, _ in self.run_food('rice')]
        self.assertEqual(kinds, ['arrive', 'fire', 'finish'])


if __name__ == '__main__':
    unittest.main()


class SoundAndVersionTest(unittest.TestCase):
    def test_version(self):
        import digestion_lab
        self.assertEqual(digestion_lab.__version__, '0.1.0')

    def test_every_gassy_food_has_its_own_sound(self):
        from digestion_lab import audio
        for f in FOODS:
            name = audio.food_sound(f)
            if f.cat == 'smooth':
                self.assertIsNone(name)
            else:
                specs = audio.BURPS if f.cat == 'burp' else audio.FARTS
                self.assertIn(f.id, specs, f'{f.id} has no {f.cat} sound')

    def test_food_sounds_differ(self):
        from digestion_lab import audio
        lengths = {}
        for k, v in audio.BURPS.items():
            s = audio._burp(**v)
            self.assertGreater(max(abs(x) for x in s), 0.05, k)
            lengths[f'burp_{k}'] = len(s)
        for k, v in audio.FARTS.items():
            s = audio._fart(**v)
            self.assertGreater(max(abs(x) for x in s), 0.05, k)
            lengths[f'fart_{k}'] = len(s)
        self.assertEqual(len(set(lengths.values())), len(lengths), 'each food sound should have its own length')
