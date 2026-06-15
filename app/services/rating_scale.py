# Custom rating scale used instead of numeric 1-10 ratings.
# Ordered from lowest to highest recommendation.

RATING_SCALE = ["Skip", "Timepass", "Go for it", "Perfection"]

# Internal numeric weight per label, used for averaging/sorting.
RATING_WEIGHTS = {
    "Skip": 1,
    "Timepass": 2,
    "Go for it": 3,
    "Perfection": 4,
}

# Reverse map: weight -> label (for converting averages back to labels)
WEIGHT_TO_LABEL = {v: k for k, v in RATING_WEIGHTS.items()}


def is_valid_rating(value: str) -> bool:
    return value in RATING_SCALE


def rating_to_weight(value: str) -> int:
    return RATING_WEIGHTS[value]


def weight_to_label(weight: float) -> str:
    """Round a weight (e.g. an average) to the nearest valid rating label."""
    nearest = min(WEIGHT_TO_LABEL.keys(), key=lambda w: abs(w - weight))
    return WEIGHT_TO_LABEL[nearest]