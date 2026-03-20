import requests
import logging

log = logging.getLogger("XAUUSD.cot")


class COTIntegration:
    CODE = "088691"

    def __init__(self, db=None):
        self.db   = db
        self.bias = "neutral"
        self.data = {}

    def fetch(self):
        try:
            url = (
                "https://publicreporting.cftc.gov/api/explore/dataset/"
                f"com-disagg-reports/records?where=cftc_commodity_code='{self.CODE}'"
                "&order_by=report_date_as_yyyy_mm_dd%20DESC&limit=1&format=json"
            )
            r = requests.get(url, timeout=8)
            if r.status_code == 200 and r.json().get("records"):
                rec = r.json()["records"][0]["fields"]
                d = {
                    "date":       rec.get("report_date_as_yyyy_mm_dd", ""),
                    "comm_long":  float(rec.get("comm_positions_long_all", 0)),
                    "comm_short": float(rec.get("comm_positions_short_all", 0)),
                    "spec_long":  float(rec.get("noncomm_positions_long_all", 0)),
                    "spec_short": float(rec.get("noncomm_positions_short_all", 0)),
                }
                d["comm_net"] = d["comm_long"] - d["comm_short"]
                d["spec_net"] = d["spec_long"]  - d["spec_short"]
                d["bias"]     = self._bias(d)
                self.bias     = d["bias"]
                self.data     = d
                return d
        except Exception as e:
            log.warning("COT fetch failed: %s", e)
        return {}

    def _bias(self, d):
        ce = (d["comm_long"] - d["comm_short"]) / (d["comm_long"] + d["comm_short"] + 1)
        se = (d["spec_long"] - d["spec_short"]) / (d["spec_long"] + d["spec_short"] + 1)
        if ce < -0.3 and se > 0.3:
            return "bearish"
        if ce > 0.1 and se < -0.1:
            return "bullish"
        return "neutral"
