"""
Database layer — SQLite with automatic schema migration.
If the DB already exists from an older version, missing columns are added safely.
"""
import sqlite3
import pandas as pd
from datetime import datetime, date, timezone
from core.config import CONFIG
import os

DB_PATH = os.environ.get(
    "XAUUSD_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), CONFIG["db_path"])
)

# Base CREATE statements (safe — use IF NOT EXISTS)
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT,
    strategy    TEXT,
    direction   TEXT,
    entry       REAL,
    sl          REAL,
    tp          REAL,
    rr          REAL,
    score       REAL,
    regime      TEXT,
    session     TEXT,
    status      TEXT DEFAULT 'OPEN',
    outcome     TEXT,
    pnl_r       REAL,
    lots        REAL,
    risk_usd    REAL,
    notes       TEXT
);
CREATE TABLE IF NOT EXISTS account (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT,
    event       TEXT,
    amount      REAL,
    balance     REAL,
    note        TEXT
);
CREATE TABLE IF NOT EXISTS strategy_stats (
    strategy    TEXT PRIMARY KEY,
    wins        INTEGER DEFAULT 0,
    losses      INTEGER DEFAULT 0,
    consec_loss INTEGER DEFAULT 0,
    sharpe      REAL DEFAULT 0,
    active      INTEGER DEFAULT 1,
    last_update TEXT
);
CREATE TABLE IF NOT EXISTS daily_goal (
    date_str    TEXT PRIMARY KEY,
    target_usd  REAL DEFAULT 20.0,
    achieved    REAL DEFAULT 0.0,
    trades      INTEGER DEFAULT 0
);
"""

# Columns that may be missing in older DB files — added via migration
MIGRATIONS = [
    ("signals", "pnl_usd",    "REAL"),
    ("signals", "close_price","REAL"),
    ("signals", "close_ts",   "TEXT"),
]


class Database:
    def __init__(self, path=None):
        self.path = path or DB_PATH
        self._init()

    def conn(self):
        c = sqlite3.connect(self.path, check_same_thread=False)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init(self):
        """Create tables + run migrations to add any missing columns."""
        with self.conn() as c:
            c.executescript(CREATE_SQL)

        # Migration: add columns that didn't exist in old schema
        with self.conn() as c:
            for table, col, col_type in MIGRATIONS:
                existing = [
                    row[1] for row in
                    c.execute(f"PRAGMA table_info({table})").fetchall()
                ]
                if col not in existing:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

        # Seed account balance if empty
        with self.conn() as c:
            cnt = c.execute("SELECT COUNT(*) FROM account").fetchone()[0]
            if cnt == 0:
                bal = CONFIG["risk"]["account_balance"]
                c.execute(
                    "INSERT INTO account (ts,event,amount,balance,note) VALUES (?,?,?,?,?)",
                    (datetime.now(timezone.utc).isoformat(), "DEPOSIT", bal, bal, "Initial deposit")
                )

    # ── ACCOUNT / BALANCE ─────────────────────────────────────────────────────
    def get_balance(self) -> float:
        with self.conn() as c:
            row = c.execute(
                "SELECT balance FROM account ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return round(float(row[0]), 2) if row else CONFIG["risk"]["account_balance"]

    def add_pnl(self, pnl_usd: float, note: str = ""):
        old_bal = self.get_balance()
        new_bal = old_bal + pnl_usd
        with self.conn() as c:
            c.execute(
                "INSERT INTO account (ts,event,amount,balance,note) VALUES (?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(),
                 "TRADE_WIN" if pnl_usd >= 0 else "TRADE_LOSS",
                 pnl_usd, new_bal, note)
            )
        return round(new_bal, 2)

    def deposit(self, amount: float):
        old_bal = self.get_balance()
        new_bal = old_bal + amount
        with self.conn() as c:
            c.execute(
                "INSERT INTO account (ts,event,amount,balance,note) VALUES (?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), "DEPOSIT", amount, new_bal, "Manual deposit")
            )
        return round(new_bal, 2)

    def get_account_history(self) -> pd.DataFrame:
        with self.conn() as c:
            return pd.read_sql("SELECT * FROM account ORDER BY id ASC", c)

    def monthly_pnl(self) -> pd.DataFrame:
        with self.conn() as c:
            df = pd.read_sql(
                "SELECT ts, amount FROM account "
                "WHERE event IN ('TRADE_WIN','TRADE_LOSS')", c
            )
        if df.empty:
            return df
        df["ts"]    = pd.to_datetime(df["ts"])
        df["month"] = df["ts"].dt.to_period("M").astype(str)
        return df.groupby("month")["amount"].sum().reset_index()

    # ── SIGNALS / TRADES ──────────────────────────────────────────────────────
    def save_signal(self, sig, sizing=None) -> int:
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO signals "
                "(ts,strategy,direction,entry,sl,tp,rr,score,"
                " regime,session,lots,risk_usd,notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sig.ts, sig.strategy, sig.direction,
                 sig.entry, sig.sl, sig.tp, sig.rr, sig.score,
                 sig.regime, sig.session,
                 sizing.get("lots", 0)     if sizing else 0,
                 sizing.get("risk_usd", 0) if sizing else 0,
                 sig.notes)
            )
            return cur.lastrowid

    def close_trade(self, sid: int, close_price: float,
                    outcome: str, pnl_usd: float, pnl_r: float):
        close_ts = datetime.now(timezone.utc).isoformat()
        with self.conn() as c:
            c.execute(
                "UPDATE signals SET status='CLOSED', outcome=?, pnl_r=?, "
                "pnl_usd=?, close_price=?, close_ts=? WHERE id=?",
                (outcome, pnl_r, pnl_usd, close_price, close_ts, sid)
            )
        self.add_pnl(pnl_usd, f"Trade #{sid} {outcome}")
        self._update_daily_goal(pnl_usd)
        return self.get_balance()

    def update_outcome(self, sid: int, outcome: str, pnl_r: float):
        """Legacy compat — no pnl_usd compound here."""
        with self.conn() as c:
            c.execute(
                "UPDATE signals SET status='CLOSED', outcome=?, pnl_r=? WHERE id=?",
                (outcome, pnl_r, sid)
            )

    def auto_close_open_trades(self, current_price: float):
        open_trades = self.get_signals(status="OPEN")
        closed = []
        for _, row in open_trades.iterrows():
            sid  = int(row["id"])
            dire = row["direction"]
            sl   = float(row["sl"])
            tp   = float(row["tp"])
            risk = float(row.get("risk_usd") or 0)

            hit_tp = (dire == "long"  and current_price >= tp) or \
                     (dire == "short" and current_price <= tp)
            hit_sl = (dire == "long"  and current_price <= sl) or \
                     (dire == "short" and current_price >= sl)

            if hit_tp:
                rr      = float(row["rr"])
                pnl_usd = risk * rr
                self.close_trade(sid, current_price, "WIN", pnl_usd, rr)
                closed.append({"id": sid, "outcome": "WIN", "pnl_usd": pnl_usd})
            elif hit_sl:
                self.close_trade(sid, current_price, "LOSS", -risk, -1.0)
                closed.append({"id": sid, "outcome": "LOSS", "pnl_usd": -risk})
        return closed

    # ── DAILY GOAL ────────────────────────────────────────────────────────────
    def _update_daily_goal(self, pnl_usd: float):
        today = date.today().isoformat()
        with self.conn() as c:
            c.execute(
                "INSERT INTO daily_goal (date_str,target_usd,achieved,trades) "
                "VALUES (?,20.0,?,1) ON CONFLICT(date_str) DO UPDATE SET "
                "achieved=achieved+?, trades=trades+1",
                (today, pnl_usd, pnl_usd)
            )

    def get_daily_goal(self, date_str=None) -> dict:
        if date_str is None:
            date_str = date.today().isoformat()
        with self.conn() as c:
            row = c.execute(
                "SELECT target_usd,achieved,trades FROM daily_goal WHERE date_str=?",
                (date_str,)
            ).fetchone()
        if row:
            return {"target": row[0], "achieved": round(row[1], 2),
                    "trades": row[2], "pct": round(row[1] / row[0] * 100, 1)}
        return {"target": 20.0, "achieved": 0.0, "trades": 0, "pct": 0.0}

    # ── QUERIES ───────────────────────────────────────────────────────────────
    def get_signals(self, limit=500, status=None) -> pd.DataFrame:
        with self.conn() as c:
            if status:
                return pd.read_sql(
                    f"SELECT * FROM signals WHERE status=? ORDER BY id DESC LIMIT {limit}",
                    c, params=(status,)
                )
            return pd.read_sql(
                f"SELECT * FROM signals ORDER BY id DESC LIMIT {limit}", c
            )

    def get_open_signals(self) -> pd.DataFrame:
        return self.get_signals(limit=50, status="OPEN")

    def get_stats(self, strategy) -> dict:
        with self.conn() as c:
            row = c.execute(
                "SELECT wins,losses,consec_loss,sharpe,active "
                "FROM strategy_stats WHERE strategy=?",
                (strategy,)
            ).fetchone()
        if row:
            return {"wins": row[0], "losses": row[1], "consec_loss": row[2],
                    "sharpe": row[3], "active": bool(row[4])}
        return {"wins": 0, "losses": 0, "consec_loss": 0, "sharpe": 0, "active": True}

    def save_stats(self, strategy, st):
        with self.conn() as c:
            c.execute(
                "INSERT INTO strategy_stats "
                "(strategy,wins,losses,consec_loss,sharpe,active,last_update) "
                "VALUES (?,?,?,?,?,?,?) ON CONFLICT(strategy) DO UPDATE SET "
                "wins=excluded.wins, losses=excluded.losses, "
                "consec_loss=excluded.consec_loss, sharpe=excluded.sharpe, "
                "active=excluded.active, last_update=excluded.last_update",
                (strategy, st["wins"], st["losses"], st["consec_loss"],
                 st["sharpe"], int(st["active"]), datetime.now(timezone.utc).isoformat())
            )

    def summary_stats(self) -> dict:
        with self.conn() as c:
            total = c.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            open_ = c.execute("SELECT COUNT(*) FROM signals WHERE status='OPEN'").fetchone()[0]
            wins  = c.execute("SELECT COUNT(*) FROM signals WHERE outcome='WIN'").fetchone()[0]
            losses= c.execute("SELECT COUNT(*) FROM signals WHERE outcome='LOSS'").fetchone()[0]
            avg_sc= c.execute("SELECT AVG(score) FROM signals WHERE score>0").fetchone()[0]
            # Use pnl_r (always existed) as fallback if pnl_usd column is new/empty
            try:
                total_pnl = c.execute(
                    "SELECT SUM(pnl_usd) FROM signals WHERE status='CLOSED'"
                ).fetchone()[0]
            except Exception:
                total_pnl = None
            if total_pnl is None:
                try:
                    total_pnl = c.execute(
                        "SELECT SUM(pnl_r) FROM signals WHERE status='CLOSED'"
                    ).fetchone()[0]
                except Exception:
                    total_pnl = 0
        wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
        return {
            "total_signals": total,
            "open_signals":  open_,
            "wins":          wins,
            "losses":        losses,
            "win_rate":      round(wr, 1),
            "avg_score":     round(avg_sc, 2) if avg_sc else 0,
            "total_pnl_usd": round(float(total_pnl), 2) if total_pnl else 0,
        }
