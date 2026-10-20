import re

"""
Clean names by removing 4-digit year disambiguators and HTML artifacts
"""

def clean_name(name):
    """Replace &apos; HTML artifact with ', and remove any 4-digit year disambiguators"""
    name = name.replace("&apos;", "'")
    name = re.sub(r" \d{4}", "", name)
    return name
