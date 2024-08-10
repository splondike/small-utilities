import argparse
import json
import os
import sys
import urllib.request
from typing import Optional, Iterator, Tuple


class OpenaiAPI:
    def __init__(self, token, model):
        self.token = token
        self.model = model

    def user_query_streamed(self, messages: list) -> Iterator[str]:
        data = {
            "model": self.model,
            "messages": messages,
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


class ChatContext():
    """
    Stores the current state of the chat
    """

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"

    def __init__(self):
        self.history = []
        self.files = []

    def add_history(self, role: str, content: str, item_id: Optional[str]=None):
        """
        Adds the given item to the chat history.
        """
        self.history.append({
            "role": role,
            "content": content,
            "item_id": item_id
        })

    def add_file(self, filename: str) -> bool:
        """
        Adds the given file to the chat context
        """
        try:
            with open(filename) as fh:
                self.files.append({
                    "filename": filename,
                    "content": fh.read(),
                })

                return True
        except FileNotFoundError:
            return False

    def build_messages(self, user_message: str):
        """
        Converts this context into something suitable for the OpenAI API.
        Takes the latest user_message. We're going to modify that to add
        any attached files.
        """

        if len(self.files) > 0:
            files_part = "\n".join([
                f"<FILENAME>{file['filename']}</FILENAME><FILECONTENT>{file['content']}</FILECONTENT>"
                for file in self.files
            ])
            message = f"Consider the following files:\n\n{files_part}\n\nMy question is this: {user_message}"
        else:
            message = user_message

        return [
            {
                "role": item["role"],
                "content": item["content"]
            }
            for item in self.history
        ] + [
            {
                "role": self.ROLE_USER,
                "content": message
            }
        ]


def process_prompt(context: ChatContext, prompt: str) -> Tuple[str, str]:
    bits = prompt.split(" ", maxsplit=1)
    command = bits[0] if len(bits) == 2 and bits[0].startswith("/") else ""
    rest = bits[1] if len(bits) == 2 and bits[0].startswith("/") else prompt

    if command == "/add":
        result = context.add_file(rest)
        if result:
            return "", f"Added file {rest}"
        else:
            return "", f"Failed to add file {rest}"
    elif command == "/remove":
        found = False
        new_files = []
        for idx, file in enumerate(context.files):
            if str(idx) != rest and file["filename"] != rest:
                new_files.append(file)
            else:
                found = True

        context.files = new_files
        return "", "Removed file" if found else "Didn't find file"
    elif command == "/remove-all":
        context.files = []
        return "", "Removed all files"
    elif command == "":
        return prompt, ""


def main():
    parser = argparse.ArgumentParser(description="Simple CLI to ChatGPT")
    parser.add_argument("--model", help="The model to use, e.g. gpt-4o-mini, gpt-4o", default="gpt-4o-mini")
    parser.add_argument("--system-prompt", help="Will load a system prompt from this file")
    parser.add_argument("--oneshot", help="Does nothing, used to help rlwrap wrapper", action="store_true")
    args = parser.parse_args()

    client = OpenaiAPI(os.environ["OPENAI_KEY"], model=args.model)
    context = ChatContext()
    if args.system_prompt:
        with open(args.system_prompt) as fh:
            system_prompt = fh.read()
        context.add_history(context.ROLE_SYSTEM, system_prompt)

    response_counter = 0
    while True:
        response_id = f"r{response_counter:02}"
        files = ""
        if len(context.files) > 0:
            files = " " + " ".join([
                file["filename"]
                for file in context.files
            ])
        sys.stdout.write(f"{response_id}{files}>> ")
        try:
            prompt = input().strip()
        except EOFError:
            break

        prompt_modified, info_message = process_prompt(context, prompt)
        if info_message != "":
            sys.stdout.write(info_message + "\n")
        elif prompt_modified != "":
            result = ""
            for chunk in client.user_query_streamed(context.build_messages(prompt_modified)):
                sys.stdout.write(chunk)
                result += chunk
            # Put the prompt on its own line.
            sys.stdout.write("\n")

            context.add_history(context.ROLE_USER, prompt)
            context.add_history(context.ROLE_ASSISTANT, result, item_id=response_id)
            response_counter += 1

if __name__ == "__main__":
    main()
