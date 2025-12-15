# src/topk.py
from collections import Counter
from typing import List

def top_k_frequent(nums: List[int], k: int) -> List[int]:
    """
    BUGGY on purpose:
    - Returns items in arbitrary dict order, not by frequency desc
    - No tie-breaker rule
    - Doesn't trim properly when k > unique count
    """
    counts = Counter(nums)
    # wrong: this returns in arbitrary hash order; not sorted by freq
    result = list(counts.keys())[:k]
    return result