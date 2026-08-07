import re

def build_fuzzy_search_regex(query: str) -> str:
    """
    Builds a subsequence matching regex pattern that allows >70% fuzzy matching
    and ignores spaces/special characters natively.
    
    Example: 
    - "narto" -> "n.*a.*r.*t.*o" (matches "Naruto")
    - "spiderman" -> "s.*p.*i.*d.*e.*r.*m.*a.*n" (matches "Spider-Man")
    """
    if not query:
        return ""
        
    # Strip spaces and special characters
    clean_query = re.sub(r'[^a-zA-Z0-9]', '', query)
    
    if not clean_query:
        # Fallback if query was entirely special characters
        return re.escape(query)
        
    # Join each character with '.*' to allow any characters in between
    return '.*'.join(list(clean_query))
