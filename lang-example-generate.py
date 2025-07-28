"""
Uses an LLM to generate example foreign language/native language pairs for
comprehension practice
"""

import argparse
import hashlib
import json
import pathlib
import random
import select
import subprocess
import sys


DEFAULT_PROMPT = """
You are a foreign language tutor teaching {language}. Pick a common day to day situation.{words_prefix}{words}{words_suffix} Generate a short single line in {language} by itself with no preliminary or following text. Then generate a translation of that into English on its own line. Do not output anything else.
"""


def generate_example(prompt_text: str, words: list) -> dict:
    result = subprocess.run(
        ["python", "llm-chat.py", "--oneshot"],
        capture_output=True,
        input=prompt_text.encode(),
        cwd=pathlib.Path(__file__).parent.resolve(),
    )
    if result.returncode != 0:
        sys.stdout.write(result.stdout.decode())
        sys.stderr.write(result.stderr.decode())
        raise RuntimeError("Error calling llm-chat.py")

    lines = result.stdout.decode().splitlines()
    foreign = lines[0].strip()
    native = lines[1].strip()
    id = hashlib.new("md5", foreign.encode()).hexdigest()
    return {
        "id": id,
        "foreign": foreign,
        "native": native,
        "words": words
    }


def read_words() -> list:
    if select.select([sys.stdin], [], [], 0)[0]:
        # Attempt to inject more variance into LLM by shuffling vocab
        words = [w.strip() for w in sys.stdin.readlines()]
        random.shuffle(words)
        return words
    else:
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Generate language comprehension examples from an LLM"
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=1,
        help="Number of examples to generate"
    )
    parser.add_argument(
        "-p",
        "--prompt",
        type=str,
        default=DEFAULT_PROMPT,
        help=(
            "Prompt for the LLM, accepts {language} and "
            "{words_prefix} and {words} placeholders"
        )
    )
    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default="spanish",
        help="Foreign language for generated examples"
    )

    args = parser.parse_args()
    words_list = read_words()
    words = " ".join(words_list)
    for _ in range(args.count):
        system_prompt = args.prompt.format(
            language=args.language,
            words_prefix="Prefer using these words the student knows: "
            if words
            else "",
            words_suffix="." if words else "",
            words=words
        )
        example = generate_example(system_prompt, words_list)
        print(json.dumps(example))


if __name__ == "__main__":
    main()
