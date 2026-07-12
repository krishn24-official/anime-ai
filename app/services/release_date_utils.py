def parse_release_date(day: int | None, month: int | None, year: int | None, precision: str) -> dict:
    if precision not in ("day", "month", "year"):
        raise ValueError("precision must be 'day', 'month', or 'year'")
        
    if precision == "day":
        if day is None or month is None or year is None:
            raise ValueError("day precision requires day, month, and year")
    elif precision == "month":
        if month is None or year is None:
            raise ValueError("month precision requires month and year")
        if day is not None:
            raise ValueError("month precision should not have a day")
    elif precision == "year":
        if year is None:
            raise ValueError("year precision requires year")
        if month is not None or day is not None:
            raise ValueError("year precision should not have month or day")
            
    return {
        "day": day,
        "month": month,
        "year": year,
        "precision": precision
    }
