import argparse
import os
import re
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime


class CustomHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        logging.info(f"GET request, Path: {self.path}")
        get_method = self.request_handler(create_uri(self.command, self.path))

        if get_method:
            get_method()
        else:
            self._set_response(404, "Not Found")

    def do_POST(self) -> None:
        post_data = self._get_request_body()
        logging.info(f"POST request, Path: {str(self.path)}, Body: {post_data}")
        post_method = self.request_handler(create_uri(self.command, self.path))

        if post_method:
            post_method(post_data)
        else:
            self._set_response(200, "OK")

    def do_DELETE(self) -> None:
        logging.info(f"DELETE request, Path: {self.path}")
        delete_method = self.request_handler(create_uri(self.command, self.path))

        if delete_method:
            delete_method()
        else:
            self._set_response(404, "Not Found")

    def do_PUT(self) -> None:
        post_data = self._get_request_body()
        logging.info(f"PUT request, Path: {str(self.path)}, Body: {post_data}")
        put_method = self.request_handler(create_uri(self.command, self.path))

        if put_method:
            put_method(post_data)
        else:
            self._set_response(404, "Not Found")

    def get_all_posts_request(self):
        filename = generate_filename()
        file_content = get_all_posts(filename)
        self._set_response(200, "OK")
        self.wfile.write(json.dumps(file_content).encode("utf-8"))

    def get_single_post_request(self):
        filename = generate_filename()
        unique_id = parse_url_path(self.path)[1]
        post = get_single_post(filename, unique_id)

        if post is not None:
            self._set_response(200, "OK")
            self.wfile.write(json.dumps(deserialize_post_data(post)).encode("utf-8"))
            return True
        else:
            self._set_response(404, "Not Found")

    def post_request(self, post_data):
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
        else:
            self._set_response(200, "OK")

    def delete_request(self):
        filename = generate_filename()
        unique_id = parse_url_path(self.path)[1]
        if delete_post(filename, unique_id):
            self._set_response(200, "OK")
        else:
            self._set_response(205, "No Content")

    def put_request(self, post_data, unique_id):
        filename = generate_filename()
        unique_id = parse_url_path(self.path)[1]
        if modify_post(filename, unique_id, post_data):
            self._set_response(200, "OK")
        else:
            self._set_response(205, "No Content")

    def request_handler(self, uri):
        possible_endpoints = {
            r"GET /posts/?": self.get_all_posts_request,
            r"GET /posts/.*/?": self.get_single_post_request,
            r"POST /posts/?": self.post_request,
            r"DELETE /posts/.*/?": self.delete_request,
            r"PUT /posts/.*/?": self.put_request
        }

        return find_matches(possible_endpoints, uri)

    def _get_request_body(self) -> dict:
        content_length = int(self.headers['Content-Length'])
        return json.loads(self.rfile.read(content_length).decode("utf-8"))

    def _set_response(self, status_code: int, name: str) -> None:
        self.send_response(status_code, name)
        self._set_content_type()

    def _set_content_type(self) -> None:
        self.send_header('Content-Type', 'application/json')
        self.end_headers()


def create_uri(command, path):
    return " ".join([command, path])


def find_matches(possible_endpoints, uri):
    for key, value in possible_endpoints.items():
        if re.fullmatch(key, uri):
            return value


def get_single_post(filename: str, unique_id: str) -> str or None:
    if post_exist_in_file(filename, unique_id):
        with open(filename, "r") as file:
            for post in file:
                if unique_id in post:
                    return post

    return None


def get_all_posts(filename: str) -> list:
    return [deserialize_post_data(post) for post in read_all_posts(filename)]


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
        return len(file.readlines())


def read_all_posts(filename: str) -> list:
    with open(filename, "r") as file:
        return file.readlines()


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
        return unique_id in file.read()


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
