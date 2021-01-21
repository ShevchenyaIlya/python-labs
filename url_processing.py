import re


def create_url(command, path):
    return " ".join([command, path])


def find_matches(possible_endpoints, uri):
    for key, value in possible_endpoints.items():
        if re.fullmatch(key, uri):
            return value


def get_unique_id_from_url(path: str) -> str:
    return path.split("/")[2]
