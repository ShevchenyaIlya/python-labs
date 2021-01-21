import os
from datetime import datetime


def get_single_post(filename: str, unique_id: str) -> str or None:
    if post_exist_in_file(filename, unique_id):
        with open(filename, "r") as file:
            for post in file:
                if unique_id in post:
                    return post

    return None


def get_all_posts(filename: str) -> list:
    return [deserialize_post_data(post) for post in read_all_posts(filename)]


def save_all_posts(filename: str, all_posts: dict):
    with open(filename, "w") as file:
        file.writelines(
            [f"{serialize_post_data(unique_id, post)}{os.linesep}" for unique_id, post in all_posts.items()]
        )


def delete_post(filename: str, unique_id: str) -> bool:
    if post_exist_in_file(filename, unique_id):
        all_posts = read_all_posts(filename)
        with open(filename, "w") as file:
            file.writelines([post for post in all_posts if unique_id not in post])

        return True

    return False


def modify_post(filename: str, unique_id: str, post_data: dict) -> bool:
    if post_exist_in_file(filename, unique_id):
        all_posts = read_all_posts(filename)
        with open(filename, "w") as file:
            file.writelines(
                [f"{serialize_post_data(unique_id, post_data)}{os.linesep}" if unique_id in post else post
                 for post in all_posts]
            )

        return True

    return False


def generate_filename() -> str:
    current_date = datetime.now()
    return f"reddit-{current_date.strftime('%Y%m%d')}.txt"


def file_exist(filename: str) -> bool:
    if os.path.isfile(filename):
        return True

    return False


def create_file(filename: str) -> None:
    with open(filename, "w"):
        pass


def get_line_number(filename: str) -> int:
    with open(filename, "r") as file:
        return len(file.readlines())


def read_all_posts(filename: str) -> list:
    if not file_exist(filename):
        create_file(filename)

    with open(filename, "r") as file:
        return file.readlines()


def save_post_to_file(filename: str, parsed_post_data: str) -> None:
    with open(filename, "a") as file:
        file.write(f"{parsed_post_data}{os.linesep}")


def post_exist_in_file(filename: str, unique_id: str) -> bool:
    if not file_exist(filename):
        create_file(filename)

    with open(filename, "r") as file:
        return unique_id in file.read()


def get_post_information_sequence() -> list:
    return [
        "post_url", "username", "user_karma", "user_cake_day", "post_karma", "comment_karma",
        "post_date", "comments_number", "votes_number", "post_category"
    ]


def serialize_post_data(unique_id: str, parsed_data: dict):
    sequence = get_post_information_sequence()
    output_string = unique_id
    for field in sequence:
        output_string = ";".join([output_string, parsed_data[field]])

    return output_string


def deserialize_post_data(post: str) -> dict:
    sequence = get_post_information_sequence()
    sequence.insert(0, "unique_id")

    post_information = post.rstrip(os.linesep).split(";")
    post = {key: value for key, value in zip(sequence, post_information)}

    return post
