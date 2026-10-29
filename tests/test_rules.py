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
        import re
        import digestion_lab
        self.assertRegex(digestion_lab.__version__, r'^\d+\.\d+\.\d+$')

    def test_every_gassy_food_has_a_recording(self):
        import wave
        from digestion_lab import audio
        names = set(audio.recorded_names())
        for f in FOODS:
            name = audio.food_sound(f)
            if f.cat == 'smooth':
                self.assertIsNone(name)
                continue
            self.assertIn(name, names, f'{f.id} has no recording')
            with wave.open(str(audio.sounds_dir() / f'{name}.wav')) as w:
                secs = w.getnframes() / w.getframerate()
                self.assertTrue(0.3 < secs < 2.6, f'{name} is {secs:.2f}s')
                self.assertGreater(max(w.readframes(w.getnframes())), 0)

    def test_recordings_are_credited(self):
        from digestion_lab import audio
        credits = (audio.sounds_dir() / 'CREDITS.md').read_text(encoding='utf-8')
        for name in audio.recorded_names():
            self.assertIn(f'{name}.wav', credits)


class FoodDeckTest(unittest.TestCase):
    def deck(self, seed):
        from digestion_lab.rules import FoodDeck
        return FoodDeck(FOODS, random.Random(seed))

    def test_first_eight_never_repeat_and_eaten_food_stays_away(self):
        for seed in range(40):
            d, rng, eaten = self.deck(seed), random.Random(seed), []
            for _ in range(40):
                f = rng.choice(d.menu)
                self.assertNotIn(f.id, [e for e in eaten[-3:]], f'seed {seed}: {f.id} came back too soon')
                eaten.append(f.id)
                d.eat(f)
            self.assertEqual(len(set(eaten[:8])), 8, f'seed {seed}: {eaten[:8]}')

    def test_classic_game_never_repeats(self):
        for seed in range(40):
            d, seen, rng = self.deck(seed), set(), random.Random(seed + 99)
            for _ in range(8):
                f = rng.choice(d.menu)
                self.assertNotIn(f.id, seen)
                seen.add(f.id)
                d.eat(f)

    def test_menu_stays_full_unique_and_balanced(self):
        for seed in range(40):
            d, rng = self.deck(seed), random.Random(seed)
            for _ in range(60):   # long Rush/Endless game, several deck cycles
                self.assertEqual(len(d.menu), 6)
                self.assertEqual(len({f.id for f in d.menu}), 6)
                self.assertEqual({f.cat for f in d.menu}, set(CATS))
                last = rng.choice(d.menu)
                d.eat(last)
                self.assertNotIn(last.id, {f.id for f in d.menu}, 'eaten food came straight back')

    def test_levels(self):
        from digestion_lab.rules import level_for
        self.assertEqual([level_for(r) for r in range(0, 12)], [1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 5])


class MusicTest(unittest.TestCase):
    def test_title_and_every_level_have_a_loop(self):
        import wave
        from digestion_lab import music
        from digestion_lab.rules import MAX_LEVEL
        names = set(music.track_names())
        for name in ['title'] + [f'level{i}' for i in range(1, MAX_LEVEL + 1)]:
            self.assertIn(name, names)
            with wave.open(str(music.music_dir() / f'{name}.wav')) as w:
                self.assertGreater(w.getnframes() / w.getframerate(), 8)

    def test_levels_get_faster(self):
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location('mm', pathlib.Path('tools/make_music.py'))
        try:
            mm = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mm)
        except ImportError:
            self.skipTest('numpy not installed (only needed to compose the music)')
        bpms = [mm.TRACKS[f'level{i}']['bpm'] for i in range(1, 6)]
        self.assertEqual(bpms, sorted(bpms))
        self.assertEqual(len(set(bpms)), 5)
