# tests/test_topk.py
import pytest
from src.topk import top_k_frequent

@pytest.mark.parametrize("nums,k,exp", [
    ([1,1,1,2,2,3], 2, [1,2]),               # 1:3x, 2:2x, 3:1x
    ([1,2,2,3,3], 2, [2,3]),                 # tie 2x vs 2x -> smaller value first
    ([-1,-1,-2,-2,-2,3], 1, [-2]),           # negatives okay
    ([7,7,8,8,9], 3, [7,8,9]),               # all unique after top 2
    ([5,6], 5, [5,6]),                       # k > unique -> just all unique, ordered by rule
    ([10,10,10,9,9,8,8,8,8], 2, [8,10]),     # 8:4x, 10:3x, 9:2x
])
def test_topk(nums, k, exp):
    assert top_k_frequent(nums, k) == exp