"""Game controller: window, main loop, input, and game flow."""
import math
import os
import random
import sys
import time

from . import audio  # noqa: F401  (imported before pygame.init so the mixer can be pre-initialised)
import pygame

from . import __version__, fonts, storage, ui
from .achievements import ACH_BY_ID, evaluate
from .foods import FOODS
from .i18n import set_lang, get_lang, t, L
from .icon import make_icon
from .render import COL, StageRenderer
from .rules import (DIFFICULTY, begin_round, can_start_round, create_session, is_over, pick_menu, rank_index,
                    resolve, speed_for, tick)
from .sim import Sim

WINDOW_SIZE = (1280, 820)
MIN_SIZE = (960, 640)


def detect_lang():
    try:
        if sys.platform == 'win32':
            import ctypes
            return 'ja' if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x11 else 'en'
        for var in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
            v = os.environ.get(var)
            if v:
                return 'ja' if v.lower().startswith('ja') else 'en'
    except Exception:
        pass
    return 'en'


class App:
    def __init__(self):
        if sys.platform == 'win32':
            try:  # crisp rendering on high-DPI Windows displays
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
        self.save = storage.load()
        st = self.save['settings']
        if not st.get('lang'):
            st['lang'] = detect_lang()
        set_lang(st['lang'])

        audio.init()
        pygame.init()
        pygame.display.set_caption(f'Digestion Lab v{__version__}')
        pygame.display.set_icon(make_icon(64))
        self.windowed_size = WINDOW_SIZE
        self._apply_display_mode()
        audio.configure(volume=st['volume'], muted=st['muted'])

        self.clock = pygame.time.Clock()
        self.ui = ui.Widgets()
        self.renderer = StageRenderer()
        self.sim = Sim()
        self.mode = 'title'          # title | play | results
        self.screen = 'title'        # overlay screen name, or None during play
        self.paused = False
        self.session = None
        self.menu_foods = pick_menu(FOODS)
        self.pred = self._empty_pred()
        self.toasts = []
        self.scroll = 0
        self.scroll_max = 0
        self.slider_rect = None
        self.dragging_volume = False
        self.new_best = False
        self.rank = 0
        self.end_at = None
        self.last_second = None
        self.window_shake = 0.0
        self.clock_time = 0.0
        self.running = True

    # ---------- display ----------
    def _apply_display_mode(self):
        if self.save['settings'].get('fullscreen'):
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            try:
                pygame.Window.from_display_module().minimum_size = MIN_SIZE
            except Exception:
                pass

    def toggle_fullscreen(self):
        st = self.save['settings']
        if not st['fullscreen']:
            self.windowed_size = self.window.get_size()
        st['fullscreen'] = not st['fullscreen']
        self._apply_display_mode()
        storage.persist(self.save)

    # ---------- helpers used by the UI ----------
    @staticmethod
    def _empty_pred():
        return {'visible': False, 'progress': 1.0, 'picked': None, 'locked': False, 'result': None}

    def best_for_header(self):
        b = self.save['best']
        return b[self.session.mode] if self.session else max(b.values())

    def can_pick_food(self):
        return (self.mode == 'play' and not self.paused and not self.sim.run and self.session is not None
                and can_start_round(self.session))

    def status_text(self):
        if self.mode != 'play':
            return ''
        if self.sim.run:
            return f"{t('digesting')} · {L(self.sim.run.food.name)}"
        if self.session.mode == 'rush' and self.session.time_left <= 0:
            return t('timeUp')
        return t('ready')

    def unlock_achievements(self, **ctx):
        ids = evaluate({**ctx, 'session': self.session, 'tried': self.save['tried'], 'total_foods': len(FOODS)},
                       self.save['achievements'])
        for i in ids:
            self.save['achievements'][i] = int(time.time())
            self.toasts.append((t('unlocked'), L(ACH_BY_ID[i].name), self.clock_time))
        if ids:
            audio.play('unlock')
            storage.persist(self.save)

    # ---------- game flow ----------
    def start_game(self, mode):
        self.session = create_session(mode, self.save['settings']['difficulty'])
        self.sim.reset()
        self.menu_foods = pick_menu(FOODS)
        self.pred = self._empty_pred()
        self.screen = None
        self.mode = 'play'
        self.paused = False
        self.end_at = None
        self.last_second = None
        self.save['stats']['games'] += 1
        storage.persist(self.save)

    def pick_food(self, food):
        if not self.can_pick_food() or not begin_round(self.session):
            return
        self.sim.start_run(food, speed_for(self.session))
        self.save['tried'][food.id] = True
        self.save['stats']['rounds'] += 1
        storage.persist(self.save)
        self.pred = self._empty_pred()
        self.pred['visible'] = True
        audio.play('gulp')
        self.unlock_achievements(event='round')

    def predict(self, choice):
        run = self.sim.run
        if self.mode != 'play' or self.paused or not run or run.predicted or run.arrived:
            return
        self.settle(choice)

    def settle(self, choice):
        """choice=None: the food arrived before the player decided."""
        run = self.sim.run
        run.predicted = choice or 'late'
        res = resolve(self.session, choice, run.cat)
        res.streak = self.session.streak
        run.outcome = f'+{res.points}' if res.ok else '+0'
        self.pred.update(picked=choice, locked=True, result=res)
        if res.ok:
            audio.play('ok')
            self.save['stats']['correct'] += 1
            storage.persist(self.save)
        else:
            audio.play('bad')
        self.unlock_achievements(event='predict', ok=res.ok, cat=run.cat)

    def handle_sim_event(self, kind, run):
        if kind == 'arrive':
            self.pred['locked'] = True
            if not run.predicted:
                self.settle(None)
            if run.cat == 'burp':
                audio.play('fizz', fade_after=run.wait)
        elif kind == 'rumble':
            audio.play('rumble')
        elif kind == 'fire':
            if run.cat == 'burp':
                audio.play(audio.food_sound(run.food))
            elif run.cat == 'fart':
                audio.play(audio.food_sound(run.food))
                if self.save['settings']['shake']:
                    self.window_shake = 0.6
            else:
                audio.play('chime')
        elif kind == 'finish':
            self.pred['visible'] = False
            if is_over(self.session):
                self.end_at = self.clock_time + 0.5

    def end_game(self):
        if self.mode != 'play':
            return
        self.mode = 'results'
        self.paused = False
        self.end_at = None
        s = self.session
        self.new_best = s.score > self.save['best'][s.mode]
        if self.new_best:
            self.save['best'][s.mode] = s.score
        self.rank = rank_index(s)
        storage.persist(self.save)
        self.unlock_achievements(event='end')
        audio.play('gameover')
        self.pred = self._empty_pred()
        self.screen = 'results'

    def quit_to_title(self):
        self.mode = 'title'
        self.paused = False
        self.session = None
        self.sim.reset()
        self.pred = self._empty_pred()
        self.end_at = None
        self.screen = 'title'

    def set_paused(self, p):
        if self.mode != 'play' or self.paused == p:
            return
        self.paused = p
        self.screen = 'pause' if p else None

    # ---------- actions ----------
    def action(self, name, arg=None):
        if name not in ('volume_drag', 'food', 'predict'):
            audio.play('click')
        st = self.save['settings']
        if name == 'food':
            self.pick_food(self.menu_foods[arg])
        elif name == 'predict':
            self.predict(arg)
        elif name == 'start':
            self.start_game(arg)
        elif name == 'again':
            self.start_game(self.session.mode if self.session else 'classic')
        elif name == 'quit':
            self.quit_to_title()
        elif name == 'pause':
            self.set_paused(not self.paused)
        elif name == 'resume':
            self.set_paused(False)
        elif name == 'go':
            self.screen = arg
            self.scroll = 0
        elif name == 'difficulty':
            st['difficulty'] = arg
            storage.persist(self.save)
        elif name == 'lang':
            st['lang'] = 'ja' if get_lang() == 'en' else 'en'
            set_lang(st['lang'])
            storage.persist(self.save)
        elif name == 'sound':
            st['muted'] = not st['muted']
            audio.configure(muted=st['muted'])
            storage.persist(self.save)
        elif name == 'shake':
            st['shake'] = not st['shake']
            storage.persist(self.save)
        elif name == 'fullscreen':
            self.toggle_fullscreen()
        elif name == 'reset':
            self.screen = 'confirm'
        elif name == 'reset_yes':
            storage.reset_progress(self.save)
            self.screen = 'settings'
        elif name == 'volume_drag':
            self.dragging_volume = True
            self.set_volume_from_mouse(pygame.mouse.get_pos()[0])
        elif name == 'exit':
            self.running = False

    def set_volume_from_mouse(self, mx):
        if not self.slider_rect:
            return
        r = self.slider_rect
        st = self.save['settings']
        st['volume'] = round(max(0.0, min(1.0, (mx - r.x) / r.w)), 2)
        st['muted'] = False
        audio.configure(volume=st['volume'], muted=False)

    # ---------- input ----------
    def on_key(self, e):
        k = e.key
        if k == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if k in (pygame.K_ESCAPE, pygame.K_p):
            if self.mode == 'play':
                self.set_paused(not self.paused)
            elif self.screen in ('foodlog', 'achievements', 'settings'):
                self.screen = 'title'
            elif self.screen == 'confirm':
                self.screen = 'settings'
            return
        if k == pygame.K_m:
            self.action('sound')
            return
        if self.mode == 'results' and k in (pygame.K_RETURN, pygame.K_SPACE):
            self.action('again')
            return
        if self.mode != 'play' or self.paused:
            return
        if pygame.K_1 <= k <= pygame.K_9 and k - pygame.K_1 < len(self.menu_foods):
            self.pick_food(self.menu_foods[k - pygame.K_1])
        elif k == pygame.K_b:
            self.predict('burp')
        elif k == pygame.K_f:
            self.predict('fart')
        elif k == pygame.K_s:
            self.predict('smooth')

    def process_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.KEYDOWN:
                self.on_key(e)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                hit = self.ui.find(e.pos)
                if hit:
                    self.action(*hit)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                if self.dragging_volume:
                    self.dragging_volume = False
                    storage.persist(self.save)
            elif e.type == pygame.MOUSEMOTION:
                self.ui.mouse = e.pos
                if self.dragging_volume:
                    self.set_volume_from_mouse(e.pos[0])
            elif e.type == pygame.MOUSEWHEEL:
                if self.screen in ('foodlog', 'achievements'):
                    self.scroll = max(0, min(self.scroll_max, self.scroll - e.y * 48))
            elif e.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED):
                self.set_paused(True)
            elif e.type == pygame.WINDOWLEAVE:
                self.ui.mouse = (-1, -1)

    # ---------- per-frame ----------
    def update(self, dt):
        self.clock_time += dt
        self.toasts = [x for x in self.toasts if self.clock_time - x[2] < 3.1]
        self.window_shake = max(0.0, self.window_shake - dt)
        if self.mode == 'play' and self.paused:
            return
        for kind, run in self.sim.update(dt):
            self.handle_sim_event(kind, run)
        if self.mode != 'play':
            return
        run = self.sim.run
        if run and not run.arrived:
            self.pred['progress'] = max(0.0, 1 - run.t / run.D)
        s = self.session
        if s.mode == 'rush':
            tick(s, dt)
            sec = math.ceil(s.time_left)
            if sec != self.last_second:
                self.last_second = sec
                if 0 < sec <= 5:
                    audio.play('tick')
            if s.time_left <= 0 and not self.sim.run:
                self.end_game()
        if self.end_at is not None and self.clock_time >= self.end_at:
            self.end_game()

    def draw(self):
        win = self.window
        W, H = win.get_size()
        frame = win if self.window_shake <= 0 else pygame.Surface((W, H))
        frame.fill(COL['bg'])
        self.ui.reset()
        self.ui.modal = self.screen is not None
        stage = pygame.Rect(0, ui.HEADER_H, int(W * 0.7), H - ui.HEADER_H)
        menu = pygame.Rect(stage.right, ui.HEADER_H, W - stage.right, H - ui.HEADER_H)
        mystery = bool(self.session) and DIFFICULTY[self.session.difficulty]['mystery']
        self.renderer.draw(frame, stage, self.sim, mystery, self.save['settings']['shake'])
        ui.draw_status(self, frame, stage)
        ui.draw_predict(self, frame, stage)
        ui.draw_menu(self, frame, menu)
        # The header stays usable above overlays (language, sound, pause).
        self.ui.modal = False
        ui.draw_overlay(self, frame, W, H)
        ui.draw_header(self, frame, W)
        ui.draw_toasts(self, frame, W)
        if frame is not win:
            k = self.window_shake / 0.6
            win.fill(COL['bg'])
            win.blit(frame, (int(math.sin(self.clock_time * 70) * 10 * k), int(random.uniform(-3, 3) * k)))
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = min(0.05, self.clock.tick(60) / 1000)
            self.process_events()
            self.update(dt)
            self.draw()
        storage.persist(self.save)
        pygame.quit()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--version' in argv or '-V' in argv:
        print(f'Digestion Lab v{__version__}')
        return
    App().run()
