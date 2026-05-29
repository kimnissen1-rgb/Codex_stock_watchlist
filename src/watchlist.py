import argparse
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

import numpy as np
import pandas as pd
import pytz
import yfinance as yf

COPENHAGEN = pytz.timezone("Europe/Copenhagen")


@dataclass
class Candidate:
    ticker: str
    close: float
    change_5d: float
    change_20d: float
    williams_r: float
    volume_ratio: float
    trend_score: int
    score: float
    setup: str
    risk: str
    entry: str
    stop: str
    target: str


def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    highest_high = df["High"].rolling(period).max()
    lowest_low = df["Low"].rolling(period).min()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    return -100 * (highest_high - df["Close"]) / denom


def load_tickers(path: str = "tickers.txt") -> list[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Ticker file not found: {path}")
    tickers = []
    for line in p.read_text().splitlines():
        line = line.strip().upper()
        if line and not line.startswith("#"):
            tickers.append(line)
    return sorted(set(tickers))


def analyze_ticker(ticker: str) -> Candidate | None:
    df = yf.download(ticker, period="6mo", interval="1d", auto_adjust=True, progress=False)
    if df.empty or len(df) < 60:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.dropna()
    df["wr14"] = williams_r(df)
    df["ma20"] = df["Close"].rolling(20).mean()
    df["ma50"] = df["Close"].rolling(50).mean()
    df["vol20"] = df["Volume"].rolling(20).mean()

    last = df.iloc[-1]
    prev5 = df.iloc[-6]
    prev20 = df.iloc[-21]

    close = float(last["Close"])
    change_5d = (close / float(prev5["Close"]) - 1) * 100
    change_20d = (close / float(prev20["Close"]) - 1) * 100
    wr = float(last["wr14"])
    vol_ratio = float(last["Volume"] / last["vol20"]) if last["vol20"] else 0.0

    trend_score = 0
    if close > float(last["ma20"]):
        trend_score += 1
    if close > float(last["ma50"]):
        trend_score += 1
    if float(last["ma20"]) > float(last["ma50"]):
        trend_score += 1

    # Williams %R interpretation:
    # Above -20 is strong/overbought. Below -80 can be oversold/reversal watch.
    momentum_bonus = 0
    setup = "Neutral / afvent"
    if wr > -20 and change_5d > 0:
        momentum_bonus = 2
        setup = "Long-watch: stærkt momentum, vent på pullback eller breakout"
    elif -50 < wr <= -20 and change_5d > 0:
        momentum_bonus = 1
        setup = "Long-watch: konstruktiv trend uden ekstrem overkøbthed"
    elif wr < -80 and change_20d > 0:
        momentum_bonus = 1
        setup = "Reversal-watch: pullback i mulig optrend"
    elif wr < -80:
        momentum_bonus = -1
        setup = "Kun reversal ved tydelig styrke; ellers undgå"

    score = (trend_score * 1.5) + momentum_bonus + min(vol_ratio, 3) + (change_20d / 10) + (change_5d / 8)

    risk = "Middel"
    if abs(change_5d) > 12 or vol_ratio > 2.2:
        risk = "Høj"
    if ticker in {"UMAC", "NBIS", "MSTR", "COIN", "SMCI", "IREN"}:
        risk = "Høj"

    entry = "Over gårsdagens high eller efter pullback til VWAP/20-dages trend"
    stop = "Under seneste højere bund eller 1-2 ATR under entry"
    target = "1,5-2,5x risiko; tag delgevinst ved første stærke spike"

    return Candidate(ticker, close, change_5d, change_20d, wr, vol_ratio, trend_score, score, setup, risk, entry, stop, target)


def build_email(candidates: list[Candidate]) -> tuple[str, str]:
    now = datetime.now(COPENHAGEN)
    subject = f"Daglig aktie-watchlist - {now:%d-%m-%Y}"

    lines = []
    lines.append(f"Hej Kim\n")
    lines.append(f"Her er dagens systematiske aktie-watchlist for {now:%A den %d-%m-%Y kl. %H:%M} dansk tid.\n")
    lines.append("Vigtigt: Dette er ikke finansiel rådgivning. Verificér altid realtidspris, nyheder, spread, volumen, entry og stop-loss i din handelsplatform før handel.\n")
    lines.append("Metode: listen er rangeret efter trend, Williams %R, 5/20-dages momentum og volumen-ratio. ETF'er indgår ikke, medmindre du selv tilføjer dem i tickers.txt.\n")

    for i, c in enumerate(candidates, 1):
        lines.append(f"{i}. {c.ticker}")
        lines.append(f"Kurs: {c.close:.2f} | 5d: {c.change_5d:+.1f}% | 20d: {c.change_20d:+.1f}% | Williams %R: {c.williams_r:.1f} | Volumen-ratio: {c.volume_ratio:.2f}x")
        lines.append(f"Setup: {c.setup}")
        lines.append(f"Risiko: {c.risk}")
        lines.append(f"Entry-idé: {c.entry}")
        lines.append(f"Stop-idé: {c.stop}")
        lines.append(f"Target-idé: {c.target}\n")

    lines.append("Handelsregler:")
    lines.append("- Køb ikke første spike blindt; vent 5-15 minutter efter åbning.")
    lines.append("- Prioritér aktier over VWAP med relativ styrke mod Nasdaq/S&P 500.")
    lines.append("- Brug mindre positioner ved gap-up, earnings og høj headline-risiko.")
    lines.append("- Fastlæg maksimal risiko pr. trade på forhånd.\n")
    lines.append("Mvh\nDin automatiske watchlist")
    return subject, "\n".join(lines)


def send_email(subject: str, body: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ.get("EMAIL_FROM", user)
    recipient = os.environ["EMAIL_TO"]

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def should_run_now(force: bool = False) -> bool:
    if force:
        return True
    now = datetime.now(COPENHAGEN)
    if now.weekday() >= 5:
        return False
    # Accept a window so GitHub Actions delay does not break the job.
    return now.hour == 14 and 0 <= now.minute <= 45


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print email instead of sending it")
    parser.add_argument("--force", action="store_true", help="Run even outside the Copenhagen time window")
    args = parser.parse_args()

    if not should_run_now(force=args.force or args.dry_run):
        print("Outside Copenhagen run window; exiting without sending.")
        return

    candidates = []
    for ticker in load_tickers():
        try:
            c = analyze_ticker(ticker)
            if c:
                candidates.append(c)
        except Exception as exc:
            print(f"Skipping {ticker}: {exc}")

    candidates = sorted(candidates, key=lambda x: x.score, reverse=True)[:10]
    if not candidates:
        raise RuntimeError("No candidates generated")

    subject, body = build_email(candidates)
    if args.dry_run:
        print(subject)
        print("=" * len(subject))
        print(body)
    else:
        send_email(subject, body)
        print(f"Sent: {subject}")


if __name__ == "__main__":
    main()
