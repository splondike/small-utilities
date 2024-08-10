from typing import Iterator
import os
import json
import sys
import urllib.request


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


model = "gpt-3.5-turbo"
system_prompt = None
oneshot = False
if len(sys.argv) > 1:
    args = sys.argv[1:]
    if args[0] == "-4":
        model = "gpt-4o"
        args = args[1:]

    if len(args) > 0:
        if args[0] == "-oneshot":
            args = args[1:]
            oneshot = True

        if len(args) > 0:
            with open(args[0]) as fh:
                system_prompt = fh.read()

client = OpenaiAPI(os.environ["OPENAI_KEY"], model=model)
history = []
if system_prompt:
    history.append({
        "role": "system",
        "content": system_prompt
    })

if oneshot:
    prompt = sys.stdin.read()
    result = client.user_query(prompt, history=history)
    print(result)
else:
    while True:
        try:
            prompt = input().strip()
        except EOFError:
            print("")
            break

        if prompt != "":
            if prompt.startswith("!"):
                # Replace the last prompt
                history = history[:-2]

            result = ""
            for chunk in client.user_query_streamed(prompt, history=history):
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
