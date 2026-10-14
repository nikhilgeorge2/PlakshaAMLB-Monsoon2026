"""
HW 3 Structured Project: a minimal working bidder.  It bids a fixed amount on creative A and learns nothing, so it is a
starting point and a way to see the pipeline run:   python check_submission.py bidder_template.py

Copy it, name the copy with the roll numbers of your team (for example 2301001_2301007.py) and replace the strategy.

Limits (check_submission.py tests them):
- fit(): 60 s CPU.  bid()+update(): 2.5 ms CPU per auction on average, 50 ms hard deadline.
- 1 GB memory.  numpy, pandas, scipy, scikit-learn and the standard library only.  No network, no files other than
  the log you are given.  Fix your random seeds (the same inputs must give the same bids).
- bid() returns (amount >= 0, 'A' | 'B' | 'C'); anything else counts as a bid of 0 for that auction.
- Your bidder is run on several hidden campaigns; each starts with a fresh copy of the bidder as left by fit().
"""

import numpy as np
import pandas as pd


class Bidder:
    def __init__(self, product: dict):
        # product = {'name': 'RunWell Pro', 'category': 'athletic_footwear', 'value': 1400}
        self.product = product

    def fit(self, log: pd.DataFrame) -> None:
        """Called once, with historical_log.csv loaded as a DataFrame.  See the handout for the columns."""
        pass

    def start_campaign(self, budget: float, n_impressions: int) -> None:
        """Called at the start of every campaign: total budget (Rs) and the number of auctions that will arrive."""
        self.budget = budget
        self.n_impressions = n_impressions

    def bid(self, context: dict) -> tuple:
        """One auction.  context holds the ten user/context features plus budget_remaining and impressions_remaining.
        The competing price is not given.  Return (bid, creative)."""
        return 10.0, 'A'

    def update(self, outcome: dict) -> None:
        """Called after every auction.
        Won:  {'won': True, 'price': float, 'clicked': bool, 'converted': bool}
        Lost: {'won': False}
        """
        pass
