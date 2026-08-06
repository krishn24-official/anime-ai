def format_date(date_data):
    """
    Format a FuzzyDate dict from AniList to a string (YYYY-MM-DD, YYYY-MM, or YYYY).
    Handles missing month or day gracefully.
    """
    if not date_data or not date_data.get("year"):
        return None

    year = date_data.get("year")
    month = date_data.get("month")
    day = date_data.get("day")

    if month and day:
        return f"{year}-{month:02d}-{day:02d}"
    elif month:
        return f"{year}-{month:02d}"
    else:
        return f"{year}"
