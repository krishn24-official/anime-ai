def _format_relationship_group(members: list) -> str:
    parts = []
    for m in members:
        target = m.get("target", {})
        name = (target.get("name") or "").strip()
        if not name:
            continue
        rel = m.get("relation_type") or m.get("relation") or ""
        if rel:
            parts.append(f"{name} ({rel})")
        else:
            parts.append(name)
    return ", ".join(parts)

def format_character_profile(character: dict, details: dict) -> str:
    parts = []
    
    # Block 1: Header
    header_lines = []
    native_name = character.get("native_name", "").strip()
    if native_name:
        header_lines.append(f"**{character.get('name', 'Unknown')}** ({native_name})")
    else:
        header_lines.append(f"**{character.get('name', 'Unknown')}**")
        
    stats = []
    if character.get("gender", "").strip():
        stats.append(character.get("gender").strip())
    birth_month = character.get("birth_month")
    birth_day = character.get("birth_day")
    if birth_month and birth_day:
        stats.append(f"Born {birth_month}/{birth_day}")
    if character.get("height", "").strip():
        stats.append(character.get("height").strip())
        
    if stats:
        header_lines.append(" • ".join(stats))
        
    parts.append("\n".join(header_lines))
    
    # Block 2: Meta (Role, Affiliations, Relationships)
    meta_lines = []
    role = character.get("role", "").strip()
    if role:
        meta_lines.append(f"**Role**: {role}")
        
    affiliations = [a.strip() for a in (character.get("affiliations") or []) if str(a).strip()]
    if affiliations:
        meta_lines.append(f"**Affiliations**: {', '.join(affiliations)}")
        
    fam = _format_relationship_group(details.get("family", []))
    if fam: meta_lines.append(f"**Family**: {fam}")
    
    fri = _format_relationship_group(details.get("friends", []))
    if fri: meta_lines.append(f"**Friends**: {fri}")
    
    tea = _format_relationship_group(details.get("team", []))
    if tea: meta_lines.append(f"**Team**: {tea}")
    
    men = _format_relationship_group(details.get("mentors", []))
    if men: meta_lines.append(f"**Mentors**: {men}")
    
    if meta_lines:
        parts.append("\n".join(meta_lines))
        
    # Block 3: Biography
    desc = character.get("description", "").strip()
    if desc:
        parts.append(f"**Biography**\n{desc}")
        
    # Block 4: Profile Image tag
    images = character.get("images", {})
    profile_url = images.get("profile")
    character_id = character.get("_id")
    if profile_url and character_id:
        detail_url = f"/characters/{character_id}"
        poster_tag = f"<POSTER:{profile_url}|{detail_url}>\n*Visit profile page for more details*"
        parts.append(poster_tag)
        
    return "\n\n".join(parts)
