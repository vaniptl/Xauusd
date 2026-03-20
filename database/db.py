import sqlite3
import pandas as pd
from datetime import datetime
from core.config import CONFIG

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
CREATE TABLE IF NOT EXISTS strategy_stats (
    strategy    TEXT PRIMARY KEY,
    wins        INTEGER DEFAULT 0,
    losses      INTEGER DEFAULT 0,
    consec_loss INTEGER DEFAULT 0,
    sharpe      REAL DEFAULT 0,
    active      INTEGER DEFAULT 1,
    last_update TEXT
);
CREATE TABLE IF NOT EXISTS wfo_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT,
    strategy    TEXT,
    params      TEXT,
    is_sharpe   REAL,
    oos_sharpe  REAL,
    is_winrate  REAL,
    oos_winrate REAL
);
CREATE TABLE IF NOT EXISTS cot_data (
    date        TEXT PRIMARY KEY,
    comm_long   REAL,
    comm_short  REAL,
    spec_long   REAL,
    spec_short  REAL,
    bias        TEXT
);
"""


class Database:
    def __init__(self, path=None):
        self.path = path or CONFIG["db_path"]
        self._init()

    def conn(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self.conn() as c:
            c.executescript(CREATE_SQL)

    def save_signal(self, sig, sizing=None):
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO signals "
                "(ts,strategy,direction,entry,sl,tp,rr,score,regime,session,lots,risk_usd,notes)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sig.ts, sig.strategy, sig.direction,
                    sig.entry, sig.sl, sig.tp, sig.rr, sig.score,
                    sig.regime, sig.session,
                    sizing.get("lots", 0) if sizing else 0,
                    sizing.get("risk_usd", 0) if sizing else 0,
                    sig.notes,
                )
            )
            return cur.lastrowid

    def update_outcome(self, sid, outcome, pnl_r):
        with self.conn() as c:
            c.execute(
                "UPDATE signals SET status='CLOSED', outcome=?, pnl_r=? WHERE id=?",
                (outcome, pnl_r, sid)
            )

    def get_stats(self, strategy):
        with self.conn() as c:
            row = c.execute(
                "SELECT wins,losses,consec_loss,sharpe,active FROM strategy_stats WHERE strategy=?",
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
                "(strategy,wins,losses,consec_loss,sharpe,active,last_update)"
                " VALUES (?,?,?,?,?,?,?)"
                " ON CONFLICT(strategy) DO UPDATE SET"
                "  wins=excluded.wins, losses=excluded.losses,"
                "  consec_loss=excluded.consec_loss, sharpe=excluded.sharpe,"
                "  active=excluded.active, last_update=excluded.last_update",
                (strategy, st["wins"], st["losses"], st["consec_loss"],
                 st["sharpe"], int(st["active"]),
                 datetime.utcnow().isoformat())
            )

    def get_signals(self, limit=200, status=None):
        with self.conn() as c:
            if status:
                return pd.read_sql(
                    f"SELECT * FROM signals WHERE status=? ORDER BY id DESC LIMIT {limit}",
                    c, params=(status,)
                )
            return pd.read_sql(
                f"SELECT * FROM signals ORDER BY id DESC LIMIT {limit}", c
            )

    def get_daily_signals(self, date_str):
        """Get all signals for a specific date."""
        with self.conn() as c:
            return pd.read_sql(
                "SELECT * FROM signals WHERE ts LIKE ? ORDER BY id DESC",
                c, params=(f"{date_str}%",)
            )

    def get_open_signals(self):
        return self.get_signals(limit=50, status="OPEN")

    def save_wfo(self, strategy, params_str, is_sh, oos_sh, is_wr, oos_wr):
        with self.conn() as c:
            c.execute(
                "INSERT INTO wfo_runs "
                "(ts,strategy,params,is_sharpe,oos_sharpe,is_winrate,oos_winrate)"
                " VALUES (?,?,?,?,?,?,?)",
                (datetime.utcnow().isoformat(), strategy, params_str,
                 is_sh, oos_sh, is_wr, oos_wr)
            )

    def get_wfo_history(self, limit=20):
        with self.conn() as c:
            return pd.read_sql(
                f"SELECT * FROM wfo_runs ORDER BY id DESC LIMIT {limit}", c
            )

    def summary_stats(self):
        """Return quick summary statistics."""
        with self.conn() as c:
            total = c.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            open_ = c.execute("SELECT COUNT(*) FROM signals WHERE status='OPEN'").fetchone()[0]
            wins  = c.execute("SELECT COUNT(*) FROM signals WHERE outcome='WIN'").fetchone()[0]
            losses= c.execute("SELECT COUNT(*) FROM signals WHERE outcome='LOSS'").fetchone()[0]
            avg_score = c.execute("SELECT AVG(score) FROM signals WHERE score > 0").fetchone()[0]
            total_pnl = c.execute("SELECT SUM(pnl_r) FROM signals WHERE status='CLOSED'").fetchone()[0]
        wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
        return {
            "total_signals": total,
            "open_signals":  open_,
            "wins":          wins,
            "losses":        losses,
            "win_rate":      round(wr, 1),
            "avg_score":     round(avg_score, 2) if avg_score else 0,
            "total_pnl_r":   round(total_pnl, 2) if total_pnl else 0,
        }
