import pytest
from gender.classify import classify_gender


@pytest.mark.parametrize("gender,probability,expected", [
    # None gender is always unknown, regardless of probability
    (None, 0.99, "unknown"),
    (None, 0.00, "unknown"),
    # At the 0.70 boundary (inclusive)
    ("female", 0.70, "female-presenting"),
    ("male", 0.70, "male-presenting"),
    # Above threshold
    ("female", 0.95, "female-presenting"),
    ("male", 0.80, "male-presenting"),
    # Below threshold
    ("female", 0.69, "unclassified"),
    ("male", 0.00, "unclassified"),
    # Unrecognized gender string at high probability falls through to unclassified
    ("nonbinary", 0.90, "unclassified"),
])
def test_classify_gender(gender, probability, expected):
    assert classify_gender(gender, probability) == expected