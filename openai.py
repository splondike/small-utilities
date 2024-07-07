import os
import json
import sys
import urllib.request


class OpenaiAPI:
    def __init__(self, token, model):
        self.token = token
        self.model = model

    def user_query(self, prompt: str, history=None) -> str:
        response = self._request({
            "model": self.model,
            "messages": [
                *(history or []),
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        })
        return response["choices"][0]["message"]["content"]

    def _request(self, data):
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(data).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}"
            }
        )
        with urllib.request.urlopen(request) as fh:
            return json.load(fh)


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

            result = client.user_query(prompt, history=history)
            print(result)
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
