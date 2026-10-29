"""Achievement definitions and evaluation. Pure: plain data in, newly unlocked ids out."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Achievement:
    id: str
    check: Callable
    name: dict
    desc: dict


def _s(c):
    return c.get('session')


ACHIEVEMENTS = [
    Achievement('first_burp', lambda c: c.get('ok') and c.get('cat') == 'burp',
                {'en': 'Burp Detector', 'ja': 'ゲップ探知機'},
                {'en': 'Correctly predict a BURP.', 'ja': 'ゲップを正しく予想する。'}),
    Achievement('first_fart', lambda c: c.get('ok') and c.get('cat') == 'fart',
                {'en': 'Gas Forecaster', 'ja': 'ガス予報士'},
                {'en': 'Correctly predict a FART.', 'ja': 'おならを正しく予想する。'}),
    Achievement('first_smooth', lambda c: c.get('ok') and c.get('cat') == 'smooth',
                {'en': 'Smooth Operator', 'ja': 'スムーズオペレーター'},
                {'en': 'Correctly predict a SMOOTH RIDE.', 'ja': 'スムーズを正しく予想する。'}),
    Achievement('streak5', lambda c: _s(c) and _s(c).streak >= 5,
                {'en': 'On a Roll', 'ja': '絶好調'},
                {'en': '5 correct predictions in a row.', 'ja': '5回連続で正解する。'}),
    Achievement('streak10', lambda c: _s(c) and _s(c).streak >= 10,
                {'en': 'Iron Stomach', 'ja': '鉄の胃袋'},
                {'en': '10 correct predictions in a row.', 'ja': '10回連続で正解する。'}),
    Achievement('perfect', lambda c: c.get('event') == 'end' and _s(c).mode == 'classic' and _s(c).score >= 800,
                {'en': 'Perfect Digestion', 'ja': 'パーフェクト消化'},
                {'en': 'Score 800 in Classic.', 'ja': 'クラシックで800点を取る。'}),
    Achievement('foodie', lambda c: len(c.get('tried', {})) >= c.get('total_foods', 1 << 30),
                {'en': 'Food Critic', 'ja': 'グルメ評論家'},
                {'en': 'Taste every food in the game.', 'ja': 'すべての食べ物を味わう。'}),
    Achievement('rush', lambda c: _s(c) and _s(c).mode == 'rush' and _s(c).score >= 2000,
                {'en': 'Speed Eater', 'ja': '早食いチャンピオン'},
                {'en': 'Score 2000 or more in Rush.', 'ja': 'ラッシュで2000点以上を取る。'}),
    Achievement('survivor', lambda c: _s(c) and _s(c).mode == 'endless' and _s(c).round >= 20,
                {'en': 'Bottomless Pit', 'ja': '底なし胃袋'},
                {'en': 'Reach round 20 in Endless.', 'ja': 'エンドレスでラウンド20に到達する。'}),
    Achievement('mystery', lambda c: _s(c) and _s(c).difficulty == 'hard' and _s(c).streak >= 5,
                {'en': 'Gut Detective', 'ja': '腸の名探偵'},
                {'en': '5 correct in a row on Hard.', 'ja': 'ハードで5回連続正解する。'}),
]
ACH_BY_ID = {a.id: a for a in ACHIEVEMENTS}


def evaluate(ctx, unlocked):
    """ctx keys: event, ok, cat, session, tried, total_foods. unlocked: {id: timestamp}."""
    return [a.id for a in ACHIEVEMENTS if a.id not in unlocked and a.check(ctx)]
