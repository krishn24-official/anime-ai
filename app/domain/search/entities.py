from dataclasses import dataclass, field

# Searchable kinds, in the order used to break ties for the "top result"
# (a title is usually what people look for, then people/organizations).
SEARCH_KINDS: tuple[str, ...] = (
    "anime",
    "movies",
    "tv_series",
    "manga",
    "characters",
    "actors",
    "organizations",
)

# Singular content types used elsewhere in the API (ratings, tier lists,
# relationships) -> search kind.
KIND_BY_CONTENT_TYPE: dict[str, str] = {
    "anime": "anime",
    "manga": "manga",
    "movie": "movies",
    "tv_series": "tv_series",
    "character": "characters",
    "actor": "actors",
    "organization": "organizations",
}
CONTENT_TYPE_BY_KIND: dict[str, str] = {v: k for k, v in KIND_BY_CONTENT_TYPE.items()}


@dataclass(frozen=True)
class SearchDocument:
    """One searchable item, as returned by a SearchIndex."""

    kind: str
    id: str
    title: str
    aliases: tuple[str, ...] = ()
    rating: float = 0.0  # 0-10
    popularity: float = 0.0  # e.g. number of votes; 0 when unknown
    image: str | None = None  # poster / profile / logo URL
    # Fields the client displays for this kind (kept opaque to the domain).
    display: dict = field(default_factory=dict, compare=False, hash=False)


@dataclass(frozen=True)
class RankedHit:
    document: SearchDocument
    rank: int  # lower is better; see rules.MatchRank

    @property
    def sort_key(self) -> tuple:
        # Within the same match quality: popular first, then the title closest to
        # the query (shorter), and rating last (a short special can outrate the series).
        d = self.document
        return (self.rank, -d.popularity, len(d.title), -d.rating)


@dataclass(frozen=True)
class SearchResults:
    by_kind: dict[str, list[RankedHit]]
    top: RankedHit | None
