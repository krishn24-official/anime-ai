def format_actor_profile(actor: dict, known_for: list[dict]) -> str:
    parts = []
    
    # 1. Name and Birthdate
    name = actor.get("name", "Unknown").strip()
    header_lines = [f"**{name}**"]
    
    birthdate = actor.get("birthdate", "").strip()
    if birthdate:
        parts_arr = birthdate.split("-")
        if len(parts_arr) >= 3:
            try:
                month = int(parts_arr[1])
                day = int(parts_arr[2])
                header_lines.append(f"Born {month}/{day}")
            except ValueError:
                pass
            
    parts.append("\n".join(header_lines))
    
    # 2. Biography
    bio = actor.get("biography", "").strip()
    if bio:
        parts.append(f"**Biography**\n{bio}")
        
    # 3. Known For
    if known_for:
        kf_list = []
        for item in known_for:
            title = (item.get("title") or "").strip()
            year = item.get("year")
            if title:
                if year:
                    kf_list.append(f"{title} ({year})")
                else:
                    kf_list.append(title)
        
        if kf_list:
            parts.append(f"**Known For**\n{', '.join(kf_list)}")
            
    return "\n\n".join(parts)
