from datetime import datetime

from file_management import get_all_posts, save_all_posts, generate_filename


class Cache:
    def __init__(self):
        self.filename = generate_filename()
        self.last_backup = datetime.now()
        self._cached_data = {}

        self.load_cache()

    def load_cache(self):
        all_posts = get_all_posts(self.filename)
        for post in all_posts:
            self._cached_data[post["unique_id"]] = post

    def backup_cache(self):
        save_all_posts(self.filename, self._cached_data)
        self.last_backup = datetime.now()

    def get_post_by_id(self, unique_id):
        return self._cached_data.get(unique_id)

    def get_all_posts(self):
        return list(self._cached_data.values())

    def append(self, unique_id, post):
        self._cached_data[unique_id] = post

    def delete(self, unique_id):
        return self._cached_data.pop(unique_id, None)

    def modify(self, unique_id, post):
        self._cached_data[unique_id] = post

    def cache_size(self):
        return len(self._cached_data)


if __name__ == '__main__':
    cache = Cache()
