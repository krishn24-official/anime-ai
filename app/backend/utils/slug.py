import re

def create_slug(text):

    text = text.lower()

    text = re.sub(r"[^a-z0-9]+", "_", text)

    return text.strip("_")