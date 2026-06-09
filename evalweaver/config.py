"""Configuration loading and pipeline defaults."""

import random
import yaml
from pathlib import Path


# Pipeline defaults
DEFAULTS = {
    "goal": "persuasive",
    "raw_text": "EvalWeaver lets anyone create, use, and monetize AI improvers for subjective goals like make this more persuasive.",
    "seed": 7,
    "n_rounds": 2,
    "n_init_scorers": 8,
    "n_repair_scorers": 6,
    "n_init_pairs": 24,
    "n_repair_pairs": 12,
    "test_fraction": 0.33,
    "n_candidates": 4,
    "min_init_heldout": 8,
    "min_r1_heldout": 15,
}


def load_config(path=None) -> dict:
    """Load config from YAML file, merging with defaults."""
    config = dict(DEFAULTS)
    if path is not None:
        p = Path(path)
        if p.exists():
            with open(p) as f:
                overrides = yaml.safe_load(f) or {}
            config.update(overrides)
    return config


def seeded_shuffle(lst: list, seed: int) -> list:
    """Return a shuffled copy of lst using the given seed."""
    r = random.Random(seed)
    lst2 = lst[:]
    r.shuffle(lst2)
    return lst2
