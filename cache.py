from datetime import datetime

from file_management import get_all_posts, save_all_posts, generate_filename


class Cache:
    def __init__(self):
        self.filename = generate_filename()
        self._last_backup = datetime.now()
        self._cache_modified = False
        self._cached_data = {}

        self.load_cache()

    def load_cache(self):
        all_posts = get_all_posts(self.filename)
        for post in all_posts:
            self._cached_data[post["unique_id"]] = post

    def backup_cache(self):
        if self._cache_modified:
            save_all_posts(self.filename, self._cached_data)
            self._last_backup = datetime.now()
            self._cache_modified = False

    def get_post_by_id(self, unique_id):
        return self._cached_data.get(unique_id)

    def get_all_posts(self):
        return list(self._cached_data.values())

    def append(self, unique_id, post):
        self._cached_data[unique_id] = post
        self._cache_modified = True

    def delete(self, unique_id):
        post = self._cached_data.pop(unique_id, None)
        if not post:
            self._cache_modified = True

        return post

    def modify(self, unique_id, post):
        self._cached_data[unique_id] = post
        self._cache_modified = True

    def cache_size(self):
        return len(self._cached_data)


def datetime_difference(first_date, second_date):
    difference = second_date - first_date
    return difference.total_seconds() / 60


if __name__ == '__main__':
    cache = Cache()
