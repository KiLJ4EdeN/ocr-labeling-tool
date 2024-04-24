import os
from os.path import isfile, join
from deep_utils import dump_json, load_json


class Cursor:
    def __init__(self, data_dir, labeled_dir):
        self.data_dir = data_dir
        self.labeled_dir = labeled_dir
        if not os.path.isdir(self.data_dir):
            raise NotADirectoryError(
                f"dataset: {self.data_dir} is not a directory!")
        if not os.path.isdir(self.labeled_dir):
            raise NotADirectoryError(
                f"labeled_dir: {self.labeled_dir} is not a directory!")
        dir_, name = os.path.split(data_dir)
        self.cursor_path = join(
            dir_, f"ocr-labeling-cursor-{name}-cursor.json")
        self._cursor_dict = self._initialize()
        self.image_cache = self._initialize_cache()

    def __str__(self) -> str:
        return str(self._cursor_dict)

    def __getitem__(self, key):
        return self._cursor_dict[key]

    def __len__(self):
        return len(self._cursor_dict['images'])

    def __setitem__(self, key, data):
        self._cursor_dict[key] = data

    def _initialize(self):
        """
        Creates or loads the `cursor.json` file.
        """
        # Fetch or create cursor file
        if not os.path.exists(self.cursor_path):
            cursor = {'file_index_to_read': 1, 'images': {}, "data_dir": self.data_dir,
                      "min_length": "10", "max_length": "15", "use_case": "ocr"}
            img_files = os.listdir(self.data_dir)
            index = 1
            for img_file in img_files:
                if str(img_file).endswith(('.jpg', '.png', '.jpeg')) and isfile(join(self.data_dir, img_file)):
                    cursor['images'][str(index)] = img_file
                index += 1

            dump_json(self.cursor_path, cursor)
        # Open cursor file
        cursor = load_json(self.cursor_path)
        return cursor

    def _initialize_cache(self):
        """
        Initializes image cache.
        """
        labeled_files = os.listdir(self.labeled_dir)
        return set(labeled_files)

    def set_index(self, index: int):
        """
        Sets `file_index_to_read` to a specific index.
        If the given index is out of range, it falls back to 1.
        """
        if index > len(self):
            index = len(self)
        self._cursor_dict['file_index_to_read'] = index
        dump_json(self.cursor_path, self._cursor_dict)

    def increase_index(self):
        self.set_index(self._cursor_dict['file_index_to_read'] + 1)
        dump_json(self.cursor_path, self._cursor_dict)

    def reload_file(self):
        self._cursor_dict = load_json(self.cursor_path)

    def save_lengths(self, min_length, max_length):
        self._cursor_dict['min_length'] = min_length
        self._cursor_dict['max_length'] = max_length
        dump_json(self.cursor_path, self._cursor_dict)

    def set_use_case_plate(self, use_case):
        if use_case:
            self._cursor_dict['use_case'] = 'plate'
        else:
            self._cursor_dict['use_case'] = 'ocr'

        dump_json(self.cursor_path, self._cursor_dict)

    def get_next_image(self):
        """
        Returns the next image file to be labeled,
        while ensuring it is not already labeled and not being accessed by another user.
        """
        index_to_read = self._cursor_dict['file_index_to_read']
        while True:
            if str(index_to_read) not in self._cursor_dict['images']:
                # Reached end of images
                return None
            img_file = self._cursor_dict['images'][str(index_to_read)]
            if img_file not in self.image_cache:
                # Image is not already labeled
                self.image_cache.add(img_file)
                return img_file
            else:
                # Image is already labeled, move to the next one
                index_to_read += 1
                self.set_index(index_to_read)
