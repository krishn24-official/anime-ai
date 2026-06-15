import re


def slugify(text: str) -> str:
    """Convert a title into a lowercase underscore slug.
    e.g. 'Mission: Impossible' -> 'mission_impossible'
         'Loki' -> 'loki'
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)  # remove punctuation
    text = re.sub(r"\s+", "_", text)         # spaces -> underscores
    text = re.sub(r"_+", "_", text)          # collapse repeats
    return text.strip("_")