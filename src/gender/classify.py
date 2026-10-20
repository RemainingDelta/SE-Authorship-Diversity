"""Classify gender based on GENDER_CONFIDENCE_THRESHOLD."""

from shared.config import GENDER_CONFIDENCE_THRESHOLD


def classify_gender(gender, probability):
    """Return a gender classification based on assigned gender and probability.
    If no assigned gender, return unknown, and return unclassified when probability is too low."""
    if gender is None:
        return "unknown"
    if probability >= GENDER_CONFIDENCE_THRESHOLD:
        if gender == "female":
            return "female-presenting"
        if gender == "male":
            return "male-presenting"
    return "unclassified"
