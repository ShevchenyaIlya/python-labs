import argparse
import os
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime


class CustomHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path_components = parse_url_path(self.path)
        path_components_len = len(path_components)
        logging.info(f"GET request, Path: {self.path}")

        if 0 < path_components_len <= 2 and path_components[0] == "posts":
            filename = generate_filename()
            if path_components_len == 2:
                unique_id = path_components[1]
                post = get_single_post(filename, unique_id)
                if post is not None:
                    self._set_response(200, "OK")
                    self.wfile.write(json.dumps(deserialize_post_data(post)).encode("utf-8"))
                    return
            else:
                file_content = get_all_posts(filename)
                self._set_response(200, "OK")
                self.wfile.write(json.dumps(file_content).encode("utf-8"))
                return

        self._set_response(404, "Not Found")

    def do_POST(self) -> None:
        path_components = parse_url_path(self.path)
        post_data = self._get_request_body()
        logging.info(f"POST request, Path: {str(self.path)}, Body: {post_data}")

        if len(path_components) == 1 and path_components[0] == "posts":
            filename = generate_filename()
            if not file_exist(filename):
                create_file(filename)
                logging.info(f"File created(name: {filename})")

            unique_id = post_data["unique_id"]
            if not post_exist_in_file(filename, unique_id):
                save_post_to_file(filename, serialize_post_data(unique_id, post_data))
                line_number = get_line_number(filename)
                self._set_response(201, "Created")
                self.wfile.write(json.dumps({unique_id: line_number}).encode("utf-8"))
                return

        self._set_response(200, "OK")

    def do_DELETE(self) -> None:
        logging.info(f"DELETE request, Path: {self.path}")

        path = parse_url_path(self.path)
        if path[0] == "posts" and len(path) == 2:
            unique_id = path[1]
            filename = generate_filename()
            if delete_post(filename, unique_id):
                self._set_response(200, "OK")
                return

        self._set_response(404, "Not Found")

    def do_PUT(self) -> None:
        path_components = parse_url_path(self.path)
        post_data = self._get_request_body()
        logging.info(f"PUT request, Path: {str(self.path)}, Body: {post_data}")

        if path_components[0] == "posts" and len(path_components) == 2:
            unique_id = path_components[1]
            filename = generate_filename()
            if modify_post(filename, unique_id, post_data):
                self._set_response(200, "OK")
                return

        self._set_response(404, "Not Found")

    def _get_request_body(self) -> dict:
        content_length = int(self.headers['Content-Length'])
        return json.loads(self.rfile.read(content_length).decode("utf-8"))

    def _set_response(self, status_code: int, name: str) -> None:
        self.send_response(status_code, name)
        self._set_content_type()

    def _set_content_type(self) -> None:
        self.send_header('Content-Type', 'application/json')
        self.end_headers()


def get_single_post(filename: str, unique_id: str) -> str or None:
    if post_exist_in_file(filename, unique_id):
        with open(filename, "r") as file:
            for post in file:
                if unique_id in post:
                    return post

    return None


def get_all_posts(filename: str) -> list:
    file_content = []
    with open(filename, "r") as file:
        for line in file:
            file_content.append(deserialize_post_data(line))

    return file_content


def delete_post(filename: str, unique_id: str) -> bool:
    if post_exist_in_file(filename, unique_id):
        all_posts = read_all_posts(filename)
        with open(filename, "w") as file:
            for post in all_posts:
                if unique_id not in post:
                    file.write(post)

        return True

    return False


def modify_post(filename: str, unique_id: str, post_data: dict) -> bool:
    if post_exist_in_file(filename, unique_id):
        all_posts = read_all_posts(filename)
        with open(filename, "w") as file:
            for post in all_posts:
                if unique_id in post:
                    file.write(serialize_post_data(unique_id, post_data))
                else:
                    file.write(post)

        return True

    return False


def parse_url_path(path: str) -> list:
    return list(filter(None, path.split("/")))


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
        return sum(1 for _ in file)


def read_all_posts(filename: str) -> list:
    with open(filename, "r") as file:
        all_posts = file.readlines()

    return all_posts


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


def save_post_to_file(filename: str, parsed_post_data: str) -> None:
    with open(filename, "a") as file:
        file.write(f"{parsed_post_data}{os.linesep}")


def post_exist_in_file(filename: str, unique_id: str) -> bool:
    with open(filename, "r") as file:
        if unique_id in file.read():
            return True

    return False


def run_server(port, server_class=ThreadingHTTPServer, handler_class=CustomHTTPRequestHandler):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    try:
        httpd.serve_forever()
        logging.info(f"Start server on port {port}")
    except KeyboardInterrupt as exception:
        logging.error(exception)
    finally:
        httpd.server_close()
        logging.info(f"Server closed on port {port}")


def string_to_logging_level(log_level: str) -> int:
    possible_levels = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING,
                       'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL}

    return possible_levels[log_level]


def parse_command_line_arguments() -> tuple:
    argument_parser = argparse.ArgumentParser(description="Simple http server")
    argument_parser.add_argument("--port", metavar="port", type=int, default=8087)
    argument_parser.add_argument("--log_level", metavar="log_level", type=str, default="CRITICAL",
                                 choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                 help="Minimal logging level('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')")
    args = argument_parser.parse_args()

    return args.port, args.log_level


if __name__ == '__main__':
    port_number, logging_level = parse_command_line_arguments()
    logging.basicConfig(level=string_to_logging_level(logging_level))
    run_server(port_number)
