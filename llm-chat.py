import argparse
import datetime
import json
import os
import select
import subprocess
import sys
import time
import urllib.request
from typing import Iterator, Tuple


class AnthropicAPI:
    def __init__(self, token, model):
        self.token = token
        self.model = model

    def user_query_streamed(self, messages: list) -> Iterator[str]:
        # Convert OpenAI message format to Anthropic format
        system = ""
        for message in messages:
            if message["role"] == ChatContext.ROLE_SYSTEM:
                system = message["content"]

        data = {
            "model": self.model,
            "messages": [
                message
                for message in messages
                if message["role"] != ChatContext.ROLE_SYSTEM
            ],
            "system": system,
            "stream": True,
            "max_tokens": 4096
        }

        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(data).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.token,
                "anthropic-version": "2023-06-01"
            }
        )

        buffer = b""
        prefix = "data: "
        with urllib.request.urlopen(request) as fh:
            while response_body := fh.read(100):
                buffer += response_body

                # Avoid potential infinite loop
                for _ in range(100):
                    maybe_idx = buffer.find(b"\n")
                    if maybe_idx == -1:
                        break
                    line = buffer[:maybe_idx].decode()
                    if line.startswith(prefix):
                        data = line[len(prefix):]
                        content = json.loads(data)
                        delta = content.get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            yield text

                    buffer = buffer[maybe_idx + 1:]


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

                # Avoid potential infinite loop
                for _ in range(100):
                    maybe_idx = buffer.find(b"\n")
                    if maybe_idx == -1:
                        break

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

    def add_history(self, role: str, content: str, item_id: str="unset"):
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


def set_clipboard(content: str) -> bool:
    commands = [
        ["termux-clipboard-set"],
        ["pbcopy"],
        ["wl-copy"],
    ]
    for command in commands:
        try:
            proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL
            )
            proc.stdin.write(content.encode())
            proc.stdin.close()
            proc.wait()
            return True
        except FileNotFoundError:
            pass
    return False


def process_prompt(context: ChatContext, prompt: str) -> Tuple[str, str]:
    bits = prompt.split(" ", maxsplit=1)
    command = ""
    rest = prompt
    if bits[0].startswith("/"):
        command = bits[0]
        rest = bits[1] if len(bits) == 2 else ""

    if command in ("/add", "/a"):
        result = context.add_file(rest)
        if result:
            return "", f"Added file {rest}"
        else:
            return "", f"Failed to add file {rest}"
    elif command in ("/remove", "/r"):
        found = False
        new_files = []
        for idx, file in enumerate(context.files):
            if str(idx) != rest and file["filename"] != rest:
                new_files.append(file)
            else:
                found = True

        context.files = new_files
        return "", "Removed file" if found else "Didn't find file"
    elif command in ("/remove-all", "/ra"):
        context.files = []
        return "", "Removed all files"
    elif command in ("/copy", "/c"):
        item_id = None
        content = ""
        extra = ""
        def _find(matcher):
            nonlocal content, item_id
            for item in reversed(context.history):
                if item["role"] == context.ROLE_ASSISTANT and matcher(item["item_id"]):
                    content = item["content"]
                    item_id = item["item_id"]
                    break

        if rest == "":
            _find(lambda _: True)
        elif rest.startswith("r"):
            _find(lambda item: item == rest)
        if rest.startswith("c"):
            if len(rest) > 1:
                item_id = "r" + rest[1:]
                _find(lambda item: item == item_id)
            else:
                _find(lambda _: True)


            state = "start"
            code_lines = []
            for line in content.splitlines():
                if state == "start":
                    if line.startswith("```"):
                        state = "code"
                elif state == "code":
                    if line.startswith("```"):
                        state = "start"
                    else:
                        code_lines.append(line)
            content = "\n".join(code_lines)
            extra = " code"

        if item_id:
            copied = set_clipboard(content)
            if copied:
                return "", f"Copied {item_id}{extra} to clipboard"
            else:
                return "", f"Failed to copy {item_id}{extra} to clipboard"
        else:
            return "", "Could not find item to copy"
    elif command in ("/pop-history", "/ph"):
        context.history = context.history[:-2]
        return "", "Dropped last request/response from history"
    elif command in ("/print-history", "/prh"):
        if not context.history:
            return "", "No chat history to display"
        
        history_output = []
        for item in context.history:
            role = item["role"]
            content = item["content"]
            item_id = item.get("item_id", "")
            
            if role == ChatContext.ROLE_SYSTEM:
                history_output.append(f"[SYSTEM] {content}")
            elif role == ChatContext.ROLE_USER:
                id_part = f" ({item_id})" if item_id and item_id != "unset" else ""
                history_output.append(f"[USER{id_part}] {content}")
            elif role == ChatContext.ROLE_ASSISTANT:
                id_part = f" ({item_id})" if item_id and item_id != "unset" else ""
                history_output.append(f"[ASSISTANT{id_part}] {content}")
        
        print("\n" + "\n\n".join(history_output) + "\n")
        return "", "Chat history printed above"
    elif command in ("/help", "/h"):
        help_text = """Available commands:
/add <file>, /a <file>        - Add file to chat context
/remove <file>, /r <file>     - Remove file by name or index
/remove-all, /ra              - Remove all files from context
/copy [item], /c [item]       - Copy response to clipboard (latest if no item)
/copy c[num], /c c[num]       - Copy code blocks from response
/pop-history, /ph             - Remove last request/response from history
/print-history, /prh          - Print all chat history to terminal
/help, /h                     - Show this help message"""
        return "", help_text
    elif command == "":
        return prompt, ""
    else:
        return "", f"Unknown command: {command} . Try /help."


def log_message(log_file, actor, message, model=None, response_time=None):
    """Log a message to the conversation log file in JSON format"""
    if log_file:
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "role": actor,
            "message": message
        }
        if model is not None:
            log_entry["model"] = model
        if response_time is not None:
            log_entry["response_time"] = response_time
        log_file.write(json.dumps(log_entry) + "\n")
        log_file.flush()


def restore_chat_history(context: ChatContext, log_filename: str):
    """Restore chat history from a log file"""
    try:
        with open(log_filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    role = entry.get("role")
                    message = entry.get("message")
                    item_id = entry.get("item_id", "unset")
                    
                    # Only restore user and assistant messages, skip system messages
                    # since system prompt is handled separately
                    if role in (ChatContext.ROLE_USER, ChatContext.ROLE_ASSISTANT) and message:
                        context.add_history(role, message, item_id)
                except json.JSONDecodeError:
                    # Skip malformed JSON lines
                    continue
    except FileNotFoundError:
        print(f"Warning: Could not find restore file {log_filename}")
    except Exception as e:
        print(f"Warning: Error reading restore file {log_filename}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Chat with LLMs in the terminal")
    parser.add_argument("--model", 
                       help="The model to use: gpt-4.1-mini, gpt-4.1, claude-haiku, claude-sonnet", 
                       default="gpt-4.1-nano")
    parser.add_argument("--system-prompt", help="Will load a system prompt from this file")
    parser.add_argument("--log", help="Log the conversation to this file in JSON format")
    parser.add_argument("--restore", help="Restore chat history from this log file")
    parser.add_argument("--oneshot", help="Does nothing, used to help rlwrap wrapper", action="store_true")
    args = parser.parse_args()

    if args.model.startswith("claude-"):
        model_map = {
            "claude-haiku": "claude-3-haiku-20240307",
            "claude-sonnet": "claude-3-sonnet-20240229"
        }
        client = AnthropicAPI(os.environ["ANTHROPIC_KEY"], model=model_map[args.model])
    else:
        client = OpenaiAPI(os.environ["OPENAI_KEY"], model=args.model)
    context = ChatContext()
    if args.system_prompt:
        with open(args.system_prompt) as fh:
            system_prompt = fh.read()
        context.add_history(context.ROLE_SYSTEM, system_prompt)

    if args.restore:
        restore_chat_history(context, args.restore)

    log_file = None
    if args.log:
        log_file = open(args.log, "a")


    response_counter = 0
    try:
        while True:
            files = ""
            if len(context.files) > 0:
                files = " " + " ".join([
                    file["filename"]
                    for file in context.files
                ])
            sys.stdout.write(f"{len(context.history):03} r{response_counter:03}{files}>> ")

            # Coalesce multiple lines into a single prompt if they come rapidly.
            # Allows us to supply a single multiline request to the model.
            prompt = sys.stdin.readline()
            if prompt == "":
                break
            while select.select([sys.stdin,], [], [], 0.25)[0]:
                prompt += sys.stdin.readline()
            prompt = prompt.strip()

            prompt_modified, info_message = process_prompt(context, prompt)
            if info_message != "":
                sys.stdout.write(info_message + "\n")
            elif prompt_modified != "":
                log_message(log_file, context.ROLE_USER, prompt)
                start_time = time.time()
                result = ""
                for chunk in client.user_query_streamed(context.build_messages(prompt_modified)):
                    sys.stdout.write(chunk)
                    result += chunk
                # Put the prompt on its own line.
                sys.stdout.write("\n")
                
                response_time = time.time() - start_time
                log_message(log_file, context.ROLE_ASSISTANT, result, model=args.model, response_time=response_time)
                context.add_history(context.ROLE_USER, prompt)
                context.add_history(context.ROLE_ASSISTANT, result, item_id=f"r{response_counter}")
                
                response_counter += 1
    finally:
        if log_file:
            log_file.close()

if __name__ == "__main__":
    main()
