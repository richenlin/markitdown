"""Centralized configuration for tunable parameters."""

# Knowledge lifecycle
DECAY_DAYS_THRESHOLD = 90        # Days without use before decay starts
DECAY_RATE = 0.1                 # Effectiveness reduction per decay cycle
GC_EFFECTIVENESS_THRESHOLD = 0.1  # Entries below this get garbage collected

# Knowledge retrieval
FUZZY_MATCH_THRESHOLD = 0.6      # Minimum SequenceMatcher ratio for fuzzy match
RELEVANCE_WEIGHTS = {
    "trigger_match": 0.4,
    "effectiveness": 0.3,
    "recency": 0.2,
    "usage": 0.1,
}
RECENCY_DECAY_DAYS = 365.0       # Days over which recency decays to 0
USAGE_NORMALIZATION = 100.0      # Normalize usage_count by this value
TOP_K_RESULTS = 10               # Default number of results returned

# Summarizer
MIN_INPUT_LENGTH = 10            # Minimum text length for single-sentence validation

# Knowledge category to directory mapping (single source of truth)
CATEGORY_DIRS = {
    'experience': 'experiences',
    'tech-stack': 'tech-stacks',
    'scenario': 'scenarios',
    'problem': 'problems',
    'testing': 'testing',
    'pattern': 'patterns',
    'skill': 'skills',
}
VALID_CATEGORIES = list(CATEGORY_DIRS.keys())
