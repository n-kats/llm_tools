import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from utils.arxiv_utils import ArxivRetriver, ArxivSummary, UpdateTimeStopCondition


def ymd_format(s: str):
    assert len(s) == 8  # YYYYMMDD
    y = int(s[:-4])
    m = int(s[-4:-2])
    d = int(s[-2:])
    return datetime(y, m, d, tzinfo=UTC)


def lastweek():
    now = datetime.now(UTC)
    return datetime(now.year, now.month, now.day, tzinfo=UTC) - timedelta(days=7)


def datedir_name(date: datetime):
    date = date.astimezone(UTC)
    return date.strftime("%Y%m%d")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--categories", nargs="+", required=True)
    parser.add_argument("--since", type=ymd_format, default=lastweek())
    parser.add_argument("--output", type=Path, default=Path("./_cache/daily_summary"))
    parser.add_argument("--max_count", type=int, default=100)
    return parser.parse_args()


def main():
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    stop_condition = UpdateTimeStopCondition(args.since)

    for cat in args.categories:

        def dump_summary(summary: ArxivSummary):
            path = args.output / datedir_name(summary.updated) / cat / f"{summary.short_id}.json"
            json_str = summary.model_dump_json()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f_out:
                f_out.write(json_str)

        for summary in ArxivRetriver(
            max_count_per_request=args.max_count,
            interval_sec=3.0,
            stop_condition=stop_condition,
        ).iter_per_category(cat):
            dump_summary(summary)
            print(summary.updated, summary.short_id)


if __name__ == "__main__":
    main()
