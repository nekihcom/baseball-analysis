import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from ama_baseball.fetcher import Fetcher
from ama_baseball.runner import run
from ama_baseball.sheet_store import SheetStore

JST = timezone(timedelta(hours=9), "JST")
DATA_DIR = Path("data")

logger = logging.getLogger("ama_baseball")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ama_baseball", description="teams のチームデータを収集する")
    parser.add_argument("--teams", required=True, help="チームID（カンマ区切りで複数指定可）")
    parser.add_argument("--all-years", action="store_true", help="全チームについて全年度を再取得する")
    args = parser.parse_args(argv)

    _setup_logging()
    teams = parse_teams(args.teams)
    if not teams:
        logger.error("--teams にチームIDを指定してください")
        return 2

    # GitHub Actions では環境変数で渡すため、既に設定済みの値を .env で上書きしない
    load_dotenv(find_dotenv(usecwd=True), override=False)
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    missing = [name for name, value in [("SPREADSHEET_ID", spreadsheet_id), ("GOOGLE_APPLICATION_CREDENTIALS", credentials_path)] if not value]
    if missing:
        logger.error("設定値がありません: %s（.env または環境変数で指定してください）", ", ".join(missing))
        return 2
    if not Path(credentials_path).is_file():
        logger.error("GOOGLE_APPLICATION_CREDENTIALS のファイルが見つかりません")
        return 2

    try:
        store = SheetStore(spreadsheet_id, credentials_path)
    except Exception as e:
        logger.error("スプレッドシートを開けないため中止します: %s: %s", type(e).__name__, e)
        return 1

    return run(teams, args.all_years, store, Fetcher(), DATA_DIR, datetime.now(JST))


def parse_teams(value: str) -> list[str]:
    teams = [t.strip() for t in value.split(",")]
    return list(dict.fromkeys(t for t in teams if t))


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    formatter.converter = lambda t: datetime.fromtimestamp(t, JST).timetuple()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    for noisy in ("urllib3", "google", "gspread"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
