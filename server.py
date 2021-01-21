import argparse
import json
import logging
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer, HTTPServer
from typing import Tuple

from cache import Cache
from logging_converter import string_to_logging_level
from url_processing import find_matches, create_url, get_unique_id_from_url


class CustomHTTPRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.possible_endpoints = {
            r"GET /posts/?": self.get_all_posts_request,
            r"GET /posts/.{32}/?": self.get_single_post_request,
            r"POST /posts/?": self.post_request,
            r"DELETE /posts/.{32}/?": self.delete_request,
            r"PUT /posts/.{32}/?": self.put_request
        }
        self.cache = args[-1].cache
        super().__init__(*args, **kwargs)

    def request_handler(self, uri: str):
        return find_matches(self.possible_endpoints, uri)

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

    def do_GET(self) -> None:
        logging.info(f"GET request, Path: {self.path}")
        get_method = self.request_handler(create_url(self.command, self.path))

        if get_method:
            self._set_response(*get_method())
        else:
            self._set_response(404, "Not Found")

    def do_POST(self) -> None:
        post_data = self._get_request_body()
        logging.info(f"POST request, Path: {str(self.path)}, Body: {post_data}")
        post_method = self.request_handler(create_url(self.command, self.path))

        if post_method:
            self._set_response(*post_method(post_data))
        else:
            self._set_response(200, "OK")

    def do_DELETE(self) -> None:
        logging.info(f"DELETE request, Path: {self.path}")
        delete_method = self.request_handler(create_url(self.command, self.path))

        if delete_method:
            self._set_response(*delete_method())
        else:
            self._set_response(404, "Not Found")

    def do_PUT(self) -> None:
        post_data = self._get_request_body()
        logging.info(f"PUT request, Path: {str(self.path)}, Body: {post_data}")
        put_method = self.request_handler(create_url(self.command, self.path))

        if put_method:
            self._set_response(*put_method(post_data))
        else:
            self._set_response(404, "Not Found")

    def get_all_posts_request(self) -> Tuple[int, str, list]:
        file_content = self.cache.get_all_posts()
        return 200, "OK", file_content

    def get_single_post_request(self):
        unique_id = get_unique_id_from_url(self.path)
        post = self.cache.get_post_by_id(unique_id)

        if post is not None:
            return 200, "OK", post
        else:
            return 404, "Not Found"

    def post_request(self, post_data: dict):
        unique_id = post_data["unique_id"]
        if not self.cache.get_post_by_id(unique_id):
            self.cache.append(unique_id, post_data)
            line_number = self.cache.cache_size()
            return 201, "Created", {unique_id: line_number}
        else:
            return 200, "OK"

    def delete_request(self) -> Tuple[int, str]:
        unique_id = get_unique_id_from_url(self.path)
        if self.cache.delete(unique_id):
            return 200, "OK"
        else:
            return 205, "No Content"

    def put_request(self, post_data: dict) -> Tuple[int, str]:
        unique_id = get_unique_id_from_url(self.path)
        if self.cache.get_post_by_id(unique_id):
            self.cache.modify(unique_id, post_data)
            return 200, "OK"
        else:
            return 205, "No Content"


class CachedThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    cache = Cache()


def parse_command_line_arguments() -> tuple:
    argument_parser = argparse.ArgumentParser(description="Simple http server")
    argument_parser.add_argument("--port", metavar="port", type=int, default=8087)
    argument_parser.add_argument("--log_level", metavar="log_level", type=str, default="CRITICAL",
                                 choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                 help="Minimal logging level('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')")
    args = argument_parser.parse_args()

    return args.port, args.log_level


def run_server(port, server_class=CachedThreadingHTTPServer, handler_class=CustomHTTPRequestHandler):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    try:
        logging.info(f"Start server on port {port}")
        httpd.serve_forever()
    except KeyboardInterrupt as exception:
        logging.error(exception)
    finally:
        httpd.server_close()
        httpd.cache.backup_cache()
        logging.info(f"Server closed on port {port}")


if __name__ == '__main__':
    port_number, logging_level = parse_command_line_arguments()
    logging.basicConfig(level=string_to_logging_level(logging_level))
    run_server(port_number)
