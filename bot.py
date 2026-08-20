import csv
import os
import time
import requests
from datetime import datetime, timezone

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

# =========================
# STRATEGY SETTINGS
# =========================

CHECK_EVERY_SECONDS = 5
MAX_MINUTES_REMAINING = 3

UP_MIN = 0.75
UP_MAX = 0.90

DOWN_MIN = 0.10
DOWN_MAX = 0.20

TRADE_LOG = "paper_trades.csv"

# Prevent duplicate paper trades during this run
acted_contracts = set()


# =========================
# CSV SETUP
# =========================

def setup_log():

    if os.path.exists(TRADE_LOG):
        return

    with open(
        TRADE_LOG,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "entry_time",
            "series",
            "ticker",
            "side",
            "entry_price",
            "minutes_remaining",
            "close_time",
            "result",
            "payout",
            "profit_loss",
        ])


# =========================
# GET 15-MINUTE SERIES
# =========================

def get_15m_series():

    response = requests.get(
        f"{BASE_URL}/series",
        params={"limit": 1000},
        timeout=10,
    )

    response.raise_for_status()

    series = response.json().get("series", [])

    return [
        item
        for item in series
        if "15m" in str(
            item.get("ticker", "")
        ).lower()
    ]


# =========================
# GET MARKETS
# =========================

def get_markets(series_ticker):

    response = requests.get(
        f"{BASE_URL}/markets",
        params={
            "series_ticker": series_ticker,
            "status": "open",
            "limit": 100,
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json().get("markets", [])


# =========================
# TIME REMAINING
# =========================

def get_minutes_remaining(close_time):

    if not close_time:
        return None

    try:

        close = datetime.fromisoformat(
            close_time.replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        return (
            close - now
        ).total_seconds() / 60

    except Exception:

        return None


# =========================
# SAFE PRICE CONVERSION
# =========================

def convert_price(value):

    if value is None:
        return None

    try:
        return float(value)

    except (ValueError, TypeError):

        return None


# =========================
# RECORD PAPER TRADE
# =========================

def record_trade(
    series,
    ticker,
    side,
    price,
    remaining,
    close_time,
):

    entry_time = datetime.now(
        timezone.utc
    ).isoformat()

    with open(
        TRADE_LOG,
        "a",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            entry_time,
            series,
            ticker,
            side,
            f"{price:.4f}",
            f"{remaining:.4f}",
            close_time,
            "PENDING",
            "",
            "",
        ])


# =========================
# SCAN
# =========================

def scan():

    series = get_15m_series()

    active_markets = 0
    qualifying = 0

    for item in series:

        series_ticker = item.get("ticker")

        try:

            markets = get_markets(
                series_ticker
            )

        except Exception as error:

            print(
                f"Error getting "
                f"{series_ticker}: {error}"
            )

            continue

        for market in markets:

            active_markets += 1

            ticker = market.get("ticker")

            if not ticker:
                continue

            # Already triggered
            if ticker in acted_contracts:
                continue

            remaining = get_minutes_remaining(
                market.get("close_time")
            )

            if remaining is None:
                continue

            if remaining <= 0:
                continue

            if remaining > MAX_MINUTES_REMAINING:
                continue

            yes_ask = convert_price(
                market.get(
                    "yes_ask_dollars"
                )
            )

            no_ask = convert_price(
                market.get(
                    "no_ask_dollars"
                )
            )

            # =========================
            # UP FIRST
            # =========================

            if (
                yes_ask is not None
                and UP_MIN <= yes_ask <= UP_MAX
            ):

                acted_contracts.add(
                    ticker
                )

                qualifying += 1

                record_trade(
                    series_ticker,
                    ticker,
                    "UP",
                    yes_ask,
                    remaining,
                    market.get(
                        "close_time"
                    ),
                )

                print()
                print(
                    "================================"
                )
                print(
                    "PAPER TRADE — UP"
                )
                print(
                    "================================"
                )
                print(
                    "Series:",
                    series_ticker
                )
                print(
                    "Ticker:",
                    ticker
                )
                print(
                    "Price:",
                    f"${yes_ask:.2f}"
                )
                print(
                    "Time remaining:",
                    f"{remaining:.2f} minutes"
                )
                print(
                    "Action: WOULD BUY UP"
                )
                print(
                    "Logged to:",
                    TRADE_LOG
                )
                print(
                    "NO ORDER WAS PLACED"
                )
                print()

                continue

            # =========================
            # DOWN
            # =========================

            if (
                no_ask is not None
                and DOWN_MIN <= no_ask <= DOWN_MAX
            ):

                acted_contracts.add(
                    ticker
                )

                qualifying += 1

                record_trade(
                    series_ticker,
                    ticker,
                    "DOWN",
                    no_ask,
                    remaining,
                    market.get(
                        "close_time"
                    ),
                )

                print()
                print(
                    "================================"
                )
                print(
                    "PAPER TRADE — DOWN"
                )
                print(
                    "================================"
                )
                print(
                    "Series:",
                    series_ticker
                )
                print(
                    "Ticker:",
                    ticker
                )
                print(
                    "Price:",
                    f"${no_ask:.2f}"
                )
                print(
                    "Time remaining:",
                    f"{remaining:.2f} minutes"
                )
                print(
                    "Action: WOULD BUY DOWN"
                )
                print(
                    "Logged to:",
                    TRADE_LOG
                )
                print(
                    "NO ORDER WAS PLACED"
                )
                print()

    return (
        len(series),
        active_markets,
        qualifying,
    )


# =========================
# MAIN
# =========================

def main():

    setup_log()

    print()
    print(
        "======================================"
    )
    print(
        " KALSHI 15-MINUTE PAPER TRADING BOT"
    )
    print(
        "======================================"
    )
    print()

    print(
        f"UP range: "
        f"${UP_MIN:.2f} - ${UP_MAX:.2f}"
    )

    print(
        f"DOWN range: "
        f"${DOWN_MIN:.2f} - ${DOWN_MAX:.2f}"
    )

    print(
        f"Entry window: "
        f"{MAX_MINUTES_REMAINING} minutes"
    )

    print(
        f"Scan interval: "
        f"{CHECK_EVERY_SECONDS} seconds"
    )

    print()

    print(
        "PAPER TRADING ONLY"
    )

    print(
        "NO ORDERS WILL BE PLACED."
    )

    print()

    scan_number = 0

    while True:

        scan_number += 1

        try:

            (
                series_count,
                market_count,
                qualifying,
            ) = scan()

            current_time = datetime.now().strftime(
                "%H:%M:%S"
            )

            print(
                f"[{current_time}] "
                f"Scan #{scan_number} | "
                f"{series_count} series | "
                f"{market_count} markets | "
                f"Qualifying: {qualifying}"
            )

        except KeyboardInterrupt:

            print()
            print(
                "Scanner stopped."
            )

            break

        except Exception as error:

            print()
            print(
                "SCANNER ERROR:",
                error
            )
            print(
                "Continuing..."
            )
            print()

        time.sleep(
            CHECK_EVERY_SECONDS
        )


if __name__ == "__main__":
    main()