def normalize_keys(keys):
    if isinstance(keys, str):
        return [(keys, 1)]
    if isinstance(keys, tuple) and len(keys) == 2 and isinstance(keys[0], str):
        return [keys]
    if isinstance(keys, list):
        normalized = []
        for k in keys:
            if isinstance(k, str):
                normalized.append((k, 1))
            elif isinstance(k, (list, tuple)) and len(k) == 2:
                normalized.append((k[0], int(k[1])))
            else:
                raise ValueError(f"Invalid key format: {k}")
        return normalized
    raise ValueError(f"Invalid keys format: {keys}")


def generate_index_name(normalized_keys):
    return "_".join(f"{field}_{direction}" for field, direction in normalized_keys)


async def create_index_safely(collection, keys, name=None, **kwargs):
    """
    Safely creates an index on a MongoDB collection. If an index already exists
    with the same name but different options, it drops it and recreates it.
    If it exists with identical options, it skips creation.
    """
    try:
        normalized = normalize_keys(keys)
    except Exception as e:
        print(f"Error normalizing keys {keys}: {e}")
        # Fall back to let MongoDB handle validation
        return await collection.create_index(keys, name=name, **kwargs)

    if not name:
        name = generate_index_name(normalized)

    try:
        existing = await collection.index_information()
    except Exception as e:
        print(f"Could not retrieve index info for {collection.name}: {e}")
        existing = {}

    if name in existing:
        info = existing[name]
        
        # Convert index info keys to list of tuples with int directions
        info_keys = []
        for k in info.get("key", []):
            if len(k) == 2:
                info_keys.append((k[0], int(k[1])))

        keys_match = (info_keys == normalized)

        options_match = True
        # Compare important options that define index specs
        for opt in ["unique", "sparse", "expireAfterSeconds"]:
            expected = kwargs.get(opt)
            actual = info.get(opt)
            # Treat missing or False/None as equivalent
            if not expected:
                expected = None
            if not actual:
                actual = None
            if expected != actual:
                options_match = False
                break

        if keys_match and options_match:
            # Match found! Skip creation to avoid IndexKeySpecsConflict
            return name

        # Specs differ, drop the existing index
        try:
            await collection.drop_index(name)
            print(f"Dropped conflicting index {name} on {collection.name}")
        except Exception as e:
            print(f"Failed to drop index {name} on {collection.name}: {e}")

    # Create the index
    return await collection.create_index(keys, name=name, **kwargs)
