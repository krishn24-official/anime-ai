def format_attribute_response(entity_doc: dict, entity_type: str, attribute_key: str) -> str:
    if entity_type == "character":
        name = entity_doc.get("name", "The character")
        
        if attribute_key == "hair_color":
            val = entity_doc.get("physical", {}).get("hair_color")
            if val:
                return f"{name}'s hair color is {val}."
                
        elif attribute_key == "height":
            val = entity_doc.get("physical", {}).get("height")
            if val:
                return f"{name} is {val} tall."
                
        elif attribute_key == "birthday":
            m = entity_doc.get("birth_month")
            d = entity_doc.get("birth_day")
            if m and d:
                # Basic formatting for month/day
                months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
                if 1 <= m <= 12:
                    return f"{name}'s birthday is {months[m-1]} {d}."
                return f"{name}'s birthday is {m}/{d}."
                
        elif attribute_key == "age":
            # If age isn't strictly stored, we can check description or physical
            val = entity_doc.get("physical", {}).get("age")
            if val:
                return f"{name} is {val} years old."
                
        elif attribute_key == "affiliations":
            val = entity_doc.get("affiliations")
            if val and isinstance(val, list):
                return f"{name}'s affiliations: {', '.join(val)}."
                
        elif attribute_key == "abilities":
            val = entity_doc.get("abilities")
            if val and isinstance(val, list):
                return f"{name}'s abilities: {', '.join(val)}."
                
        elif attribute_key == "description":
            val = entity_doc.get("description")
            if val:
                import re
                val = re.sub(r'<[^>]+>', '', val)
                return f"**{name} Biography:**\n\n{val}"
                
    else:
        # Media (anime, movie, tv_series)
        if entity_type == "anime":
            title = entity_doc.get("title", {}).get("english") or entity_doc.get("title", {}).get("romaji", "The anime")
        else:
            title = entity_doc.get("title", f"The {entity_type.replace('_', ' ')}")
            
        if attribute_key == "director":
            val = entity_doc.get("director")
            if val and isinstance(val, list):
                return f"The director(s) of {title}: {', '.join(val)}."
            elif val and isinstance(val, str):
                return f"The director of {title} is {val}."
                
        elif attribute_key == "writers":
            val = entity_doc.get("writers")
            if val and isinstance(val, list):
                return f"The writers for {title}: {', '.join(val)}."
            elif val and isinstance(val, str):
                return f"The writer for {title} is {val}."
                
        elif attribute_key == "cast":
            val = entity_doc.get("cast")
            if val and isinstance(val, list):
                return f"The cast of {title}: {', '.join(val)}."
                
        elif attribute_key == "description":
            val = entity_doc.get("description") or entity_doc.get("plot")
            if val:
                import re
                val = re.sub(r'<[^>]+>', '', val)
                return f"**{title} Synopsis:**\n\n{val}"

    # Fallback if field is missing or empty
    readable_attr = attribute_key.replace('_', ' ')
    name_display = entity_doc.get("name")
    if not name_display:
        title = entity_doc.get("title")
        if isinstance(title, dict):
            name_display = title.get("english") or title.get("romaji") or "this entity"
        elif isinstance(title, str):
            name_display = title
        else:
            name_display = "this entity"
            
    return f"I don't have any information about the {readable_attr} for {name_display} in my database."
