import argparse
import json
import os
import sys
import urllib.request
from typing import Iterator


class OpenaiAPI:
    def __init__(self, token, model):
        self.token = token
        self.model = model

    def user_query_streamed(self, prompt: str, history=None) -> Iterator[str]:
        data = {
            "model": self.model,
            "messages": [
                *(history or []),
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "stream": True
        }

        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(data).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}"
            }
        )
        buffer = b""
        prefix = "data: "
        with urllib.request.urlopen(request) as fh:
            while response_body := fh.read(100):
                buffer += response_body

                maybe_idx = buffer.find(b"\n")
                if maybe_idx != -1:
                    line = buffer[:maybe_idx].decode()
                    if line.startswith(prefix):
                        data = line[len(prefix):]
                        if data != "[DONE]":
                            content = json.loads(data)
                            choices = content["choices"]
                            if len(choices) > 0:
                                maybe_content = choices[0]["delta"].get("content")
                                if maybe_content is not None:
                                    yield maybe_content

                    buffer = buffer[maybe_idx + 1:]


def main():
    parser = argparse.ArgumentParser(description="Simple CLI to ChatGPT")
    parser.add_argument("--model", help="The model to use, e.g. gpt-4o-mini, gpt-4o", default="gpt-4o-mini")
    parser.add_argument("--system-prompt", help="Will load a system prompt from this file")
    parser.add_argument("--oneshot", help="Does nothing, used to help rlwrap wrapper", action="store_true")
    args = parser.parse_args()

    client = OpenaiAPI(os.environ["OPENAI_KEY"], model=args.model)
    history = []
    if args.system_prompt:
        with open(args.system_prompt) as fh:
            system_prompt = fh.read()
        history.append({
            "role": "system",
            "content": system_prompt
        })

    while True:
        sys.stdout.write(">> ")
        try:
            prompt = input().strip()
        except EOFError:
            break

        if prompt != "":
            prompt_modified = prompt
            result = ""
            for chunk in client.user_query_streamed(prompt_modified, history=history):
                sys.stdout.write(chunk)
                result += chunk
            # So rlwrap doesn't eat the last line
            sys.stdout.write("\n")

            history += [
                {
                    "role": "user",
                    "content": prompt
                },
                {
                    "role": "assistant",
                    "content": result
                },
            ]


if __name__ == "__main__":
    main()
