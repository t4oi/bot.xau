import sys
import time
import json
import math
import logging
import hashlib
import statistics
import traceback
import datetime as dt
import urllib.request
import urllib.error
import urllib.parse
import sqlite3
import threading
import html as html_mod
from dataclasses import dataclass, field, asdict
from typing import (
    Any, Dict, List, Optional, Tuple, Callable, Union
)
from collections import deque, defaultdict
from pathlib import Path
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler

# =============================================================================
# VERSION & APP INFO
# =============================================================================

APP_NAME = "XAUUSD_Elite_Signal_Bot"
VERSION = "4.1.0"
AUTHOR = "Custom Elite Build"
BUILD_DATE = "2026-10"

# =============================================================================
# CONFIGURATION  (عدّل هنا مباشرة — بدون ملف .env)
# =============================================================================

# --- Telegram (ضع بياناتك هنا) ---
BOT_TOKEN: str = "8503353625:AAG9mQcYrYzbeZGfE6vVBcPeQsFBCsbyfHw"
CHAT_ID: str = "8952278702"

# --- Data Source ---
BIQUOTE_BASE_URL: str = "https://biquote.io/api"
SYMBOL: str = "XAUUSD"

# --- Timeframes ---
TIMEFRAMES: List[str] = ["1m", "5m", "15m", "30m", "1h", "4h"]
CANDLES_PER_TF: int = 1000
PRIMARY_TF: str = "15m"
HIGHER_TFS: List[str] = ["1h", "4h"]
LOWER_TFS: List[str] = ["1m", "5m"]

# --- Signal Quality & Limits ---
MAX_DAILY_SIGNALS: int = 20
MIN_GRADE: str = "B"                    # A أو B أو C
MIN_CONFIDENCE: int = 72
MIN_RR_RATIO: float = 1.6
COOLDOWN_SECONDS: int = 300
POLL_SECONDS: int = 45

# --- Filters ---
MAX_SPREAD: float = 1.80
MIN_ATR_PCT: float = 0.018
MAX_ATR_PCT: float = 0.55
REQUIRE_SESSION_FILTER: bool = True
PREFERRED_SESSIONS: List[str] = ["London", "NewYork", "LondonNewYork"]

# --- Risk / Targets ---
ATR_SL_MULTIPLIER: float = 1.35
ATR_TP1_MULTIPLIER: float = 1.10
ATR_TP2_MULTIPLIER: float = 1.90
ATR_TP3_MULTIPLIER: float = 2.80

# --- Logging & State ---
LOG_LEVEL: str = "INFO"
STATE_FILE: str = "bot_state.json"
LOG_FILE: str = "bot.log"
DB_FILE: str = "signals.db"
ENABLE_FILE_LOG: bool = True

# --- Advanced Scoring Weights ---
WEIGHT_TREND_ALIGNMENT = 22
WEIGHT_PATTERN_STRENGTH = 18
WEIGHT_MOMENTUM = 14
WEIGHT_STRUCTURE = 14
WEIGHT_MULTI_TF = 16
WEIGHT_SESSION = 8
WEIGHT_VOLATILITY = 8

# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging() -> logging.Logger:
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if ENABLE_FILE_LOG:
        try:
            fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception as e:
            print(f"Could not create log file: {e}")

    return logger


logger = setup_logging()

# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


class Grade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    REJECT = "REJECT"


class Session(str, Enum):
    ASIA = "Asia"
    LONDON = "London"
    NEWYORK = "NewYork"
    LONDON_NY = "LondonNewYork"
    LATE = "Late"
    WEEKEND = "Weekend"


class Trend(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    STRONG_BULL = "strong_bull"
    STRONG_BEAR = "strong_bear"


class PatternType(str, Enum):
    REVERSAL = "reversal"
    CONTINUATION = "continuation"
    INDECISION = "indecision"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Candle:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    tick_volume: float = 0.0
    is_open: bool = False

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        if self.range == 0:
            return True
        return self.body / self.range < 0.08

    def body_pct(self) -> float:
        if self.range == 0:
            return 0.0
        return self.body / self.range


@dataclass
class Tick:
    symbol: str
    bid: float
    ask: float
    mid: float
    spread: float
    high: float = 0.0
    low: float = 0.0
    day_diff_pct: float = 0.0
    timestamp: str = ""
    market_state: str = "open"


@dataclass
class PatternHit:
    name: str
    direction: Direction
    strength: float          # 0.0 – 1.0
    pattern_type: PatternType
    bars_used: int = 1
    description: str = ""


@dataclass
class IndicatorSnapshot:
    rsi: float = 50.0
    rsi_prev: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    atr: float = 0.0
    atr_pct: float = 0.0
    ema9: float = 0.0
    ema21: float = 0.0
    ema50: float = 0.0
    ema200: float = 0.0
    sma20: float = 0.0
    sma50: float = 0.0
    stoch_k: float = 50.0
    stoch_d: float = 50.0
    adx: float = 20.0
    plus_di: float = 0.0
    minus_di: float = 0.0
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_width: float = 0.0
    momentum: float = 0.0
    roc: float = 0.0


@dataclass
class StructureSnapshot:
    trend: Trend = Trend.NEUTRAL
    last_swing_high: float = 0.0
    last_swing_low: float = 0.0
    higher_highs: bool = False
    higher_lows: bool = False
    lower_highs: bool = False
    lower_lows: bool = False
    bos_bullish: bool = False
    bos_bearish: bool = False
    choch_bullish: bool = False
    choch_bearish: bool = False
    support: float = 0.0
    resistance: float = 0.0
    structure_score: float = 0.0


@dataclass
class TFAnalysis:
    timeframe: str
    candles: List[Candle]
    indicators: IndicatorSnapshot
    structure: StructureSnapshot
    patterns: List[PatternHit]
    trend: Trend
    momentum_score: float = 0.0
    pattern_score: float = 0.0
    overall_bias: Direction = Direction.NONE
    confidence: float = 0.0


@dataclass
class Signal:
    valid: bool
    direction: Direction
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    confidence: int
    grade: Grade
    reason: str
    strategy: str
    patterns: List[str] = field(default_factory=list)
    timeframe_bias: Dict[str, str] = field(default_factory=dict)
    rr1: float = 0.0
    rr2: float = 0.0
    rr3: float = 0.0
    atr: float = 0.0
    session: str = ""
    timestamp: str = ""
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    multi_tf_score: float = 0.0


@dataclass
class BotState:
    last_signal_key: str = ""
    last_signal_time: float = 0.0
    last_signal_direction: str = ""
    signals_today: int = 0
    day_key: str = ""
    total_signals_sent: int = 0
    last_error: str = ""
    last_analysis_time: float = 0.0
    grade_counts: Dict[str, int] = field(default_factory=lambda: {"A": 0, "B": 0, "C": 0})
    consecutive_rejects: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    start_time: float = 0.0
    last_price: float = 0.0
    last_update_id: int = 0


# Global state
state = BotState()
_last_tick: Optional[Tick] = None
_last_analyses: Dict[str, Any] = {}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_iso() -> str:
    return now_utc().isoformat()


def utc_day_key() -> str:
    return now_utc().strftime("%Y-%m-%d")


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return default


def round_price(x: float, digits: int = 2) -> float:
    return round(float(x), digits)


def pct(a: float, b: float) -> float:
    if a == 0:
        return 0.0
    return ((b - a) / a) * 100.0


def midpoint(a: float, b: float) -> float:
    return (a + b) / 2.0


def signed_body(c: Candle) -> float:
    return c.close - c.open


def candle_color(c: Candle) -> str:
    if c.is_bullish:
        return "green"
    if c.is_bearish:
        return "red"
    return "doji"


def hash_signal(direction: str, entry: float, sl: float, tp1: float) -> str:
    raw = f"{direction}:{entry:.2f}:{sl:.2f}:{tp1:.2f}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def to_json(obj: Any, indent: int = 2) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=indent, default=str)


def load_state() -> BotState:
    path = Path(STATE_FILE)
    if not path.exists():
        return BotState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        s = BotState()
        for k, v in data.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s
    except Exception as e:
        logger.warning(f"Could not load state: {e}")
        return BotState()


def save_state() -> None:
    try:
        data = asdict(state)
        # keep history short
        data["history"] = data.get("history", [])[-80:]
        Path(STATE_FILE).write_text(to_json(data), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def reset_daily_if_needed() -> None:
    today = utc_day_key()
    if state.day_key != today:
        logger.info(f"New day detected ({today}). Resetting daily counters.")
        state.day_key = today
        state.signals_today = 0
        state.consecutive_rejects = 0
        state.grade_counts = {"A": 0, "B": 0, "C": 0}
        save_state()


def uptime_str() -> str:
    if not state.start_time:
        return "0s"
    sec = int(time.time() - state.start_time)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# =============================================================================
# SQLITE DATABASE — signal history & paper tracking
# =============================================================================

def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def db_init() -> None:
    conn = db_connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry REAL NOT NULL,
            sl REAL NOT NULL,
            tp1 REAL NOT NULL,
            tp2 REAL NOT NULL,
            tp3 REAL NOT NULL,
            confidence INTEGER,
            grade TEXT,
            reason TEXT,
            strategy TEXT,
            session TEXT,
            status TEXT DEFAULT 'Open',
            close_price REAL,
            closed_at TEXT,
            result TEXT
        )
    """)
    conn.commit()
    conn.close()


def db_insert_signal(sig: Signal) -> int:
    conn = db_connect()
    cur = conn.execute(
        """INSERT INTO signals
           (created_at, direction, entry, sl, tp1, tp2, tp3, confidence, grade, reason, strategy, session, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open')""",
        (
            sig.timestamp or utc_iso(),
            sig.direction.value if hasattr(sig.direction, "value") else str(sig.direction),
            sig.entry, sig.sl, sig.tp1, sig.tp2, sig.tp3,
            sig.confidence,
            sig.grade.value if hasattr(sig.grade, "value") else str(sig.grade),
            sig.reason, sig.strategy, sig.session,
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return int(row_id or 0)


def db_open_trades() -> List[Dict[str, Any]]:
    conn = db_connect()
    rows = conn.execute("SELECT * FROM signals WHERE status='Open' ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_history(limit: int = 30) -> List[Dict[str, Any]]:
    conn = db_connect()
    rows = conn.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_stats() -> Dict[str, Any]:
    conn = db_connect()
    total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    opens = conn.execute("SELECT COUNT(*) FROM signals WHERE status='Open'").fetchone()[0]
    wins = conn.execute("SELECT COUNT(*) FROM signals WHERE result='Win'").fetchone()[0]
    losses = conn.execute("SELECT COUNT(*) FROM signals WHERE result='Loss'").fetchone()[0]
    conn.close()
    return {"total": total, "open": opens, "wins": wins, "losses": losses}


def db_export_csv() -> str:
    rows = db_history(500)
    lines = ["id,created_at,direction,entry,sl,tp1,tp2,tp3,confidence,grade,status,result"]
    for r in rows:
        lines.append(
            f"{r['id']},{r['created_at']},{r['direction']},{r['entry']},{r['sl']},"
            f"{r['tp1']},{r['tp2']},{r['tp3']},{r['confidence']},{r['grade']},{r['status']},{r.get('result') or ''}"
        )
    return "\n".join(lines)


def db_auto_close_by_price(price: float) -> None:
    opens = db_open_trades()
    if not opens:
        return
    conn = db_connect()
    for t in opens:
        direction = t["direction"]
        sl = t["sl"]
        tp1 = t["tp1"]
        result = None
        if direction == "BUY":
            if price <= sl:
                result = "Loss"
            elif price >= tp1:
                result = "Win"
        elif direction == "SELL":
            if price >= sl:
                result = "Loss"
            elif price <= tp1:
                result = "Win"
        if result:
            conn.execute(
                "UPDATE signals SET status='Closed', close_price=?, closed_at=?, result=? WHERE id=?",
                (price, utc_iso(), result, t["id"]),
            )
    conn.commit()
    conn.close()


# =============================================================================
# SESSION DETECTION
# =============================================================================

def get_session(now: Optional[dt.datetime] = None) -> Session:
    if now is None:
        now = now_utc()
    # Gold trades almost 24/5. Sessions in UTC.
    weekday = now.weekday()  # 0=Mon … 6=Sun
    if weekday >= 5:  # Sat/Sun
        # Sunday evening open is late Asia/early London
        if weekday == 6 and now.hour >= 21:
            return Session.ASIA
        return Session.WEEKEND

    h = now.hour
    # Approximate:
    # Asia: 00:00 – 07:00 UTC
    # London: 07:00 – 13:00
    # London+NY overlap: 13:00 – 16:00
    # New York: 13:00 – 21:00
    # Late: 21:00 – 00:00
    if 0 <= h < 7:
        return Session.ASIA
    if 7 <= h < 13:
        return Session.LONDON
    if 13 <= h < 16:
        return Session.LONDON_NY
    if 16 <= h < 21:
        return Session.NEWYORK
    return Session.LATE


def session_score(session: Session) -> float:
    """Higher score for preferred gold sessions."""
    mapping = {
        Session.LONDON_NY: 1.0,
        Session.LONDON: 0.85,
        Session.NEWYORK: 0.80,
        Session.ASIA: 0.45,
        Session.LATE: 0.35,
        Session.WEEKEND: 0.10,
    }
    return mapping.get(session, 0.3)


# =============================================================================
# BIQUOTE DATA CLIENT
# =============================================================================

class BiQuoteClient:
    """HTTP client using only Python standard library (urllib)."""

    def __init__(self, base_url: str = BIQUOTE_BASE_URL, timeout: int = 25):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_ttl = 8.0

    def _get(self, path: str, params: Optional[Dict] = None, use_cache: bool = False) -> Optional[Dict]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        cache_key = url
        if use_cache and cache_key in self._cache:
            ts, data = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return data

        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": f"{APP_NAME}/{VERSION}",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    if use_cache:
                        self._cache[cache_key] = (time.time(), data)
                    return data
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = int(e.headers.get("Retry-After", 5))
                    logger.warning(f"Rate limited. Sleeping {wait}s")
                    time.sleep(wait)
                    continue
                logger.error(f"HTTP {e.code} on {url}")
            except urllib.error.URLError as e:
                logger.warning(f"URL error on {url} (attempt {attempt+1}): {e}")
            except Exception as e:
                logger.error(f"Request error {url}: {e}")
            time.sleep(1.2 * (attempt + 1))
        return None

    def get_tick(self, symbol: str = SYMBOL) -> Optional[Tick]:
        data = self._get(f"{symbol}", use_cache=True)
        if not data:
            return None
        bid = safe_float(data.get("bid"))
        ask = safe_float(data.get("ask"))
        mid = safe_float(data.get("mid"))
        if mid <= 0 and bid > 0 and ask > 0:
            mid = midpoint(bid, ask)
        spread = safe_float(data.get("spread"))
        if spread <= 0 and bid > 0 and ask > 0:
            spread = ask - bid
        return Tick(
            symbol=symbol,
            bid=bid,
            ask=ask,
            mid=mid,
            spread=round(spread, 3),
            high=safe_float(data.get("high")),
            low=safe_float(data.get("low")),
            day_diff_pct=safe_float(data.get("dayDiffPercent")),
            timestamp=str(data.get("timestamp", "")),
            market_state=str(data.get("marketState", "open")),
        )

    def get_ohlc(self, symbol: str, interval: str, limit: int = 1000) -> List[Candle]:
        """Returns candles oldest → newest (closed bars preferred)."""
        params = {"interval": interval, "limit": min(limit, 1000)}
        data = self._get(f"{symbol}/ohlc", params=params)
        if not data or "bars" not in data:
            logger.error(f"No OHLC data for {symbol} {interval}")
            return []

        bars = data["bars"]
        candles: List[Candle] = []
        for b in bars:
            if b.get("isOpen"):
                continue
            c = Candle(
                time=str(b.get("openTime", "")),
                open=safe_float(b.get("open")),
                high=safe_float(b.get("high")),
                low=safe_float(b.get("low")),
                close=safe_float(b.get("close")),
                volume=safe_float(b.get("volume")),
                tick_volume=safe_float(b.get("tickVolume")),
                is_open=bool(b.get("isOpen", False)),
            )
            if c.high >= c.low and c.open > 0 and c.close > 0:
                candles.append(c)

        candles.reverse()
        return candles


client = BiQuoteClient()

# =============================================================================
# INDICATOR ENGINE
# =============================================================================

def sma(values: List[float], period: int) -> float:
    if len(values) < period or period <= 0:
        return 0.0
    return sum(values[-period:]) / period


def ema_series(values: List[float], period: int) -> List[float]:
    if not values or period <= 0:
        return []
    k = 2.0 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def ema(values: List[float], period: int) -> float:
    series = ema_series(values, period)
    return series[-1] if series else 0.0


def calculate_rsi(closes: List[float], period: int = 14) -> Tuple[float, float]:
    if len(closes) < period + 2:
        return 50.0, 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    def _rsi(g: float, l: float) -> float:
        if l == 0:
            return 100.0
        rs = g / l
        return 100.0 - (100.0 / (1.0 + rs))

    rsi_now = _rsi(avg_gain, avg_loss)

    # previous RSI approximation
    if len(gains) > period:
        prev_g = (avg_gain * period - gains[-1]) / (period - 1) if period > 1 else avg_gain
        prev_l = (avg_loss * period - losses[-1]) / (period - 1) if period > 1 else avg_loss
        rsi_prev = _rsi(prev_g, prev_l)
    else:
        rsi_prev = rsi_now
    return rsi_now, rsi_prev


def calculate_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
    if len(closes) < slow + signal:
        return 0.0, 0.0, 0.0
    ema_fast = ema_series(closes, fast)
    ema_slow = ema_series(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast[-len(ema_slow):], ema_slow)]
    if len(macd_line) < signal:
        return macd_line[-1] if macd_line else 0.0, 0.0, 0.0
    signal_line = ema_series(macd_line, signal)
    hist = macd_line[-1] - signal_line[-1]
    return macd_line[-1], signal_line[-1], hist


def calculate_atr(candles: List[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        c, p = candles[i], candles[i - 1]
        tr = max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close))
        trs.append(tr)
    if len(trs) < period:
        return statistics.mean(trs) if trs else 0.0
    # Wilder smoothing
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def calculate_stochastic(candles: List[Candle], k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
    if len(candles) < k_period:
        return 50.0, 50.0
    recent = candles[-k_period:]
    highest = max(c.high for c in recent)
    lowest = min(c.low for c in recent)
    close = candles[-1].close
    if highest == lowest:
        k = 50.0
    else:
        k = ((close - lowest) / (highest - lowest)) * 100.0
    # simple %D
    k_values = []
    for i in range(max(0, len(candles) - k_period - d_period + 1), len(candles) - k_period + 1):
        window = candles[i:i + k_period]
        if not window:
            continue
        h = max(c.high for c in window)
        l = min(c.low for c in window)
        cl = window[-1].close
        if h == l:
            k_values.append(50.0)
        else:
            k_values.append(((cl - l) / (h - l)) * 100.0)
    d = sum(k_values[-d_period:]) / len(k_values[-d_period:]) if k_values else k
    return k, d


def calculate_adx(candles: List[Candle], period: int = 14) -> Tuple[float, float, float]:
    if len(candles) < period * 2:
        return 20.0, 0.0, 0.0
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(candles)):
        up = candles[i].high - candles[i - 1].high
        down = candles[i - 1].low - candles[i].low
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr = max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - candles[i - 1].close),
            abs(candles[i].low - candles[i - 1].close),
        )
        trs.append(tr)

    def wilder_smooth(data: List[float], p: int) -> List[float]:
        if len(data) < p:
            return []
        res = [sum(data[:p])]
        for v in data[p:]:
            res.append(res[-1] - (res[-1] / p) + v)
        return res

    atr_s = wilder_smooth(trs, period)
    plus_s = wilder_smooth(plus_dm, period)
    minus_s = wilder_smooth(minus_dm, period)
    if not atr_s or not plus_s or not minus_s:
        return 20.0, 0.0, 0.0

    dx_list = []
    for a, p, m in zip(atr_s, plus_s, minus_s):
        if a == 0:
            continue
        plus_di = 100 * (p / a)
        minus_di = 100 * (m / a)
        di_sum = plus_di + minus_di
        if di_sum == 0:
            continue
        dx = 100 * abs(plus_di - minus_di) / di_sum
        dx_list.append(dx)

    if len(dx_list) < period:
        adx = statistics.mean(dx_list) if dx_list else 20.0
    else:
        adx = sum(dx_list[:period]) / period
        for d in dx_list[period:]:
            adx = (adx * (period - 1) + d) / period

    last_atr = atr_s[-1] if atr_s else 1.0
    plus_di = 100 * (plus_s[-1] / last_atr) if last_atr else 0.0
    minus_di = 100 * (minus_s[-1] / last_atr) if last_atr else 0.0
    return adx, plus_di, minus_di


def calculate_bollinger(closes: List[float], period: int = 20, std_mult: float = 2.0) -> Tuple[float, float, float, float]:
    if len(closes) < period:
        return 0.0, 0.0, 0.0, 0.0
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = math.sqrt(variance)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    width = (upper - lower) / mid * 100 if mid else 0.0
    return upper, mid, lower, width


def calculate_momentum(closes: List[float], period: int = 10) -> float:
    if len(closes) < period + 1:
        return 0.0
    return closes[-1] - closes[-period - 1]


def calculate_roc(closes: List[float], period: int = 10) -> float:
    if len(closes) < period + 1 or closes[-period - 1] == 0:
        return 0.0
    return ((closes[-1] - closes[-period - 1]) / closes[-period - 1]) * 100.0


def build_indicators(candles: List[Candle]) -> IndicatorSnapshot:
    if len(candles) < 50:
        return IndicatorSnapshot()

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]

    rsi, rsi_prev = calculate_rsi(closes, 14)
    macd, macd_sig, macd_hist = calculate_macd(closes)
    atr = calculate_atr(candles, 14)
    price = closes[-1]
    atr_pct = (atr / price * 100) if price else 0.0

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200) if len(closes) >= 200 else ema(closes, min(100, len(closes)))
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)

    stoch_k, stoch_d = calculate_stochastic(candles)
    adx, plus_di, minus_di = calculate_adx(candles)
    bb_u, bb_m, bb_l, bb_w = calculate_bollinger(closes)
    mom = calculate_momentum(closes, 10)
    roc = calculate_roc(closes, 10)

    return IndicatorSnapshot(
        rsi=round(rsi, 2),
        rsi_prev=round(rsi_prev, 2),
        macd=round(macd, 5),
        macd_signal=round(macd_sig, 5),
        macd_hist=round(macd_hist, 5),
        atr=round(atr, 3),
        atr_pct=round(atr_pct, 4),
        ema9=round(ema9, 3),
        ema21=round(ema21, 3),
        ema50=round(ema50, 3),
        ema200=round(ema200, 3),
        sma20=round(sma20, 3),
        sma50=round(sma50, 3),
        stoch_k=round(stoch_k, 2),
        stoch_d=round(stoch_d, 2),
        adx=round(adx, 2),
        plus_di=round(plus_di, 2),
        minus_di=round(minus_di, 2),
        bb_upper=round(bb_u, 3),
        bb_middle=round(bb_m, 3),
        bb_lower=round(bb_l, 3),
        bb_width=round(bb_w, 3),
        momentum=round(mom, 3),
        roc=round(roc, 3),
    )


# =============================================================================
# CANDLESTICK PATTERN LIBRARY
# =============================================================================

def _body_ratio(c: Candle) -> float:
    return c.body_pct()


def _is_long_body(c: Candle, min_ratio: float = 0.55) -> bool:
    return _body_ratio(c) >= min_ratio


def _is_small_body(c: Candle, max_ratio: float = 0.25) -> bool:
    return _body_ratio(c) <= max_ratio


def detect_bullish_engulfing(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bearish and b.is_bullish and b.open <= a.close and b.close >= a.open:
        strength = min(1.0, (b.body / max(a.body, 0.0001)) * 0.55 + 0.35)
        if b.body > a.body * 1.1:
            strength = min(1.0, strength + 0.15)
        return PatternHit("Bullish Engulfing", Direction.BUY, strength, PatternType.REVERSAL, 2,
                          "شمعة صاعدة تبتلع الشمعة الهابطة السابقة")
    return None


def detect_bearish_engulfing(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bullish and b.is_bearish and b.open >= a.close and b.close <= a.open:
        strength = min(1.0, (b.body / max(a.body, 0.0001)) * 0.55 + 0.35)
        if b.body > a.body * 1.1:
            strength = min(1.0, strength + 0.15)
        return PatternHit("Bearish Engulfing", Direction.SELL, strength, PatternType.REVERSAL, 2,
                          "شمعة هابطة تبتلع الشمعة الصاعدة السابقة")
    return None


def detect_hammer(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.range == 0:
        return None
    lower = c.lower_wick
    upper = c.upper_wick
    body = c.body
    if lower >= body * 2.0 and upper <= body * 0.4 and _body_ratio(c) < 0.35:
        strength = clamp(lower / (c.range + 0.0001), 0.45, 0.95)
        return PatternHit("Hammer", Direction.BUY, strength, PatternType.REVERSAL, 1,
                          "مطرقة — ظل سفلي طويل يدل على رفض الهبوط")
    return None


def detect_inverted_hammer(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.range == 0:
        return None
    upper = c.upper_wick
    lower = c.lower_wick
    body = c.body
    if upper >= body * 2.0 and lower <= body * 0.35 and _body_ratio(c) < 0.35:
        strength = clamp(upper / (c.range + 0.0001), 0.40, 0.85)
        return PatternHit("Inverted Hammer", Direction.BUY, strength, PatternType.REVERSAL, 1,
                          "مطرقة مقلوبة — احتمال انعكاس صعودي")
    return None


def detect_shooting_star(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.range == 0:
        return None
    upper = c.upper_wick
    lower = c.lower_wick
    body = c.body
    if upper >= body * 2.0 and lower <= body * 0.35 and _body_ratio(c) < 0.35 and c.is_bearish:
        strength = clamp(upper / (c.range + 0.0001), 0.45, 0.95)
        return PatternHit("Shooting Star", Direction.SELL, strength, PatternType.REVERSAL, 1,
                          "نجم ساقط — رفض الصعود")
    return None


def detect_hanging_man(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.range == 0:
        return None
    lower = c.lower_wick
    upper = c.upper_wick
    body = c.body
    if lower >= body * 2.0 and upper <= body * 0.4 and _body_ratio(c) < 0.35 and c.is_bearish:
        strength = clamp(lower / (c.range + 0.0001), 0.40, 0.85)
        return PatternHit("Hanging Man", Direction.SELL, strength, PatternType.REVERSAL, 1,
                          "رجل مشنوق — تحذير من انعكاس هبوطي")
    return None


def detect_doji(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.is_doji:
        strength = 0.55 if c.range > 0 else 0.3
        return PatternHit("Doji", Direction.NONE, strength, PatternType.INDECISION, 1,
                          "دوجي — تردد السوق")
    return None


def detect_dragonfly_doji(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.range == 0:
        return None
    if c.body / c.range < 0.08 and c.lower_wick >= c.range * 0.65 and c.upper_wick <= c.range * 0.12:
        return PatternHit("Dragonfly Doji", Direction.BUY, 0.72, PatternType.REVERSAL, 1,
                          "دوجي اليعسوب — رفض قوي للهبوط")
    return None


def detect_gravestone_doji(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.range == 0:
        return None
    if c.body / c.range < 0.08 and c.upper_wick >= c.range * 0.65 and c.lower_wick <= c.range * 0.12:
        return PatternHit("Gravestone Doji", Direction.SELL, 0.72, PatternType.REVERSAL, 1,
                          "دوجي شاهد القبر — رفض قوي للصعود")
    return None


def detect_morning_star(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bearish and _is_long_body(a) and
            _is_small_body(b) and
            c.is_bullish and c.close > midpoint(a.open, a.close)):
        strength = 0.78
        if c.close > a.open:
            strength = 0.88
        return PatternHit("Morning Star", Direction.BUY, strength, PatternType.REVERSAL, 3,
                          "نجمة الصباح — انعكاس صعودي قوي")
    return None


def detect_evening_star(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bullish and _is_long_body(a) and
            _is_small_body(b) and
            c.is_bearish and c.close < midpoint(a.open, a.close)):
        strength = 0.78
        if c.close < a.open:
            strength = 0.88
        return PatternHit("Evening Star", Direction.SELL, strength, PatternType.REVERSAL, 3,
                          "نجمة المساء — انعكاس هبوطي قوي")
    return None


def detect_three_white_soldiers(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bullish and b.is_bullish and c.is_bullish and
            b.close > a.close and c.close > b.close and
            b.open > a.open and b.open < a.close and
            c.open > b.open and c.open < b.close):
        return PatternHit("Three White Soldiers", Direction.BUY, 0.82, PatternType.CONTINUATION, 3,
                          "ثلاثة جنود بيض — استمرار صعودي قوي")
    return None


def detect_three_black_crows(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bearish and b.is_bearish and c.is_bearish and
            b.close < a.close and c.close < b.close and
            b.open < a.open and b.open > a.close and
            c.open < b.open and c.open > b.close):
        return PatternHit("Three Black Crows", Direction.SELL, 0.82, PatternType.CONTINUATION, 3,
                          "ثلاثة غربان سود — استمرار هبوطي قوي")
    return None


def detect_bullish_harami(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bearish and b.is_bullish and b.open > a.close and b.close < a.open and b.body < a.body * 0.6:
        return PatternHit("Bullish Harami", Direction.BUY, 0.68, PatternType.REVERSAL, 2,
                          "هارامي صاعد")
    return None


def detect_bearish_harami(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bullish and b.is_bearish and b.open < a.close and b.close > a.open and b.body < a.body * 0.6:
        return PatternHit("Bearish Harami", Direction.SELL, 0.68, PatternType.REVERSAL, 2,
                          "هارامي هابط")
    return None


def detect_piercing_line(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bearish and b.is_bullish and b.open < a.low and b.close > midpoint(a.open, a.close) and b.close < a.open:
        return PatternHit("Piercing Line", Direction.BUY, 0.74, PatternType.REVERSAL, 2,
                          "خط الثقب — انعكاس صعودي")
    return None


def detect_dark_cloud_cover(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bullish and b.is_bearish and b.open > a.high and b.close < midpoint(a.open, a.close) and b.close > a.open:
        return PatternHit("Dark Cloud Cover", Direction.SELL, 0.74, PatternType.REVERSAL, 2,
                          "غطاء السحابة الداكنة — انعكاس هبوطي")
    return None


def detect_tweezer_bottom(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    tol = max(a.range * 0.08, 0.15)
    if abs(a.low - b.low) <= tol and a.is_bearish and b.is_bullish:
        return PatternHit("Tweezer Bottom", Direction.BUY, 0.70, PatternType.REVERSAL, 2,
                          "قاع الملقط")
    return None


def detect_tweezer_top(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    tol = max(a.range * 0.08, 0.15)
    if abs(a.high - b.high) <= tol and a.is_bullish and b.is_bearish:
        return PatternHit("Tweezer Top", Direction.SELL, 0.70, PatternType.REVERSAL, 2,
                          "قمة الملقط")
    return None


def detect_marubozu_bull(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.is_bullish and c.upper_wick <= c.body * 0.08 and c.lower_wick <= c.body * 0.08 and _body_ratio(c) > 0.75:
        return PatternHit("Bullish Marubozu", Direction.BUY, 0.80, PatternType.CONTINUATION, 1,
                          "ماروبوزو صاعد — سيطرة المشترين")
    return None


def detect_marubozu_bear(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.is_bearish and c.upper_wick <= c.body * 0.08 and c.lower_wick <= c.body * 0.08 and _body_ratio(c) > 0.75:
        return PatternHit("Bearish Marubozu", Direction.SELL, 0.80, PatternType.CONTINUATION, 1,
                          "ماروبوزو هابط — سيطرة البائعين")
    return None


def detect_spinning_top(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if 0.15 <= _body_ratio(c) <= 0.35 and c.upper_wick > c.body * 0.4 and c.lower_wick > c.body * 0.4:
        return PatternHit("Spinning Top", Direction.NONE, 0.45, PatternType.INDECISION, 1,
                          "قمة دوارة — تردد")
    return None


PATTERN_DETECTORS: List[Callable[[List[Candle]], Optional[PatternHit]]] = [
    detect_bullish_engulfing,
    detect_bearish_engulfing,
    detect_hammer,
    detect_inverted_hammer,
    detect_shooting_star,
    detect_hanging_man,
    detect_dragonfly_doji,
    detect_gravestone_doji,
    detect_morning_star,
    detect_evening_star,
    detect_three_white_soldiers,
    detect_three_black_crows,
    detect_bullish_harami,
    detect_bearish_harami,
    detect_piercing_line,
    detect_dark_cloud_cover,
    detect_tweezer_bottom,
    detect_tweezer_top,
    detect_marubozu_bull,
    detect_marubozu_bear,
    detect_doji,
    detect_spinning_top,
]


def scan_patterns(candles: List[Candle]) -> List[PatternHit]:
    hits: List[PatternHit] = []
    for detector in PATTERN_DETECTORS:
        try:
            hit = detector(candles)
            if hit:
                hits.append(hit)
        except Exception:
            continue
    # sort by strength descending
    hits.sort(key=lambda p: p.strength, reverse=True)
    return hits


# =============================================================================
# MARKET STRUCTURE
# =============================================================================

def find_swing_points(candles: List[Candle], left: int = 3, right: int = 3) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Returns (swing_highs, swing_lows) as list of (index, price)."""
    highs, lows = [], []
    n = len(candles)
    for i in range(left, n - right):
        window_high = [candles[j].high for j in range(i - left, i + right + 1)]
        window_low = [candles[j].low for j in range(i - left, i + right + 1)]
        if candles[i].high == max(window_high):
            highs.append((i, candles[i].high))
        if candles[i].low == min(window_low):
            lows.append((i, candles[i].low))
    return highs, lows


def analyze_structure(candles: List[Candle]) -> StructureSnapshot:
    snap = StructureSnapshot()
    if len(candles) < 40:
        return snap

    swing_highs, swing_lows = find_swing_points(candles, 4, 4)
    closes = [c.close for c in candles]
    price = closes[-1]

    if len(swing_highs) >= 2:
        snap.last_swing_high = swing_highs[-1][1]
        if swing_highs[-1][1] > swing_highs[-2][1]:
            snap.higher_highs = True
        else:
            snap.lower_highs = True

    if len(swing_lows) >= 2:
        snap.last_swing_low = swing_lows[-1][1]
        if swing_lows[-1][1] > swing_lows[-2][1]:
            snap.higher_lows = True
        else:
            snap.lower_lows = True

    # BOS / CHOCH simplified
    if snap.higher_highs and snap.higher_lows:
        snap.trend = Trend.BULLISH
        snap.structure_score = 0.75
        if len(swing_highs) >= 2 and price > swing_highs[-2][1]:
            snap.bos_bullish = True
            snap.structure_score = 0.90
    elif snap.lower_highs and snap.lower_lows:
        snap.trend = Trend.BEARISH
        snap.structure_score = 0.75
        if len(swing_lows) >= 2 and price < swing_lows[-2][1]:
            snap.bos_bearish = True
            snap.structure_score = 0.90
    else:
        snap.trend = Trend.NEUTRAL
        snap.structure_score = 0.35

    # Support / Resistance from recent swings
    recent_highs = [h for _, h in swing_highs[-6:]] or [max(c.high for c in candles[-30:])]
    recent_lows = [l for _, l in swing_lows[-6:]] or [min(c.low for c in candles[-30:])]
    snap.resistance = max(recent_highs)
    snap.support = min(recent_lows)

    # CHOCH detection (change of character)
    if snap.trend == Trend.BEARISH and snap.higher_lows and price > snap.last_swing_high:
        snap.choch_bullish = True
        snap.structure_score = max(snap.structure_score, 0.85)
    if snap.trend == Trend.BULLISH and snap.lower_highs and price < snap.last_swing_low:
        snap.choch_bearish = True
        snap.structure_score = max(snap.structure_score, 0.85)

    return snap


def detect_trend_from_emas(ind: IndicatorSnapshot, price: float) -> Trend:
    if ind.ema9 > ind.ema21 > ind.ema50 and price > ind.ema21:
        if ind.adx > 28 and ind.plus_di > ind.minus_di:
            return Trend.STRONG_BULL
        return Trend.BULLISH
    if ind.ema9 < ind.ema21 < ind.ema50 and price < ind.ema21:
        if ind.adx > 28 and ind.minus_di > ind.plus_di:
            return Trend.STRONG_BEAR
        return Trend.BEARISH
    return Trend.NEUTRAL


# =============================================================================
# SINGLE TIMEFRAME ANALYSIS
# =============================================================================

def analyze_timeframe(tf: str, candles: List[Candle]) -> TFAnalysis:
    if len(candles) < 60:
        return TFAnalysis(
            timeframe=tf,
            candles=candles,
            indicators=IndicatorSnapshot(),
            structure=StructureSnapshot(),
            patterns=[],
            trend=Trend.NEUTRAL,
        )

    ind = build_indicators(candles)
    structure = analyze_structure(candles)
    patterns = scan_patterns(candles)
    price = candles[-1].close
    trend = detect_trend_from_emas(ind, price)

    # refine with structure
    if structure.trend == Trend.BULLISH and trend in (Trend.BULLISH, Trend.STRONG_BULL, Trend.NEUTRAL):
        if trend == Trend.NEUTRAL:
            trend = Trend.BULLISH
    elif structure.trend == Trend.BEARISH and trend in (Trend.BEARISH, Trend.STRONG_BEAR, Trend.NEUTRAL):
        if trend == Trend.NEUTRAL:
            trend = Trend.BEARISH

    # momentum score
    mom_score = 0.0
    if ind.rsi > 55 and ind.macd_hist > 0 and ind.momentum > 0:
        mom_score = 0.7 + min(0.3, (ind.rsi - 50) / 100)
    elif ind.rsi < 45 and ind.macd_hist < 0 and ind.momentum < 0:
        mom_score = 0.7 + min(0.3, (50 - ind.rsi) / 100)
    else:
        mom_score = 0.35

    # pattern score (best directional pattern)
    pattern_score = 0.0
    best_dir = Direction.NONE
    for p in patterns:
        if p.direction != Direction.NONE and p.strength > pattern_score:
            pattern_score = p.strength
            best_dir = p.direction

    # overall bias
    bias = Direction.NONE
    conf = 0.0
    bull_points = 0.0
    bear_points = 0.0

    if trend in (Trend.BULLISH, Trend.STRONG_BULL):
        bull_points += 0.35
    if trend in (Trend.BEARISH, Trend.STRONG_BEAR):
        bear_points += 0.35
    if structure.bos_bullish or structure.choch_bullish:
        bull_points += 0.25
    if structure.bos_bearish or structure.choch_bearish:
        bear_points += 0.25
    if best_dir == Direction.BUY:
        bull_points += pattern_score * 0.30
    if best_dir == Direction.SELL:
        bear_points += pattern_score * 0.30
    if ind.rsi > 52 and ind.macd_hist > 0:
        bull_points += 0.15
    if ind.rsi < 48 and ind.macd_hist < 0:
        bear_points += 0.15

    if bull_points > bear_points + 0.12:
        bias = Direction.BUY
        conf = clamp(bull_points, 0.3, 0.95)
    elif bear_points > bull_points + 0.12:
        bias = Direction.SELL
        conf = clamp(bear_points, 0.3, 0.95)

    return TFAnalysis(
        timeframe=tf,
        candles=candles,
        indicators=ind,
        structure=structure,
        patterns=patterns,
        trend=trend,
        momentum_score=round(mom_score, 3),
        pattern_score=round(pattern_score, 3),
        overall_bias=bias,
        confidence=round(conf, 3),
    )


# =============================================================================
# MULTI-TIMEFRAME CONFLUENCE & SIGNAL ENGINE
# =============================================================================

def multi_tf_confluence(analyses: Dict[str, TFAnalysis]) -> Tuple[Direction, float, Dict[str, str]]:
    """Returns (direction, score 0-100, bias_map)."""
    bias_map: Dict[str, str] = {}
    buy_weight = 0.0
    sell_weight = 0.0
    total_weight = 0.0

    # Higher timeframes weigh more
    weights = {
        "4h": 1.35,
        "1h": 1.20,
        "30m": 1.00,
        "15m": 0.95,
        "5m": 0.70,
        "1m": 0.45,
    }

    for tf, ana in analyses.items():
        w = weights.get(tf, 0.8)
        total_weight += w
        bias_map[tf] = ana.overall_bias.value
        if ana.overall_bias == Direction.BUY:
            buy_weight += w * ana.confidence
        elif ana.overall_bias == Direction.SELL:
            sell_weight += w * ana.confidence

    if total_weight == 0:
        return Direction.NONE, 0.0, bias_map

    buy_score = (buy_weight / total_weight) * 100
    sell_score = (sell_weight / total_weight) * 100

    if buy_score > sell_score + 12:
        return Direction.BUY, round(buy_score, 1), bias_map
    if sell_score > buy_score + 12:
        return Direction.SELL, round(sell_score, 1), bias_map
    return Direction.NONE, round(max(buy_score, sell_score), 1), bias_map


def compute_signal_score(
    direction: Direction,
    analyses: Dict[str, TFAnalysis],
    multi_score: float,
    session: Session,
    atr_pct: float,
    patterns: List[PatternHit],
) -> Tuple[float, Dict[str, float]]:
    """Returns total score 0-100 and breakdown."""
    breakdown: Dict[str, float] = {}

    # 1. Trend alignment across TFs
    aligned = 0
    total = 0
    for tf, ana in analyses.items():
        total += 1
        if ana.overall_bias == direction:
            aligned += 1
        elif ana.trend.value.startswith("strong") and (
            (direction == Direction.BUY and "bull" in ana.trend.value) or
            (direction == Direction.SELL and "bear" in ana.trend.value)
        ):
            aligned += 1
    trend_score = (aligned / max(total, 1)) * WEIGHT_TREND_ALIGNMENT
    breakdown["trend"] = round(trend_score, 1)

    # 2. Pattern strength
    best_pat = 0.0
    for p in patterns:
        if p.direction == direction:
            best_pat = max(best_pat, p.strength)
    pattern_score = best_pat * WEIGHT_PATTERN_STRENGTH
    breakdown["pattern"] = round(pattern_score, 1)

    # 3. Momentum
    primary = analyses.get(PRIMARY_TF) or next(iter(analyses.values()), None)
    mom = 0.0
    if primary:
        ind = primary.indicators
        if direction == Direction.BUY:
            if ind.rsi > 50 and ind.macd_hist > 0:
                mom = 0.75 + min(0.25, (ind.rsi - 50) / 80)
            else:
                mom = 0.30
        else:
            if ind.rsi < 50 and ind.macd_hist < 0:
                mom = 0.75 + min(0.25, (50 - ind.rsi) / 80)
            else:
                mom = 0.30
    mom_score = mom * WEIGHT_MOMENTUM
    breakdown["momentum"] = round(mom_score, 1)

    # 4. Structure
    struct = 0.0
    if primary:
        s = primary.structure
        if direction == Direction.BUY and (s.bos_bullish or s.choch_bullish or s.higher_lows):
            struct = 0.85
        elif direction == Direction.SELL and (s.bos_bearish or s.choch_bearish or s.lower_highs):
            struct = 0.85
        else:
            struct = s.structure_score * 0.6
    struct_score = struct * WEIGHT_STRUCTURE
    breakdown["structure"] = round(struct_score, 1)

    # 5. Multi-TF confluence
    mtf_score = (multi_score / 100.0) * WEIGHT_MULTI_TF
    breakdown["multi_tf"] = round(mtf_score, 1)

    # 6. Session
    sess = session_score(session) * WEIGHT_SESSION
    breakdown["session"] = round(sess, 1)

    # 7. Volatility (sweet spot)
    if MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT:
        vol = 0.9
    elif atr_pct < MIN_ATR_PCT:
        vol = 0.35
    else:
        vol = 0.45
    vol_score = vol * WEIGHT_VOLATILITY
    breakdown["volatility"] = round(vol_score, 1)

    total = sum(breakdown.values())
    return round(total, 1), breakdown


def grade_from_score(score: float, confidence: int, rr1: float) -> Grade:
    if score >= 78 and confidence >= 80 and rr1 >= 1.8:
        return Grade.A
    if score >= 66 and confidence >= 72 and rr1 >= 1.5:
        return Grade.B
    if score >= 55 and confidence >= 65 and rr1 >= 1.3:
        return Grade.C
    return Grade.REJECT


def build_levels(direction: Direction, price: float, atr: float) -> Tuple[float, float, float, float]:
    if atr <= 0:
        atr = price * 0.0015
    if direction == Direction.BUY:
        entry = price
        sl = entry - atr * ATR_SL_MULTIPLIER
        tp1 = entry + atr * ATR_TP1_MULTIPLIER
        tp2 = entry + atr * ATR_TP2_MULTIPLIER
        tp3 = entry + atr * ATR_TP3_MULTIPLIER
    else:
        entry = price
        sl = entry + atr * ATR_SL_MULTIPLIER
        tp1 = entry - atr * ATR_TP1_MULTIPLIER
        tp2 = entry - atr * ATR_TP2_MULTIPLIER
        tp3 = entry - atr * ATR_TP3_MULTIPLIER
    return (
        round_price(entry),
        round_price(sl),
        round_price(tp1),
        round_price(tp2),
        round_price(tp3),
    )


def generate_signal(analyses: Dict[str, TFAnalysis], tick: Tick) -> Signal:
    session = get_session()
    direction, multi_score, bias_map = multi_tf_confluence(analyses)

    empty = Signal(
        valid=False,
        direction=Direction.NONE,
        entry=0, sl=0, tp1=0, tp2=0, tp3=0,
        confidence=0, grade=Grade.REJECT,
        reason="لا توجد محاذاة كافية بين الفريمات",
        strategy="multi_tf_confluence",
        session=session.value,
        timestamp=utc_iso(),
    )

    if direction == Direction.NONE:
        return empty

    # Collect best patterns across TFs (prefer primary + higher)
    all_patterns: List[PatternHit] = []
    for tf in [PRIMARY_TF, "1h", "4h", "30m", "5m"]:
        if tf in analyses:
            all_patterns.extend(analyses[tf].patterns)

    primary = analyses.get(PRIMARY_TF)
    atr = primary.indicators.atr if primary else tick.mid * 0.0015
    atr_pct = primary.indicators.atr_pct if primary else 0.1

    score, breakdown = compute_signal_score(
        direction, analyses, multi_score, session, atr_pct, all_patterns
    )

    entry, sl, tp1, tp2, tp3 = build_levels(direction, tick.mid, atr)
    risk = abs(entry - sl)
    if risk <= 0:
        return empty

    rr1 = abs(tp1 - entry) / risk
    rr2 = abs(tp2 - entry) / risk
    rr3 = abs(tp3 - entry) / risk

    confidence = int(clamp(score * 0.85 + multi_score * 0.15, 40, 96))
    grade = grade_from_score(score, confidence, rr1)

    # Build reason
    top_patterns = [p.name for p in all_patterns if p.direction == direction][:3]
    reason_parts = []
    if top_patterns:
        reason_parts.append(" + ".join(top_patterns))
    if primary and primary.structure.bos_bullish and direction == Direction.BUY:
        reason_parts.append("BOS صاعد")
    if primary and primary.structure.bos_bearish and direction == Direction.SELL:
        reason_parts.append("BOS هابط")
    if multi_score >= 65:
        reason_parts.append(f"توافق فريمات ({multi_score:.0f}%)")
    reason = " | ".join(reason_parts) if reason_parts else "محاذاة تقنية متعددة"

    return Signal(
        valid=True,
        direction=direction,
        entry=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        confidence=confidence,
        grade=grade,
        reason=reason,
        strategy="MTF_Confluence_Structure_Patterns",
        patterns=top_patterns,
        timeframe_bias=bias_map,
        rr1=round(rr1, 2),
        rr2=round(rr2, 2),
        rr3=round(rr3, 2),
        atr=round(atr, 3),
        session=session.value,
        timestamp=utc_iso(),
        score_breakdown=breakdown,
        multi_tf_score=multi_score,
    )


# =============================================================================
# FILTERS & RISK MANAGEMENT
# =============================================================================

def pass_basic_filters(tick: Tick, signal: Signal, analyses: Dict[str, TFAnalysis]) -> Tuple[bool, str]:
    if tick.spread > MAX_SPREAD:
        return False, f"السبريد مرتفع: {tick.spread:.2f}"

    primary = analyses.get(PRIMARY_TF)
    if primary:
        atr_pct = primary.indicators.atr_pct
        if atr_pct < MIN_ATR_PCT:
            return False, f"تذبذب منخفض جدًا (ATR%={atr_pct:.3f})"
        if atr_pct > MAX_ATR_PCT:
            return False, f"تذبذب مرتفع جدًا (ATR%={atr_pct:.3f})"

    session = get_session()
    if REQUIRE_SESSION_FILTER and session.value not in PREFERRED_SESSIONS and session != Session.LONDON_NY:
        # still allow if grade is A
        if signal.grade != Grade.A:
            return False, f"جلسة غير مفضلة: {session.value}"

    if signal.confidence < MIN_CONFIDENCE:
        return False, f"ثقة منخفضة: {signal.confidence}%"

    if signal.rr1 < MIN_RR_RATIO:
        return False, f"نسبة مخاطرة/عائد ضعيفة: {signal.rr1}"

    if signal.grade == Grade.REJECT:
        return False, "التقييم مرفوض (أقل من C)"

    # Grade filter
    grade_order = {"A": 3, "B": 2, "C": 1, "REJECT": 0}
    if grade_order.get(signal.grade.value, 0) < grade_order.get(MIN_GRADE, 2):
        return False, f"التقييم أقل من المطلوب ({MIN_GRADE})"

    return True, "OK"


def pass_state_filters(signal: Signal) -> Tuple[bool, str]:
    reset_daily_if_needed()

    if state.signals_today >= MAX_DAILY_SIGNALS:
        return False, f"وصل الحد اليومي ({MAX_DAILY_SIGNALS})"

    if time.time() - state.last_signal_time < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (time.time() - state.last_signal_time))
        return False, f"فترة تهدئة متبقية: {remaining}s"

    key = hash_signal(signal.direction.value, signal.entry, signal.sl, signal.tp1)
    if key == state.last_signal_key:
        return False, "إشارة مكررة"

    # avoid immediate flip-flop
    if (state.last_signal_direction and
            state.last_signal_direction != signal.direction.value and
            time.time() - state.last_signal_time < COOLDOWN_SECONDS * 1.5):
        return False, "تجنب الانقلاب السريع في الاتجاه"

    return True, "OK"


# =============================================================================
# TELEGRAM — messages + interactive keyboard
# =============================================================================

MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "💰 رصيدي"}, {"text": "📊 سعر XAUUSD"}],
        [{"text": "📈 صفقاتي المفتوحة"}, {"text": "📜 السجل"}],
        [{"text": "📦 تحميل القاعدة"}, {"text": "📊 تصدير CSV"}],
        [{"text": "📰 أخبار السوق"}, {"text": "🆔 ايدي"}],
        [{"text": "ℹ️ حالة البوت"}],
    ],
    "resize_keyboard": True,
    "is_persistent": True,
}


def tg_api(method: str, payload: Optional[Dict] = None) -> Optional[Dict]:
    if not BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Telegram API ({method}): {e}")
        return None


def send_telegram(text: str, chat_id: Optional[str] = None, reply_markup: Optional[Dict] = None, parse_mode: str = "HTML") -> bool:
    cid = chat_id or CHAT_ID
    if not BOT_TOKEN or not cid:
        logger.warning("BOT_TOKEN أو CHAT_ID غير موجودين")
        return False
    payload: Dict[str, Any] = {
        "chat_id": cid,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = tg_api("sendMessage", payload)
    return bool(result and result.get("ok"))


def send_document_text(chat_id: str, content: str) -> bool:
    for i in range(0, min(len(content), 12000), 3500):
        send_telegram(f"<pre>{html_mod.escape(content[i:i+3500])}</pre>", chat_id)
    return True


def handle_command(chat_id: str, text: str) -> None:
    global _last_tick
    t = (text or "").strip()

    if t in ("/start", "start", "ابدأ"):
        send_telegram(
            f"🚀 <b>{APP_NAME}</b> v{VERSION}\n\n"
            f"بوت إشارات XAUUSD الاحترافي\nاستخدم الأزرار بالأسفل 👇",
            chat_id, MAIN_KEYBOARD,
        )
        return

    if t in ("💰 رصيدي", "رصيدي", "/balance"):
        stats = db_stats()
        send_telegram(
            f"💰 <b>إحصائيات الإشارات</b>\n\n"
            f"الإجمالي: {stats['total']}\n"
            f"مفتوحة: {stats['open']}\n"
            f"رابح: {stats['wins']}\n"
            f"خاسر: {stats['losses']}\n"
            f"اليوم: {state.signals_today}/{MAX_DAILY_SIGNALS}",
            chat_id, MAIN_KEYBOARD,
        )
        return

    if t in ("📊 سعر XAUUSD", "سعر XAUUSD", "/price"):
        tick = client.get_tick(SYMBOL) or _last_tick
        if tick:
            send_telegram(
                f"📊 <b>سعر {SYMBOL}</b>\n\n"
                f"السعر: <code>{tick.mid}</code>\n"
                f"Bid: {tick.bid} | Ask: {tick.ask}\n"
                f"السبريد: {tick.spread}\n"
                f"التغير اليومي: {tick.day_diff_pct:+.2f}%\n"
                f"الجلسة: {get_session().value}",
                chat_id, MAIN_KEYBOARD,
            )
        else:
            send_telegram("تعذر جلب السعر حالياً", chat_id, MAIN_KEYBOARD)
        return

    if t in ("📈 صفقاتي المفتوحة", "صفقاتي المفتوحة", "/open"):
        opens = db_open_trades()
        if not opens:
            send_telegram("لا توجد صفقات مفتوحة حالياً", chat_id, MAIN_KEYBOARD)
            return
        lines = [f"📈 <b>الصفقات المفتوحة ({len(opens)})</b>\n"]
        for o in opens[:15]:
            lines.append(
                f"#{o['id']} {o['direction']} Entry:{o['entry']} "
                f"SL:{o['sl']} TP1:{o['tp1']} | {o['grade']}"
            )
        send_telegram("\n".join(lines), chat_id, MAIN_KEYBOARD)
        return

    if t in ("📜 السجل", "السجل", "/history"):
        hist = db_history(15)
        if not hist:
            send_telegram("السجل فارغ", chat_id, MAIN_KEYBOARD)
            return
        lines = ["📜 <b>آخر الإشارات</b>\n"]
        for h in hist:
            st = h.get("result") or h.get("status")
            lines.append(f"#{h['id']} {h['direction']} {h['entry']} → {st} ({h['grade']})")
        send_telegram("\n".join(lines), chat_id, MAIN_KEYBOARD)
        return

    if t in ("📦 تحميل القاعدة", "تحميل القاعدة", "/db"):
        stats = db_stats()
        send_telegram(
            f"📦 <b>قاعدة البيانات</b>\n\n"
            f"الملف: {DB_FILE}\n"
            f"الإشارات: {stats['total']}\n"
            f"المفتوحة: {stats['open']}\n"
            f"استخدم «تصدير CSV» لتحميل البيانات",
            chat_id, MAIN_KEYBOARD,
        )
        return

    if t in ("📊 تصدير CSV", "تصدير CSV", "/csv"):
        send_telegram("📊 تصدير CSV:", chat_id, MAIN_KEYBOARD)
        send_document_text(chat_id, db_export_csv())
        return

    if t in ("📰 أخبار السوق", "أخبار السوق", "/news"):
        send_telegram(
            f"📰 <b>ملخص السوق</b>\n\n"
            f"الجلسة الحالية: {get_session().value}\n"
            f"الرمز: {SYMBOL}\n"
            f"آخر سعر: {state.last_price or '—'}\n"
            f"الحالة: يعمل ✅",
            chat_id, MAIN_KEYBOARD,
        )
        return

    if t in ("🆔 ايدي", "ايدي", "/id"):
        send_telegram(f"🆔 Chat ID:\n<code>{chat_id}</code>", chat_id, MAIN_KEYBOARD)
        return

    if t in ("ℹ️ حالة البوت", "حالة البوت", "/status"):
        stats = db_stats()
        send_telegram(
            f"ℹ️ <b>حالة البوت</b>\n\n"
            f"الحالة: ACTIVE ✅\n"
            f"Uptime: {uptime_str()}\n"
            f"السعر: {state.last_price}\n"
            f"إشارات اليوم: {state.signals_today}/{MAX_DAILY_SIGNALS}\n"
            f"مفتوحة: {stats['open']} | رابح: {stats['wins']} | خاسر: {stats['losses']}\n"
            f"الخطأ: {state.last_error or 'None'}",
            chat_id, MAIN_KEYBOARD,
        )
        return

    send_telegram("استخدم الأزرار بالأسفل 👇", chat_id, MAIN_KEYBOARD)


def poll_telegram_commands() -> None:
    if not BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {"timeout": 5, "offset": state.last_update_id + 1}
        full = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(full, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data.get("ok"):
            return
        for upd in data.get("result", []):
            uid = upd.get("update_id", 0)
            if uid > state.last_update_id:
                state.last_update_id = uid
            msg = upd.get("message") or {}
            chat = msg.get("chat") or {}
            chat_id = str(chat.get("id", ""))
            text = msg.get("text") or ""
            if chat_id and text:
                if not CHAT_ID or chat_id == str(CHAT_ID) or text.startswith("/"):
                    handle_command(chat_id, text)
        save_state()
    except Exception as e:
        logger.debug(f"Telegram poll: {e}")


def format_signal_message(signal: Signal, tick: Tick, analyses: Dict[str, TFAnalysis]) -> str:
    emoji = "🟢" if signal.direction == Direction.BUY else "🔴"
    grade_emoji = {"A": "🏆", "B": "⭐", "C": "🔹"}.get(signal.grade.value, "⚪")

    dir_ar = "شراء" if signal.direction == Direction.BUY else "بيع"

    lines = [
        f"{emoji} <b>إشارة ذهب XAUUSD</b> {grade_emoji}",
        f"",
        f"<b>التصنيف:</b> {signal.grade.value}",
        f"<b>الاتجاه:</b> {dir_ar} ({signal.direction.value})",
        f"<b>الثقة:</b> {signal.confidence}%",
        f"",
        f"📍 <b>الدخول:</b> <code>{signal.entry}</code>",
        f"🛑 <b>الوقف (SL):</b> <code>{signal.sl}</code>",
        f"🎯 <b>الهدف 1:</b> <code>{signal.tp1}</code>  (RR {signal.rr1})",
        f"🎯 <b>الهدف 2:</b> <code>{signal.tp2}</code>  (RR {signal.rr2})",
        f"🎯 <b>الهدف 3:</b> <code>{signal.tp3}</code>  (RR {signal.rr3})",
        f"",
        f"📊 <b>السعر الحالي:</b> {tick.mid}",
        f"📉 <b>السبريد:</b> {tick.spread}",
        f"⏱ <b>الجلسة:</b> {signal.session}",
        f"📐 <b>ATR:</b> {signal.atr}",
        f"",
    ]

    if signal.patterns:
        lines.append(f"🕯 <b>النماذج:</b> {', '.join(signal.patterns)}")
    lines.append(f"🧠 <b>السبب:</b> {signal.reason}")

    # TF bias summary
    if signal.timeframe_bias:
        bias_str = " | ".join(f"{tf}:{b}" for tf, b in signal.timeframe_bias.items() if b != "NONE")
        if bias_str:
            lines.append(f"🖥 <b>الفريمات:</b> {bias_str}")

    lines.append("")
    lines.append(f"<i>{APP_NAME} v{VERSION}</i>")
    lines.append(f"<i>{signal.timestamp}</i>")

    return "\n".join(lines)


def format_status_message(tick: Tick, analyses: Dict[str, TFAnalysis]) -> str:
    session = get_session()
    primary = analyses.get(PRIMARY_TF)
    lines = [
        f"📊 <b>حالة السوق — {SYMBOL}</b>",
        f"",
        f"السعر: <code>{tick.mid}</code>",
        f"السبريد: {tick.spread}",
        f"الجلسة: {session.value}",
        f"إشارات اليوم: {state.signals_today}/{MAX_DAILY_SIGNALS}",
    ]
    if primary:
        ind = primary.indicators
        lines.extend([
            f"",
            f"RSI(15m): {ind.rsi}",
            f"ATR%: {ind.atr_pct}",
            f"ADX: {ind.adx}",
            f"الاتجاه: {primary.trend.value}",
        ])
    return "\n".join(lines)


# =============================================================================
# MAIN ANALYSIS PIPELINE
# =============================================================================

def fetch_all_timeframes() -> Dict[str, List[Candle]]:
    result: Dict[str, List[Candle]] = {}
    for tf in TIMEFRAMES:
        try:
            candles = client.get_ohlc(SYMBOL, tf, CANDLES_PER_TF)
            if candles:
                result[tf] = candles
                logger.info(f"Loaded {len(candles)} candles for {tf}")
            else:
                logger.warning(f"No candles for {tf}")
        except Exception as e:
            logger.error(f"Error fetching {tf}: {e}")
        time.sleep(0.15)  # be gentle
    return result


def run_full_analysis() -> Optional[Signal]:
    global _last_tick, _last_analyses
    tick = client.get_tick(SYMBOL)
    if not tick or tick.mid <= 0:
        logger.error("فشل جلب السعر الحالي")
        return None

    _last_tick = tick
    state.last_price = tick.mid
    db_auto_close_by_price(tick.mid)

    if tick.market_state == "closed":
        logger.info("السوق مغلق حاليًا")
        return None

    candles_map = fetch_all_timeframes()
    if not candles_map:
        logger.error("لا توجد بيانات شموع")
        return None

    analyses: Dict[str, TFAnalysis] = {}
    for tf, candles in candles_map.items():
        analyses[tf] = analyze_timeframe(tf, candles)
    _last_analyses = analyses

    signal = generate_signal(analyses, tick)

    if signal.valid:
        logger.info(
            f"Signal candidate: {signal.direction.value} | Grade {signal.grade.value} | "
            f"Conf {signal.confidence}% | Score {sum(signal.score_breakdown.values()):.1f} | "
            f"MTF {signal.multi_tf_score}"
        )
        logger.debug(f"Breakdown: {signal.score_breakdown}")

    ok, reason = pass_basic_filters(tick, signal, analyses)
    if not ok:
        logger.info(f"Filter rejected: {reason}")
        state.consecutive_rejects += 1
        return None

    ok2, reason2 = pass_state_filters(signal)
    if not ok2:
        logger.info(f"State filter: {reason2}")
        return None

    msg = format_signal_message(signal, tick, analyses)
    if send_telegram(msg, reply_markup=MAIN_KEYBOARD):
        key = hash_signal(signal.direction.value, signal.entry, signal.sl, signal.tp1)
        state.last_signal_key = key
        state.last_signal_time = time.time()
        state.last_signal_direction = signal.direction.value
        state.signals_today += 1
        state.total_signals_sent += 1
        state.consecutive_rejects = 0
        state.grade_counts[signal.grade.value] = state.grade_counts.get(signal.grade.value, 0) + 1
        state.history.append({
            "time": signal.timestamp,
            "direction": signal.direction.value,
            "grade": signal.grade.value,
            "entry": signal.entry,
            "confidence": signal.confidence,
        })
        db_insert_signal(signal)
        save_state()
        logger.info(f"✅ Signal sent: {signal.direction.value} Grade-{signal.grade.value} @ {signal.entry}")
        return signal
    else:
        logger.warning("Failed to deliver Telegram message")
        return None


# =============================================================================
# STARTUP & MAIN LOOP
# =============================================================================

def print_banner() -> None:
    banner = f"""
╔══════════════════════════════════════════════════════════╗
║  {APP_NAME}  v{VERSION}
║  Symbol: {SYMBOL}  |  Max daily: {MAX_DAILY_SIGNALS}
║  TFs: {', '.join(TIMEFRAMES)}
║  Candles/TF: {CANDLES_PER_TF}  |  Min Grade: {MIN_GRADE}
╚══════════════════════════════════════════════════════════╝
"""
    print(banner)
    logger.info(f"Starting {APP_NAME} v{VERSION}")


def validate_config() -> bool:
    ok = True
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing")
        ok = False
    if not CHAT_ID:
        logger.error("CHAT_ID missing")
        ok = False
    return ok


def startup_test() -> bool:
    logger.info("Testing BIQUOTE connection...")
    tick = client.get_tick(SYMBOL)
    if not tick:
        logger.error("Cannot reach BIQUOTE")
        return False
    logger.info(f"Price OK: {SYMBOL} mid={tick.mid} spread={tick.spread}")
    return True


def bot_loop() -> None:
    global state
    state = load_state()
    if not state.start_time:
        state.start_time = time.time()
    reset_daily_if_needed()
    db_init()
    print_banner()
    if not validate_config():
        logger.error("Configuration incomplete.")
        return
    if not startup_test():
        logger.error("Startup test failed.")
        return
    send_telegram(
        f"🚀 <b>{APP_NAME}</b> v{VERSION}\n"
        f"تم التشغيل بنجاح\n"
        f"الرمز: {SYMBOL}\n"
        f"الحد اليومي: {MAX_DAILY_SIGNALS} صفقة\n"
        f"التصنيف الأدنى: {MIN_GRADE}",
        reply_markup=MAIN_KEYBOARD,
    )
    logger.info("Bot loop started")
    while True:
        try:
            poll_telegram_commands()
            run_full_analysis()
        except Exception as e:
            state.last_error = str(e)
            logger.exception(f"Main loop error: {e}")
            save_state()
        time.sleep(POLL_SECONDS)

# =============================================================================
# EXTENDED FEATURES — DIVERGENCE, FVG, ORDER BLOCKS, ENSEMBLE STRATEGIES
# =============================================================================

@dataclass
class DivergenceHit:
    kind: str          # regular / hidden
    direction: Direction
    indicator: str     # RSI / MACD
    strength: float
    description: str = ""


@dataclass
class FairValueGap:
    direction: Direction
    top: float
    bottom: float
    midpoint: float
    filled: bool = False
    strength: float = 0.6


@dataclass
class OrderBlock:
    direction: Direction
    high: float
    low: float
    midpoint: float
    strength: float = 0.65
    broken: bool = False


def detect_rsi_divergence(candles: List[Candle], rsi_values: List[float], lookback: int = 30) -> List[DivergenceHit]:
    """Simple regular & hidden RSI divergence detection."""
    hits: List[DivergenceHit] = []
    if len(candles) < lookback + 5 or len(rsi_values) < lookback + 5:
        return hits

    closes = [c.close for c in candles]
    # find recent swing points in price and RSI
    price_highs, price_lows = find_swing_points(candles[-lookback:], 2, 2)
    if len(price_highs) < 2 or len(price_lows) < 2:
        return hits

    # Regular bearish: higher high in price, lower high in RSI
    try:
        p1, p2 = price_highs[-2], price_highs[-1]
        # map to RSI (approximate index)
        r1 = rsi_values[-(lookback - p1[0])] if p1[0] < lookback else rsi_values[-1]
        r2 = rsi_values[-(lookback - p2[0])] if p2[0] < lookback else rsi_values[-1]
        if p2[1] > p1[1] and r2 < r1:
            hits.append(DivergenceHit(
                "regular", Direction.SELL, "RSI", 0.78,
                "دايفرجنس هبوطي منتظم على RSI"
            ))
        if p2[1] < p1[1] and r2 > r1:
            hits.append(DivergenceHit(
                "hidden", Direction.SELL, "RSI", 0.65,
                "دايفرجنس هبوطي مخفي على RSI"
            ))
    except Exception:
        pass

    try:
        p1, p2 = price_lows[-2], price_lows[-1]
        r1 = rsi_values[-(lookback - p1[0])] if p1[0] < lookback else rsi_values[-1]
        r2 = rsi_values[-(lookback - p2[0])] if p2[0] < lookback else rsi_values[-1]
        if p2[1] < p1[1] and r2 > r1:
            hits.append(DivergenceHit(
                "regular", Direction.BUY, "RSI", 0.78,
                "دايفرجنس صعودي منتظم على RSI"
            ))
        if p2[1] > p1[1] and r2 < r1:
            hits.append(DivergenceHit(
                "hidden", Direction.BUY, "RSI", 0.65,
                "دايفرجنس صعودي مخفي على RSI"
            ))
    except Exception:
        pass

    return hits


def detect_fair_value_gaps(candles: List[Candle], lookback: int = 40) -> List[FairValueGap]:
    """3-candle Fair Value Gap detection."""
    gaps: List[FairValueGap] = []
    if len(candles) < 5:
        return gaps
    start = max(0, len(candles) - lookback)
    for i in range(start + 2, len(candles)):
        c0, c1, c2 = candles[i - 2], candles[i - 1], candles[i]
        # Bullish FVG: low of c2 > high of c0
        if c2.low > c0.high:
            top = c2.low
            bottom = c0.high
            gaps.append(FairValueGap(
                Direction.BUY, top, bottom, midpoint(top, bottom),
                filled=False, strength=0.70
            ))
        # Bearish FVG: high of c2 < low of c0
        if c2.high < c0.low:
            top = c0.low
            bottom = c2.high
            gaps.append(FairValueGap(
                Direction.SELL, top, bottom, midpoint(top, bottom),
                filled=False, strength=0.70
            ))
    return gaps[-5:]  # keep recent


def detect_order_blocks(candles: List[Candle], lookback: int = 50) -> List[OrderBlock]:
    """Simplified last opposing candle before impulsive move."""
    blocks: List[OrderBlock] = []
    if len(candles) < 15:
        return blocks
    recent = candles[-lookback:]
    for i in range(5, len(recent) - 3):
        c = recent[i]
        # bullish OB: last down candle before strong up move
        if c.is_bearish:
            move = recent[i + 1].close - c.close
            if move > c.range * 1.6:
                blocks.append(OrderBlock(
                    Direction.BUY, c.high, c.low, midpoint(c.high, c.low), 0.68
                ))
        # bearish OB
        if c.is_bullish:
            move = c.close - recent[i + 1].close
            if move > c.range * 1.6:
                blocks.append(OrderBlock(
                    Direction.SELL, c.high, c.low, midpoint(c.high, c.low), 0.68
                ))
    return blocks[-4:]


def calculate_cci(candles: List[Candle], period: int = 20) -> float:
    if len(candles) < period:
        return 0.0
    tp = [(c.high + c.low + c.close) / 3 for c in candles[-period:]]
    sma_tp = sum(tp) / period
    mad = sum(abs(x - sma_tp) for x in tp) / period
    if mad == 0:
        return 0.0
    return (tp[-1] - sma_tp) / (0.015 * mad)


def calculate_williams_r(candles: List[Candle], period: int = 14) -> float:
    if len(candles) < period:
        return -50.0
    recent = candles[-period:]
    highest = max(c.high for c in recent)
    lowest = min(c.low for c in recent)
    if highest == lowest:
        return -50.0
    return ((highest - recent[-1].close) / (highest - lowest)) * -100


def calculate_obv_trend(candles: List[Candle]) -> float:
    """Simple OBV slope using tick_volume as proxy."""
    if len(candles) < 20:
        return 0.0
    obv = [0.0]
    for i in range(1, len(candles)):
        vol = candles[i].tick_volume or 1.0
        if candles[i].close > candles[i - 1].close:
            obv.append(obv[-1] + vol)
        elif candles[i].close < candles[i - 1].close:
            obv.append(obv[-1] - vol)
        else:
            obv.append(obv[-1])
    recent = obv[-15:]
    if len(recent) < 5:
        return 0.0
    return (recent[-1] - recent[0]) / max(abs(recent[0]), 1.0)


# -----------------------------------------------------------------------------
# Additional Pattern Detectors
# -----------------------------------------------------------------------------

def detect_three_inside_up(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bearish and b.is_bullish and b.high < a.high and b.low > a.low and
            c.is_bullish and c.close > a.open):
        return PatternHit("Three Inside Up", Direction.BUY, 0.76, PatternType.REVERSAL, 3,
                          "ثلاثة داخل صاعد")
    return None


def detect_three_inside_down(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bullish and b.is_bearish and b.high < a.high and b.low > a.low and
            c.is_bearish and c.close < a.open):
        return PatternHit("Three Inside Down", Direction.SELL, 0.76, PatternType.REVERSAL, 3,
                          "ثلاثة داخل هابط")
    return None


def detect_three_outside_up(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bearish and b.is_bullish and b.close > a.open and b.open < a.close and
            c.is_bullish and c.close > b.close):
        return PatternHit("Three Outside Up", Direction.BUY, 0.79, PatternType.REVERSAL, 3,
                          "ثلاثة خارج صاعد")
    return None


def detect_three_outside_down(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bullish and b.is_bearish and b.close < a.open and b.open > a.close and
            c.is_bearish and c.close < b.close):
        return PatternHit("Three Outside Down", Direction.SELL, 0.79, PatternType.REVERSAL, 3,
                          "ثلاثة خارج هابط")
    return None


def detect_bullish_kicker(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bearish and b.is_bullish and b.open > a.open:
        return PatternHit("Bullish Kicker", Direction.BUY, 0.84, PatternType.REVERSAL, 2,
                          "ركلة صاعدة — انعكاس قوي")
    return None


def detect_bearish_kicker(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bullish and b.is_bearish and b.open < a.open:
        return PatternHit("Bearish Kicker", Direction.SELL, 0.84, PatternType.REVERSAL, 2,
                          "ركلة هابطة — انعكاس قوي")
    return None


def detect_rising_three_methods(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 5:
        return None
    a, b, c, d, e = candles[-5:]
    if (a.is_bullish and _is_long_body(a) and
            b.is_bearish and c.is_bearish and d.is_bearish and
            e.is_bullish and e.close > a.close and
            max(b.high, c.high, d.high) < a.high and
            min(b.low, c.low, d.low) > a.low):
        return PatternHit("Rising Three Methods", Direction.BUY, 0.81, PatternType.CONTINUATION, 5,
                          "الطرق الثلاث الصاعدة")
    return None


def detect_falling_three_methods(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 5:
        return None
    a, b, c, d, e = candles[-5:]
    if (a.is_bearish and _is_long_body(a) and
            b.is_bullish and c.is_bullish and d.is_bullish and
            e.is_bearish and e.close < a.close and
            max(b.high, c.high, d.high) < a.high and
            min(b.low, c.low, d.low) > a.low):
        return PatternHit("Falling Three Methods", Direction.SELL, 0.81, PatternType.CONTINUATION, 5,
                          "الطرق الثلاث الهابطة")
    return None


# Register extra detectors
EXTRA_PATTERN_DETECTORS = [
    detect_three_inside_up,
    detect_three_inside_down,
    detect_three_outside_up,
    detect_three_outside_down,
    detect_bullish_kicker,
    detect_bearish_kicker,
    detect_rising_three_methods,
    detect_falling_three_methods,
]

# Extend the global list
PATTERN_DETECTORS.extend(EXTRA_PATTERN_DETECTORS)


# -----------------------------------------------------------------------------
# Ensemble Strategy Scoring
# -----------------------------------------------------------------------------

class StrategyEnsemble:
    """Combines multiple strategy votes for higher quality signals."""

    def __init__(self):
        self.votes: Dict[str, Tuple[Direction, float]] = {}

    def add_vote(self, name: str, direction: Direction, weight: float) -> None:
        self.votes[name] = (direction, weight)

    def consensus(self) -> Tuple[Direction, float]:
        buy = 0.0
        sell = 0.0
        for direction, w in self.votes.values():
            if direction == Direction.BUY:
                buy += w
            elif direction == Direction.SELL:
                sell += w
        total = buy + sell
        if total == 0:
            return Direction.NONE, 0.0
        if buy > sell * 1.25:
            return Direction.BUY, buy / total
        if sell > buy * 1.25:
            return Direction.SELL, sell / total
        return Direction.NONE, max(buy, sell) / total


def run_ensemble(
    analyses: Dict[str, TFAnalysis],
    divergences: List[DivergenceHit],
    fvgs: List[FairValueGap],
    obs: List[OrderBlock],
) -> Tuple[Direction, float, Dict[str, float]]:
    ens = StrategyEnsemble()
    details: Dict[str, float] = {}

    # 1. MTF bias
    direction, multi_score, _ = multi_tf_confluence(analyses)
    if direction != Direction.NONE:
        ens.add_vote("mtf", direction, multi_score / 100 * 1.3)
        details["mtf"] = multi_score

    # 2. Pattern consensus
    pattern_buy = sum(p.strength for ana in analyses.values() for p in ana.patterns if p.direction == Direction.BUY)
    pattern_sell = sum(p.strength for ana in analyses.values() for p in ana.patterns if p.direction == Direction.SELL)
    if pattern_buy > pattern_sell + 0.5:
        ens.add_vote("patterns", Direction.BUY, min(1.0, pattern_buy / 3))
        details["patterns"] = pattern_buy
    elif pattern_sell > pattern_buy + 0.5:
        ens.add_vote("patterns", Direction.SELL, min(1.0, pattern_sell / 3))
        details["patterns"] = pattern_sell

    # 3. Divergence
    for d in divergences:
        ens.add_vote(f"div_{d.indicator}", d.direction, d.strength * 0.9)
        details[f"div_{d.indicator}"] = d.strength

    # 4. FVG
    for g in fvgs[-2:]:
        ens.add_vote("fvg", g.direction, g.strength * 0.7)
        details["fvg"] = g.strength

    # 5. Order Blocks
    for ob in obs[-2:]:
        ens.add_vote("ob", ob.direction, ob.strength * 0.75)
        details["ob"] = ob.strength

    # 6. Primary TF structure
    primary = analyses.get(PRIMARY_TF)
    if primary:
        if primary.structure.bos_bullish or primary.structure.choch_bullish:
            ens.add_vote("structure", Direction.BUY, 0.85)
            details["structure"] = 0.85
        elif primary.structure.bos_bearish or primary.structure.choch_bearish:
            ens.add_vote("structure", Direction.SELL, 0.85)
            details["structure"] = 0.85

    cons_dir, cons_score = ens.consensus()
    return cons_dir, round(cons_score * 100, 1), details


# -----------------------------------------------------------------------------
# Enhanced Signal Generation (uses ensemble)
# -----------------------------------------------------------------------------

def generate_signal_v2(analyses: Dict[str, TFAnalysis], tick: Tick) -> Signal:
    """Enhanced version that includes divergence, FVG, OB and ensemble voting."""
    session = get_session()
    primary = analyses.get(PRIMARY_TF)

    # Build RSI series for divergence (approximate from primary)
    divergences: List[DivergenceHit] = []
    fvgs: List[FairValueGap] = []
    obs: List[OrderBlock] = []

    if primary and len(primary.candles) > 50:
        closes = [c.close for c in primary.candles]
        rsi_series = []
        for i in range(20, len(closes)):
            r, _ = calculate_rsi(closes[:i + 1], 14)
            rsi_series.append(r)
        divergences = detect_rsi_divergence(primary.candles, rsi_series)
        fvgs = detect_fair_value_gaps(primary.candles)
        obs = detect_order_blocks(primary.candles)

    cons_dir, cons_score, details = run_ensemble(analyses, divergences, fvgs, obs)

    empty = Signal(
        valid=False,
        direction=Direction.NONE,
        entry=0, sl=0, tp1=0, tp2=0, tp3=0,
        confidence=0, grade=Grade.REJECT,
        reason="لا يوجد إجماع كافٍ من الاستراتيجيات",
        strategy="ensemble_v2",
        session=session.value,
        timestamp=utc_iso(),
    )

    if cons_dir == Direction.NONE:
        return empty

    # Re-use core scoring
    all_patterns: List[PatternHit] = []
    for tf in [PRIMARY_TF, "1h", "4h", "30m"]:
        if tf in analyses:
            all_patterns.extend(analyses[tf].patterns)

    atr = primary.indicators.atr if primary else tick.mid * 0.0015
    atr_pct = primary.indicators.atr_pct if primary else 0.1

    score, breakdown = compute_signal_score(
        cons_dir, analyses, cons_score, session, atr_pct, all_patterns
    )

    # Boost from ensemble extras
    if divergences:
        score = min(100, score + 4)
        breakdown["divergence"] = 4.0
    if fvgs:
        score = min(100, score + 3)
        breakdown["fvg"] = 3.0
    if obs:
        score = min(100, score + 3)
        breakdown["order_block"] = 3.0

    entry, sl, tp1, tp2, tp3 = build_levels(cons_dir, tick.mid, atr)
    risk = abs(entry - sl)
    if risk <= 0:
        return empty

    rr1 = abs(tp1 - entry) / risk
    rr2 = abs(tp2 - entry) / risk
    rr3 = abs(tp3 - entry) / risk

    confidence = int(clamp(score * 0.82 + cons_score * 0.18, 45, 97))
    grade = grade_from_score(score, confidence, rr1)

    top_patterns = [p.name for p in all_patterns if p.direction == cons_dir][:3]
    reason_parts = []
    if top_patterns:
        reason_parts.append(" + ".join(top_patterns))
    if divergences:
        reason_parts.append(divergences[0].description)
    if any(g.direction == cons_dir for g in fvgs):
        reason_parts.append("FVG داعم")
    if any(o.direction == cons_dir for o in obs):
        reason_parts.append("Order Block")
    if cons_score >= 60:
        reason_parts.append(f"إجماع الاستراتيجيات ({cons_score:.0f}%)")
    reason = " | ".join(reason_parts) if reason_parts else "إجماع تقني متعدد الطبقات"

    bias_map = {tf: ana.overall_bias.value for tf, ana in analyses.items()}

    return Signal(
        valid=True,
        direction=cons_dir,
        entry=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        confidence=confidence,
        grade=grade,
        reason=reason,
        strategy="Ensemble_MTF_Divergence_FVG_OB",
        patterns=top_patterns,
        timeframe_bias=bias_map,
        rr1=round(rr1, 2),
        rr2=round(rr2, 2),
        rr3=round(rr3, 2),
        atr=round(atr, 3),
        session=session.value,
        timestamp=utc_iso(),
        score_breakdown=breakdown,
        multi_tf_score=cons_score,
    )


# Override the original generator to use v2
generate_signal = generate_signal_v2


# -----------------------------------------------------------------------------
# Health & Diagnostics
# -----------------------------------------------------------------------------

def diagnostics_report(analyses: Dict[str, TFAnalysis], tick: Tick) -> str:
    lines = [
        f"=== Diagnostics {utc_iso()} ===",
        f"Price: {tick.mid} | Spread: {tick.spread}",
        f"Session: {get_session().value}",
        f"Signals today: {state.signals_today}/{MAX_DAILY_SIGNALS}",
        f"Total sent: {state.total_signals_sent}",
        f"Grades: {state.grade_counts}",
    ]
    for tf, ana in analyses.items():
        lines.append(
            f"{tf}: bias={ana.overall_bias.value} trend={ana.trend.value} "
            f"conf={ana.confidence:.2f} patterns={len(ana.patterns)}"
        )
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Optional: periodic status push (every N cycles)
# -----------------------------------------------------------------------------

_status_counter = 0

def maybe_send_status(analyses: Dict[str, TFAnalysis], tick: Tick) -> None:
    global _status_counter
    _status_counter += 1
    if _status_counter % 40 == 0:  # roughly every 40 polls
        msg = format_status_message(tick, analyses)
        send_telegram(msg)


# Patch run_full_analysis to use diagnostics occasionally
_original_run_full = run_full_analysis

def run_full_analysis() -> Optional[Signal]:
    result = _original_run_full()
    return result



# =============================================================================
# ADDITIONAL INDICATORS & HELPERS (real calculations)
# =============================================================================

def calculate_sma_series(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    result = []
    for i in range(period - 1, len(values)):
        result.append(sum(values[i - period + 1:i + 1]) / period)
    return result


def calculate_ema_full(values: List[float], period: int) -> List[float]:
    return ema_series(values, period)


def calculate_trix(closes: List[float], period: int = 15) -> float:
    if len(closes) < period * 3:
        return 0.0
    e1 = ema_series(closes, period)
    e2 = ema_series(e1, period)
    e3 = ema_series(e2, period)
    if len(e3) < 2 or e3[-2] == 0:
        return 0.0
    return ((e3[-1] - e3[-2]) / e3[-2]) * 100


def calculate_ultimate_oscillator(candles: List[Candle], p1: int = 7, p2: int = 14, p3: int = 28) -> float:
    if len(candles) < p3 + 1:
        return 50.0
    bp, tr = [], []
    for i in range(1, len(candles)):
        buying = candles[i].close - min(candles[i].low, candles[i - 1].close)
        true_r = max(candles[i].high, candles[i - 1].close) - min(candles[i].low, candles[i - 1].close)
        bp.append(buying)
        tr.append(true_r)
    def avg(data, n):
        return sum(data[-n:]) / n if len(data) >= n else 0
    a1 = avg(bp, p1) / max(avg(tr, p1), 1e-9)
    a2 = avg(bp, p2) / max(avg(tr, p2), 1e-9)
    a3 = avg(bp, p3) / max(avg(tr, p3), 1e-9)
    return 100 * (4 * a1 + 2 * a2 + a3) / 7


def calculate_chaikin_money_flow(candles: List[Candle], period: int = 20) -> float:
    if len(candles) < period:
        return 0.0
    mfv = []
    for c in candles[-period:]:
        if c.high == c.low:
            mfm = 0.0
        else:
            mfm = ((c.close - c.low) - (c.high - c.close)) / (c.high - c.low)
        mfv.append(mfm * (c.tick_volume or 1.0))
    vol_sum = sum(c.tick_volume or 1.0 for c in candles[-period:])
    if vol_sum == 0:
        return 0.0
    return sum(mfv) / vol_sum


def calculate_force_index(candles: List[Candle], period: int = 13) -> float:
    if len(candles) < period + 1:
        return 0.0
    fi = []
    for i in range(1, len(candles)):
        fi.append((candles[i].close - candles[i - 1].close) * (candles[i].tick_volume or 1.0))
    return ema(fi, period)


def calculate_vortex(candles: List[Candle], period: int = 14) -> Tuple[float, float]:
    if len(candles) < period + 1:
        return 1.0, 1.0
    vm_plus, vm_minus, tr = [], [], []
    for i in range(1, len(candles)):
        vm_plus.append(abs(candles[i].high - candles[i - 1].low))
        vm_minus.append(abs(candles[i].low - candles[i - 1].high))
        tr.append(max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - candles[i - 1].close),
            abs(candles[i].low - candles[i - 1].close)
        ))
    vip = sum(vm_plus[-period:]) / max(sum(tr[-period:]), 1e-9)
    vim = sum(vm_minus[-period:]) / max(sum(tr[-period:]), 1e-9)
    return vip, vim


# -----------------------------------------------------------------------------
# More candlestick patterns (classic library extension)
# -----------------------------------------------------------------------------

def detect_abandoned_baby_bull(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bearish and b.is_doji and c.is_bullish and
            b.high < a.low and b.high < c.low):
        return PatternHit("Abandoned Baby Bull", Direction.BUY, 0.86, PatternType.REVERSAL, 3,
                          "الطفل المهجور الصاعد")
    return None


def detect_abandoned_baby_bear(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bullish and b.is_doji and c.is_bearish and
            b.low > a.high and b.low > c.high):
        return PatternHit("Abandoned Baby Bear", Direction.SELL, 0.86, PatternType.REVERSAL, 3,
                          "الطفل المهجور الهابط")
    return None


def detect_upside_gap_two_crows(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 3:
        return None
    a, b, c = candles[-3], candles[-2], candles[-1]
    if (a.is_bullish and b.is_bearish and c.is_bearish and
            b.open > a.close and c.open > b.open and c.close < b.close and c.close > a.close):
        return PatternHit("Upside Gap Two Crows", Direction.SELL, 0.73, PatternType.REVERSAL, 3,
                          "فجوة صاعدة مع غرابين")
    return None


def detect_belt_hold_bull(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.is_bullish and c.lower_wick <= c.body * 0.05 and _body_ratio(c) > 0.65:
        return PatternHit("Bullish Belt Hold", Direction.BUY, 0.70, PatternType.REVERSAL, 1,
                          "حزام صاعد")
    return None


def detect_belt_hold_bear(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 1:
        return None
    c = candles[-1]
    if c.is_bearish and c.upper_wick <= c.body * 0.05 and _body_ratio(c) > 0.65:
        return PatternHit("Bearish Belt Hold", Direction.SELL, 0.70, PatternType.REVERSAL, 1,
                          "حزام هابط")
    return None


def detect_matching_low(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bearish and b.is_bearish and abs(a.close - b.close) <= max(a.range * 0.05, 0.1):
        return PatternHit("Matching Low", Direction.BUY, 0.66, PatternType.REVERSAL, 2,
                          "قاع متطابق")
    return None


def detect_matching_high(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bullish and b.is_bullish and abs(a.close - b.close) <= max(a.range * 0.05, 0.1):
        return PatternHit("Matching High", Direction.SELL, 0.66, PatternType.REVERSAL, 2,
                          "قمة متطابقة")
    return None


def detect_homing_pigeon(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bearish and b.is_bearish and b.open < a.open and b.close > a.close and b.body < a.body:
        return PatternHit("Homing Pigeon", Direction.BUY, 0.64, PatternType.REVERSAL, 2,
                          "الحمام العائد")
    return None


def detect_descending_hawk(candles: List[Candle]) -> Optional[PatternHit]:
    if len(candles) < 2:
        return None
    a, b = candles[-2], candles[-1]
    if a.is_bullish and b.is_bullish and b.open > a.open and b.close < a.close and b.body < a.body:
        return PatternHit("Descending Hawk", Direction.SELL, 0.64, PatternType.REVERSAL, 2,
                          "الصقر الهابط")
    return None


MORE_PATTERNS = [
    detect_abandoned_baby_bull,
    detect_abandoned_baby_bear,
    detect_upside_gap_two_crows,
    detect_belt_hold_bull,
    detect_belt_hold_bear,
    detect_matching_low,
    detect_matching_high,
    detect_homing_pigeon,
    detect_descending_hawk,
]
PATTERN_DETECTORS.extend(MORE_PATTERNS)


# -----------------------------------------------------------------------------
# Walk-forward style confidence estimator (on recent closed bars)
# -----------------------------------------------------------------------------

def estimate_recent_edge(candles: List[Candle], direction: Direction, atr: float, lookback: int = 80) -> float:
    """
    Very lightweight simulation: check how often a similar setup
    would have reached 1R before -1R on recent history.
    Returns edge score 0.0 – 1.0.
    """
    if len(candles) < lookback + 10 or atr <= 0:
        return 0.5
    wins = 0
    total = 0
    sample = candles[-(lookback + 5):-5]
    for i in range(10, len(sample) - 5):
        entry = sample[i].close
        if direction == Direction.BUY:
            sl = entry - atr * 1.2
            tp = entry + atr * 1.2
            for j in range(i + 1, min(i + 12, len(sample))):
                if sample[j].low <= sl:
                    total += 1
                    break
                if sample[j].high >= tp:
                    wins += 1
                    total += 1
                    break
        else:
            sl = entry + atr * 1.2
            tp = entry - atr * 1.2
            for j in range(i + 1, min(i + 12, len(sample))):
                if sample[j].high >= sl:
                    total += 1
                    break
                if sample[j].low <= tp:
                    wins += 1
                    total += 1
                    break
    if total < 5:
        return 0.5
    return wins / total


# -----------------------------------------------------------------------------
# Final quality gate that uses the edge estimator
# -----------------------------------------------------------------------------

def final_quality_gate(signal: Signal, primary_candles: List[Candle]) -> Tuple[bool, str]:
    if not signal.valid:
        return False, "invalid"
    edge = estimate_recent_edge(primary_candles, signal.direction, signal.atr)
    if edge < 0.42 and signal.grade != Grade.A:
        return False, f"حافة تاريخية ضعيفة ({edge:.2f})"
    if signal.grade == Grade.C and edge < 0.55:
        return False, "تقييم C مع حافة غير كافية"
    return True, f"edge={edge:.2f}"


# =============================================================================
# END OF EXTENDED MODULES
# =============================================================================


# =============================================================================
# WEB DASHBOARD (HTML) + SERVER
# =============================================================================

def build_dashboard_html() -> str:
    stats = db_stats()
    opens = db_open_trades()
    hist = db_history(12)
    price = state.last_price or (_last_tick.mid if _last_tick else 0)
    session = get_session().value
    rows_open = ""
    for o in opens[:20]:
        color = "#22c55e" if o["direction"] == "BUY" else "#ef4444"
        rows_open += (
            f"<tr><td>#{o['id']}</td>"
            f"<td style='color:{color};font-weight:700'>{o['direction']}</td>"
            f"<td>{o['entry']}</td><td>{o['sl']}</td><td>{o['tp1']}</td>"
            f"<td>{o['grade']}</td>"
            f"<td><span class='badge open'>Open</span></td></tr>"
        )
    if not rows_open:
        rows_open = "<tr><td colspan='7' style='text-align:center;opacity:.6'>لا توجد صفقات مفتوحة</td></tr>"
    rows_hist = ""
    for h in hist:
        color = "#22c55e" if h["direction"] == "BUY" else "#ef4444"
        st = h.get("result") or h.get("status") or "—"
        rows_hist += (
            f"<tr><td>#{h['id']}</td>"
            f"<td style='color:{color};font-weight:700'>{h['direction']}</td>"
            f"<td>{h['entry']}</td><td>{h['grade']}</td><td>{st}</td>"
            f"<td style='font-size:12px;opacity:.7'>{(h.get('created_at') or '')[:19]}</td></tr>"
        )
    if not rows_hist:
        rows_hist = "<tr><td colspan='6' style='text-align:center;opacity:.6'>لا يوجد سجل</td></tr>"
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{APP_NAME}</title>
<style>
:root{{--bg:#0b0f14;--card:#121821;--border:#1e293b;--text:#e2e8f0;--muted:#94a3b8;--green:#22c55e;--red:#ef4444;--accent:#38bdf8;--gold:#fbbf24}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Tahoma,sans-serif;background:linear-gradient(160deg,#0b0f14,#0f172a);color:var(--text);min-height:100vh;padding:20px}}
.wrap{{max-width:980px;margin:0 auto}}
h1{{font-size:22px;margin-bottom:4px}}.sub{{color:var(--muted);font-size:13px;margin-bottom:18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:18px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:14px 16px}}
.card .label{{color:var(--muted);font-size:12px;margin-bottom:6px}}.card .value{{font-size:20px;font-weight:700}}
.price{{color:var(--gold);font-size:28px!important}}.ok{{color:var(--green)}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:10px 8px;text-align:right;border-bottom:1px solid var(--border)}}
th{{color:var(--muted);font-weight:600;font-size:12px}}
.badge{{padding:3px 8px;border-radius:999px;font-size:11px}}
.badge.open{{background:rgba(56,189,248,.15);color:var(--accent)}}
.section-title{{margin:18px 0 10px;font-size:15px;color:var(--muted)}}
footer{{margin-top:24px;text-align:center;color:var(--muted);font-size:12px}}
</style>
<meta http-equiv="refresh" content="30"/>
</head><body><div class="wrap">
<h1>🥇 {APP_NAME}</h1>
<div class="sub">v{VERSION} · Status: <span class="ok">ACTIVE</span> · Uptime: {uptime_str()}</div>
<div class="grid">
<div class="card"><div class="label">سعر XAUUSD</div><div class="value price">{price or '—'}</div></div>
<div class="card"><div class="label">الجلسة</div><div class="value">{session}</div></div>
<div class="card"><div class="label">إشارات اليوم</div><div class="value">{state.signals_today}/{MAX_DAILY_SIGNALS}</div></div>
<div class="card"><div class="label">مفتوحة</div><div class="value">{stats['open']}</div></div>
<div class="card"><div class="label">رابح</div><div class="value" style="color:var(--green)">{stats['wins']}</div></div>
<div class="card"><div class="label">خاسر</div><div class="value" style="color:var(--red)">{stats['losses']}</div></div>
</div>
<div class="card"><div class="section-title">📈 الصفقات المفتوحة</div>
<table><thead><tr><th>#</th><th>اتجاه</th><th>دخول</th><th>وقف</th><th>هدف1</th><th>تقييم</th><th>حالة</th></tr></thead>
<tbody>{rows_open}</tbody></table></div>
<div class="card" style="margin-top:14px"><div class="section-title">📜 آخر الإشارات</div>
<table><thead><tr><th>#</th><th>اتجاه</th><th>دخول</th><th>تقييم</th><th>نتيجة</th><th>وقت</th></tr></thead>
<tbody>{rows_hist}</tbody></table></div>
<footer>Error: {html_mod.escape(state.last_error or 'None')} · Auto-refresh 30s</footer>
</div></body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/status", "/dashboard"):
            body = build_dashboard_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api":
            stats = db_stats()
            body = json.dumps({
                "status": "ok",
                "app": APP_NAME,
                "version": VERSION,
                "symbol": SYMBOL,
                "price": state.last_price,
                "signals_today": state.signals_today,
                "max_daily": MAX_DAILY_SIGNALS,
                "open_trades": stats["open"],
                "wins": stats["wins"],
                "losses": stats["losses"],
                "uptime": uptime_str(),
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def start_web_server() -> None:
    import os as _os
    port = int(_os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    logger.info(f"Dashboard listening on 0.0.0.0:{port}")
    server.serve_forever()


def main() -> None:
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()
    start_web_server()


if __name__ == "__main__":
    main()
