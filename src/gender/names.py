import re

def clean_name(name):
    name = name.replace("&apos;", "'")
    name = re.sub(r" \d{4}", "", name)
    return name