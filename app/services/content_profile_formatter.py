async def format_content_profile(content: dict, content_type: str) -> str:
    from app.db.mongo import get_db
    db = get_db()

    poster_tag = ""
    cast_str = ""

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
        
        # Use release_date if available, otherwise fallback to year
        release_date = content.get("release_date")
        year = release_date if release_date else content.get("year")
        
        status = content.get("status")
        genres = content.get("genres", [])
        runtime = content.get("runtime_minutes")
        rating = content.get("rating", {}).get("tmdb")
        description = content.get("plot")

        # Extract cast
        cast = content.get("cast", [])
        if cast:
            actor_names = []
            for c in cast[:5]: # limit to top 5 cast members
                actor_id = c.get("actor_id")
                if actor_id:
                    actor_doc = await db["actors"].find_one({"_id": actor_id})
                    if actor_doc and actor_doc.get("name"):
                        actor_names.append(actor_doc["name"])
            if actor_names:
                cast_str = "\n**Cast**: " + ", ".join(actor_names)

        # Poster tag
        images = content.get("images", {})
        poster_url = images.get("poster")
        if poster_url and content.get("_id"):
            content_id = content["_id"]
            if content_id.startswith("movie_"):
                slug = content_id.replace("movie_", "")
                detail_url = f"/content/movie/{content_id}"
                poster_tag = f"\n\n<POSTER:{poster_url}|{detail_url}>\n*Visit detail page for more details*"

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
        
    if cast_str:
        output += f"\n{cast_str}"
        
    if description:
        import re
        desc_clean = re.sub(r'<[^>]+>', '', description)
        output += f"\n\n{desc_clean}"
        
    if poster_tag:
        output += poster_tag

    return output
