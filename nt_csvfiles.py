#!/bin/env python
"""
Script for browsing files using nvimtui.

Usage:
    nvimtui -- python -u nt_csvfiles.py filelist.csv
"""


import argparse
import csv
import io
import json
import sys


def emit(action, *args):
    global actions
    actions.append({"action": action, "args": args})


parser = argparse.ArgumentParser(description="CSV file browser")

parser.add_argument(
    "files_list_file",
    help="Path to a csv listing your files"
)
parser.add_argument(
    "files_pattern",
    default="{filename}",
    help="Path to a file given an id. {filename} is substituted with the raw file id. {prefix} is the first two characters if the file id."
)
parser.add_argument(
    "column",
    default=0,
    type=int,
    help="The column of the CSV that contains the filename"
)

args = parser.parse_args()
files_pattern: str = args.files_pattern
catalogue_file: str = args.files_list_file
column: int = args.column

actions = []
while True:
    event = json.loads(sys.stdin.readline().strip())
    match event["action"]:
        case "primary":
            data = next(csv.reader(io.StringIO(event["selection_text"])))
            filename = data[column]
            files_pattern.translate
            filepath = files_pattern.format(
                filename=filename,
                prefix=filename[:2]
            )
            emit("preview_file", filepath)
        case "secondary":
            emit("lua_function", "vim.cmd('NvimTui toggle-watch')")
        case "url":
            match event["url"]:
                case "":
                    emit("setrawurl", catalogue_file)
                    # Allow #/* keys to jump around whole dates/tags
                    emit(
                        "lua_function",
                        "vim.o.iskeyword = '48-57,a-z,A-Z,-,#,_,.'"
                    )

    # Emit actions
    json.dump({"actions": actions}, fp=sys.stdout)
    actions = []
    sys.stdout.write("\n")
