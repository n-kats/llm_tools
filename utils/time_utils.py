from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=+9), "JST")


def jst_now():
    return datetime.now(JST)


def time_cui_representation(t: datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%S")


def time_path_representation(t: datetime) -> str:
    return t.strftime("%Y%m%d_%H%M%S")


def time_json_representation(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.%f%z")


def day_path_representation(t: datetime) -> str:
    return t.strftime("%Y%m%d")

def day_from_path_representation(s: str) -> datetime:
    return datetime.strptime(s, "%Y%m%d")
