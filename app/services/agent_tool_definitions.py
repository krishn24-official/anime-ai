"""
Tool definitions in Gemini function-calling format.
These tell Gemini what tools are available and how to call them.
"""

AGENT_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "get_today_birthdays",
                "description": (
                    "Get a list of anime/manga characters whose birthday is today. "
                    "Use this when the user asks about today's birthdays or which "
                    "characters celebrate their birthday today."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_today_events",
                "description": (
                    "Get today's anime and manga anniversaries — series that started "
                    "airing or publishing on this day in a previous year. Use when "
                    "the user asks about today's events, anniversaries, or 'on this day'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_latest_news",
                "description": (
                    "Get the latest entertainment news articles across all categories. "
                    "Use when the user asks for recent news, trending topics, or "
                    "what's happening in anime/games/movies/TV without specifying a category."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of articles to return (1-20, default 5)",
                        }
                    },
                    "required": [],
                },
            },
            {
                "name": "get_news_by_category",
                "description": (
                    "Get latest news filtered by a specific category. "
                    "Use when the user asks specifically about anime news, game news, "
                    "movie news, or TV series news."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["Anime", "Games", "Movies", "TV Series"],
                            "description": "The news category to filter by.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of articles to return (1-20, default 5)",
                        },
                    },
                    "required": ["category"],
                },
            },
            {
                "name": "search_content",
                "description": (
                    "Search across all content types: characters, anime, manga, "
                    "movies, and TV series. Use when the user asks about a specific "
                    "title, character name, or franchise."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search term (character name, title, franchise, etc.)",
                        }
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_character_info",
                "description": (
                    "Get detailed information about a specific anime/manga character "
                    "including their abilities, relationships, role, and background. "
                    "Use when the user asks detailed questions about a named character. "
                    "If the exact name is not found, this tool will automatically "
                    "suggest similar character names from the database."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The character's name (e.g. 'Naruto', 'Goku', 'Levi')",
                        }
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "get_content_trends",
                "description": (
                    "Get the highest-rated or most-watchlisted content on the platform "
                    "based on real user ratings and watchlist data. "
                    "Use this for questions like: 'what are the highest rated anime?', "
                    "'what's popular?', 'top rated movies', 'what are users watching?', "
                    "'what's trending?', 'most saved TV shows'. "
                    "Supports filtering by content type (anime, manga, movie, tv_series) "
                    "and trend type (ratings or watchlist)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content_type": {
                            "type": "string",
                            "enum": ["anime", "manga", "movie", "tv_series"],
                            "description": (
                                "Filter by content type. Omit to get trends "
                                "across all types."
                            ),
                        },
                        "trend_type": {
                            "type": "string",
                            "enum": ["ratings", "watchlist"],
                            "description": (
                                "'ratings' for top-rated content, "
                                "'watchlist' for most-saved. Default: ratings."
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of results to return (1-20, default 5).",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_organization_info",
                "description": (
                    "Get detailed information about an organization, village, group, "
                    "pirate crew, country, family clan, or military unit in the database. "
                    "Use when the user asks about an organization (e.g. 'Akatsuki', 'Konoha', "
                    "'Straw Hat Pirates') or lists/details of organizations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The organization's name (e.g. 'Akatsuki', 'Konoha', 'Straw Hat Pirates')",
                        }
                    },
                    "required": ["name"],
                },
            },
        ]
    }
]

AGENT_SYSTEM_PROMPT = """You are an intelligent entertainment assistant for an anime, manga, movies, TV series, and organizations platform.

You have access to a real database of characters, anime, manga, movies, TV series, organizations, and the latest entertainment news.

## Tool selection rules (follow strictly):
- "highest rated", "top rated", "best rated", "most popular", "trending", "what's popular" → use get_content_trends
- "latest news", "recent news", "what's happening" → use get_latest_news or get_news_by_category
- "birthday", "born today" → use get_today_birthdays
- "anniversary", "on this day", "today's events" → use get_today_events
- "tell me about [CHARACTER NAME]", "who is [NAME]", "info about [NAME]" → use get_character_info with just the character's name
- "tell me about [ORGANIZATION NAME]", "info about [ORGANIZATION NAME]", "what is [ORGANIZATION NAME]" → use get_organization_info with just the organization's name
- "search for", "find", "is there a" → use search_content
- NEVER pass a full question or sentence to get_character_info or get_organization_info — only pass the name.

## General rules:
1. Use tools to fetch real data — never guess or make up information.
2. Chain multiple tool calls when needed.
3. Synthesize results into a clear, conversational response.
4. If the database has no relevant data, say so honestly.
5. Be concise but informative.
"""