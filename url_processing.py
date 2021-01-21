import re


def find_matches(possible_endpoints, uri):
    for key in possible_endpoints:
        if re.fullmatch(key[1], uri):
            return key


def get_unique_id_from_url(path: str) -> str:
    return path.split("/")[2]
