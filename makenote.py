import datetime
import os
import sys
import json


def load_config():
    """
    Put config in ~/.config/makenote-config.json like this:
    {
        "search_command": "/usr/bin/nvim",
        "search_basedir": "/path/to/notes",
        "note_types": [
            {
                "name": "documentation",
                "location": "/path/to/notes/docs",
                "fields": "tags:title"
            }
        ]
    }
    """
    filename = os.path.join(
        os.path.expanduser("~"),
        ".config",
        "makenote-config.json"
    )
    if os.path.exists(filename):
        with open(filename) as fh:
            return json.load(fh)
    else:
        return {"note_types": []}


def open_file(note_type, title=""):
    editor = os.environ.get("EDITOR", "")
    if not editor:
        raise RuntimeError("Must set EDITOR environment variable")
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")[2:]
    name = "-".join(
        [note_type["name"][:3]] + (title or ["untitled"])
    ).lower()
    dir = note_type["location"]
    filename = os.path.join(dir, f"{timestamp}-{name}.md")

    contents = ""
    if "fields" in note_type:
        contents = "\n".join([
            "----",
            *[
                f + ": " + " ".join(title) if f == "title" else f + ":"
                for f in note_type["fields"].split(":")
            ],
            "----"
        ])
    with open(filename, "w", encoding="utf8") as fh:
        fh.write(contents)

    os.execl(editor, editor, filename)


def handle_search(config):
    if "search_command" not in config:
        print("Need to specify search_command in config")
        sys.exit(1)

    if "search_basedir" in config:
        os.chdir(config["search_basedir"])

    os.execl(
        config["search_command"],
        config["search_command"],
    )


def handle_chdir(config):
    if "search_basedir" in config:
        os.chdir(config["search_basedir"])

    os.execl(
        os.environ["SHELL"],
        os.environ["SHELL"]
    )


def handle_cwd(config, title):
    cwd = os.getcwd()
    matches = [
        note_type
        for note_type in config["note_types"]
        if note_type["location"] == cwd
    ]
    if len(matches) > 0:
        match = matches[0]
    else:
        match = {
            "name": "generic",
            "location": cwd,
            "fields": "title"
        }
    open_file(match, title)


def handle_named(config, prefix, title):
    matches = [
        note_type
        for note_type in config["note_types"]
        if note_type["name"].startswith(prefix)
    ]
    if len(matches) == 0:
        print(f"No types matching prefix '{prefix}'. Have these:")
        for note_type in config["note_types"]:
            print(f" - {note_type['name']}")
        sys.exit(1)
    elif len(matches) > 1:
        print(f"Multiple types matched prefix '{prefix}':")
        for note_type in matches:
            print(f" - {note_type['name']}")
        sys.exit(1)

    open_file(matches[0], title)


def main(args):
    config = load_config()
    if len(args) == 0:
        handle_search(config)
    elif args[0] == "-":
        handle_chdir(config)
    elif args[0] == ".":
        handle_cwd(config, args[1:])
    else:
        handle_named(config, args[0], args[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
