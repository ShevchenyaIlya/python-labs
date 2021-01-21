import argparse
import re
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Tuple

from cache import Cache
from file_management import (get_single_post, get_all_posts, delete_post, modify_post, generate_filename,
                             file_exist, create_file, get_line_number, save_post_to_file,
                             post_exist_in_file, serialize_post_data, deserialize_post_data)


class CustomHTTPRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.possible_endpoints = {
            r"GET /posts/?": get_all_posts_request,
            r"GET /posts/.*/?": get_single_post_request,
            r"POST /posts/?": post_request,
            r"DELETE /posts/.*/?": delete_request,
            r"PUT /posts/.*/?": put_request
        }
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        logging.info(f"GET request, Path: {self.path}")
        get_method = self.request_handler(create_uri(self.command, self.path))

        if get_method:
            self._set_response(*get_method(self.path))
        else:
            self._set_response(404, "Not Found")

    def do_POST(self) -> None:
        post_data = self._get_request_body()
        logging.info(f"POST request, Path: {str(self.path)}, Body: {post_data}")
        post_method = self.request_handler(create_uri(self.command, self.path))

        if post_method:
            self._set_response(*post_method(post_data))
        else:
            self._set_response(200, "OK")

    def do_DELETE(self) -> None:
        logging.info(f"DELETE request, Path: {self.path}")
        delete_method = self.request_handler(create_uri(self.command, self.path))

        if delete_method:
            self._set_response(*delete_method(self.path))
        else:
            self._set_response(404, "Not Found")

    def do_PUT(self) -> None:
        post_data = self._get_request_body()
        logging.info(f"PUT request, Path: {str(self.path)}, Body: {post_data}")
        put_method = self.request_handler(create_uri(self.command, self.path))

        if put_method:
            self._set_response(*put_method(self.path, post_data))
        else:
            self._set_response(404, "Not Found")

    def request_handler(self, uri: str):
        return find_matches(self.possible_endpoints, uri)

    def register_endpoint(self, uri, handler):
        self.possible_endpoints[uri] = handler

    def _get_request_body(self) -> dict:
        content_length = int(self.headers['Content-Length'])
        return json.loads(self.rfile.read(content_length).decode("utf-8"))

    def _set_response(self, status_code: int, name: str, body=None) -> None:
        self.send_response(status_code, name)
        self._set_content_type()
        if body:
            self.wfile.write(json.dumps(body).encode("utf-8"))

    def _set_content_type(self) -> None:
        self.send_header('Content-Type', 'application/json')
        self.end_headers()


def get_all_posts_request(path: str) -> Tuple[int, str, list]:
    filename = generate_filename()
    file_content = get_all_posts(filename)
    return 200, "OK", file_content


def get_single_post_request(path: str):
    filename = generate_filename()
    unique_id = parse_url_path(path)[1]
    post = get_single_post(filename, unique_id)

    if post is not None:
        return 200, "OK", deserialize_post_data(post)
    else:
        return 404, "Not Found"


def post_request(post_data: dict):
    filename = generate_filename()
    if not file_exist(filename):
        create_file(filename)
        logging.info(f"File created(name: {filename})")

    unique_id = post_data["unique_id"]
    if not post_exist_in_file(filename, unique_id):
        save_post_to_file(filename, serialize_post_data(unique_id, post_data))
        line_number = get_line_number(filename)
        return 201, "Created", {unique_id: line_number}
    else:
        return 200, "OK"


def delete_request(path) -> Tuple[int, str]:
    filename = generate_filename()
    unique_id = parse_url_path(path)[1]
    if delete_post(filename, unique_id):
        return 200, "OK"
    else:
        return 205, "No Content"


def put_request(path: str, post_data: dict) -> Tuple[int, str]:
    filename = generate_filename()
    unique_id = parse_url_path(path)[1]
    if modify_post(filename, unique_id, post_data):
        return 200, "OK"
    else:
        return 205, "No Content"


def create_uri(command, path):
    return " ".join([command, path])


def find_matches(possible_endpoints, uri):
    for key, value in possible_endpoints.items():
        if re.fullmatch(key, uri):
            return value


def parse_url_path(path: str) -> list:
    """Return list of path components that were divided by '/'"""
    return list(filter(None, path.split("/")))


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


if __name__ == '__main__':
    port_number, logging_level = parse_command_line_arguments()
    logging.basicConfig(level=string_to_logging_level(logging_level))
    run_server(port_number)
