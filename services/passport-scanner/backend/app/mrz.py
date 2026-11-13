import re
from datetime import date

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
WEIGHTS = (7, 3, 1)
LINE_ONE = re.compile(r"P[A-Z<][A-Z<]{3}[A-Z][A-Z<]{38}")
LINE_TWO = re.compile(r"[A-Z0-9][A-Z0-9<]{8}[A-Z0-9<][A-Z<]{3}[0-9<]{6}[A-Z0-9<][MF<][0-9]{6}[A-Z0-9<][A-Z0-9<]{14}[A-Z0-9<]{2}")


def check_digit(value: str) -> str:
    total = sum(
        (0 if character == "<" else ALPHABET.index(character)) * WEIGHTS[index % 3]
        for index, character in enumerate(value)
    )
    return str(total % 10)


def resolve_date(raw: str, minimum_year: int, maximum_year: int, *, latest=None) -> dict:
    candidates = []
    if raw.isascii() and raw.isdigit():
        for year in range(minimum_year, maximum_year + 1):
            if year % 100 != int(raw[:2]):
                continue
            try:
                candidate = date(year, int(raw[2:4]), int(raw[4:6]))
            except ValueError:
                continue
            if latest is None or candidate <= latest:
                candidates.append(candidate.isoformat())

    if "<" in raw:
        status = "unknown"
    elif not candidates:
        status = "unresolved"
    elif len(candidates) > 1:
        status = "ambiguous"
    else:
        status = "inferred"
    return {"raw": raw, "status": status, "candidates": candidates}


def parse_td3(first: str, second: str, *, today: date | None = None) -> dict | None:
    if not LINE_ONE.fullmatch(first) or not LINE_TWO.fullmatch(second):
        return None
    today = today or date.today()

    surname, _, given_names = first[5:].partition("<<")
    checks = {}
    for key, value, observed in (
        ("passport_number", second[:9], second[9]),
        ("date_of_birth", second[13:19], second[19]),
        ("date_of_expiry", second[21:27], second[27]),
        ("optional_data", second[28:42], second[42]),
        ("composite", second[:10] + second[13:20] + second[21:43], second[43]),
    ):
        expected = check_digit(value)
        unused_optional = key == "optional_data" and value == "<" * 14 and observed == "<"
        checks[key] = {
            "status": "PASS" if observed == expected or unused_optional else "FAIL",
            "expected": expected,
            "observed": observed,
        }

    birth = resolve_date(second[13:19], today.year - 125, today.year, latest=today)
    expiry = resolve_date(second[21:27], today.year - 20, today.year + 20)
    dates = {"date_of_birth": birth, "date_of_expiry": expiry}

    errors = [
        {"code": "CHECK_DIGIT_FAILED", "field": key}
        for key, check in checks.items() if check["status"] == "FAIL"
    ]
    return {
        "status": "checksum_failed" if errors else "review_required",
        "data": {
            "passport_number": second[:9].rstrip("<").replace("<", " "),
            "first_name": " ".join(given_names.replace("<", " ").split()),
            "last_name": surname.replace("<", " "),
            "nationality": second[10:13].rstrip("<"),
            "date_of_birth": birth["candidates"][0] if birth["status"] == "inferred" else None,
            "date_of_expiry": expiry["candidates"][0] if expiry["status"] == "inferred" else None,
            "sex": second[20] if second[20] != "<" else None,
            "issuing_country": first[2:5].rstrip("<"),
        },
        "mrz": [first, second],
        "checks": checks,
        "dates": dates,
        "errors": errors,
        "warnings": [
            {"code": "DATE_" + detail["status"].upper(), "field": field}
            for field, detail in dates.items()
        ],
    }
