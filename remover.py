#!/usr/bin/env python3

import sys
import time
import re

usage = """\
Usage: remover.py [-h] input_file... -- search_file...

Arguments:
    input_file        - files with styles
    search_file       - files to search for style usages

Options:
    -h         - Show this help message\
"""

csi = "\x1B["

max_index_size = 4 * (1024 ** 3)


class CssBlock:
    def __init__(self, rule, content, start, end):
        self.rule = rule
        self.content = content
        self.start = start
        self.end = end
        self.parent = None
        self.children = []

    def is_root(self):
        return self.parent is None

    def is_selector_rule(self):
        return self.rule[0] != '@'

    def add(self, child, end=None):
        child._set_parent(self)
        self.children.append(child)
        if end is not None:
            self.end = end

    def get_normalized_rule(self):
        if not self.is_selector_rule():
            return self.rule.strip(' ')

        if '&' not in self.rule:
            return self.rule.strip(' ')
        elif self.is_root() or not self.parent.is_selector_rule():
            raise Exception('Encountered "&" at the root level rule')

        parent_rule = self.parent.get_normalized_rule()
        return self.rule.replace("&", parent_rule).strip(' ')

    def get_selectors(self):
        if not self.is_selector_rule():
            return None

        return [s for s in self.rule.split(' ') if len(s) > 0]

    def set_content(self, content, end=None):
        self.content = content
        if end is not None:
            self.end = end

    def add_content(self, content, end):
        self.content += content
        if end is not None:
            self.end = end

    def _set_parent(self, parent):
        self.parent = parent

    def __repr__(self):
        return "'{}' ({}:{}) {{...}}".format(self.get_normalized_rule(), self.start, self.end)


def progress(iterable, total=None, show=True):
    if not show:
        for o in iterable:
            yield o
        return

    total = total if total is not None else len(iterable)
    index = 0
    for o in iterable:
        if index > 0:
            sys.stdout.write("{0}0G{0}K".format(csi))
        yield o
        sys.stdout.write("{}/{} [{:.2f}%]".format(index, total, 100 * float(index) / total))
        sys.stdout.flush()
        index += 1

    if index > 0:
        sys.stdout.write("{0}0G{0}K".format(csi))
    sys.stdout.write("{}/{} [{:.2f}%]".format(total, total, 100.0))
    sys.stdout.flush()
    sys.stdout.write("\n")


def find_all_groups(input_str, r, group=1):
    return [m.group(group) for m in re.finditer(r, input_str)]


def finditer(input_str, search, index=0):
    while index < len(input_str):
        try:
            index = input_str.index(sear*selector_rule)
            yield index
        except ValueError:
            break


def find(input_str, search, reverse=False):
    try:
        index = input_str[::(1 if not reverse else -1)].index(search)
        return index if not reverse else len(input_str) - 1 - index
    except ValueError:
        return None


def find_tokens(input_str):
    result = []
    for selector in find_all_groups(input_str, "[\W\s]([\w_-]+[\w\d_-]*)[\W\s]", 1):
        for token in find_all_groups(selector, "([\w_-]+[\w\d_-])", 1):
            result.append(token)

    return result


def parse(input_str):
    prev_index = 0
    blocks = []
    current_block = None
    for match in re.finditer("[\{\}]", input_str):
        index = match.start()
        char = input_str[index]

        if char == '{':
            prev = input_str[prev_index:index]
            prev_end_block_index = find(prev, ';', reverse=True)
            prev_end_line_index = find(prev, '\n', reverse=True)


            prev_end_index = prev_index
            if prev_end_line_index is not None:
                prev_end_index = max(prev_index, prev_index + prev_end_line_index + 1)

            if prev_end_block_index is not None:
                prev_end_index = max(prev_end_index, prev_index + prev_end_block_index + 1)

            parent_content = input_str[prev_index:prev_end_index]
            rule = input_str[prev_end_index:index]
            if current_block is None:
                current_block = CssBlock(rule, "", prev_end_index, index)
                blocks.append(current_block)    # new root
            else:
                current_block.add_content(parent_content, prev_end_index)
                child_block = CssBlock(rule, "", prev_end_index, index)
                current_block.add(child_block, index)
                current_block = child_block
        else:
            content = input_str[prev_index:index]
            current_block.add_content(content, index + 1)
            current_block = current_block.parent

        prev_index = index + 1

    return blocks


def main(input_files, search_files):
    index = set()
    index_size = 0
    print("Building index...")
    for search_file in progress(search_files):
        with open(search_file, 'r') as f:
            tokens = find_tokens(f.read())
            for token in tokens:
                next_index_size = index_size + len(token)
                if next_index_size > max_index_size:
                    raise Exception("Maximum index sizr of {}B exceeded".format(max_index_size))
                index.add(token)
                index_size = next_index_size

    print("Index size: {}, Token count: {}".format(index_size, len(index)))

    print("Removing unused styles...")
    for input_file in progress(input_files):
        with open(input_file, 'r') as f:
            parse(f.read())
            break


def exit_with_help():
    print(usage)
    sys.exit(0)


if __name__ == "__main__":
    args = sys.argv[1:]

    if '--' not in args:
        exit_with_help()

    delimiter = args.index('--')
    input_files = args[:delimiter]
    search_files = args[delimiter+1:]

    if len(input_files) < 1 or len(search_files) < 1:
        exit_with_help()

    main(input_files, search_files)
