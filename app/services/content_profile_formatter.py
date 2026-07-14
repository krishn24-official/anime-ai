def format_content_profile(content: dict, content_type: str) -> str:
    if content_type == "anime":
        title = content.get("title", {}).get("english") or content.get("title", {}).get("romaji")
        year = content.get("year")
        status = content.get("status")
        genres = content.get("genres", [])
        total_episodes = content.get("total_episodes")
        rating = content.get("rating", {}).get("anilist")
        description = content.get("description")
    elif content_type == "movie":
        title = content.get("title")
        year = content.get("year")
        status = content.get("status")
        genres = content.get("genres", [])
        runtime = content.get("runtime_minutes")
        rating = content.get("rating", {}).get("tmdb")
        description = content.get("plot")
    elif content_type == "tv_series":
        title = content.get("title")
        year = content.get("year")
        status = content.get("status")
        genres = content.get("genres", [])
        total_seasons = content.get("total_seasons")
        total_episodes = content.get("total_episodes")
        rating = content.get("rating", {}).get("tmdb")
        description = content.get("plot")
    else:
        return "Unknown content type."

    if not title:
        return "Unknown Title"

    first_line = f"**{title}**"
    if year:
        first_line += f" ({year})"

    second_line_parts = []
    if status:
        second_line_parts.append(status)
    if genres:
        second_line_parts.append(", ".join(genres))

    if content_type == "anime":
        if total_episodes:
            second_line_parts.append(f"{total_episodes} episodes")
    elif content_type == "movie":
        if runtime:
            second_line_parts.append(f"{runtime} min")
    elif content_type == "tv_series":
        if total_seasons and total_episodes:
            second_line_parts.append(f"{total_seasons} seasons, {total_episodes} episodes")

    if rating:
        second_line_parts.append(f"Rated {rating}")

    second_line = " • ".join(second_line_parts)

    output = first_line
    if second_line:
        output += f"\n{second_line}"
    if description:
        import re
        desc_clean = re.sub(r'<[^>]+>', '', description)
        output += f"\n\n{desc_clean}"

    return output
