"""
TUI for doing language reading or listening comprehension practice.
"""

import io
import json
import os
import signal
import subprocess
import sys
import tty
import termios


DEFAULT_SPEECH_COMMAND = ["espeak-ng"]


def print_usage(error=True):
    name = sys.argv[0]
    print(
        f"Usage: {name} [-- <args to espeak-ng>] 3< examples.jsonl",
        file=sys.stderr
    )
    sys.exit(1 if error else 0)


def jsonl_iterator(fh: io.FileIO):
    for line in fh.readlines():
        yield json.loads(line)


def speak_example(
    id: str,
    sentence: str,
    extra_args: list
) -> subprocess.Popen:
    maybe_speech_command = os.environ.get("SPEECH_COMMAND")
    base_speech_command = \
        [maybe_speech_command] if maybe_speech_command \
        else DEFAULT_SPEECH_COMMAND
    final_speech_command = base_speech_command + extra_args + [sentence]
    return subprocess.Popen(
        final_speech_command + [sentence],
        env={
            **os.environ,
            "EXAMPLE_ID": id
        }
    )


def print_example_header(idx: int):
    print(f"Example {idx}")
    sys.stdout.write("\033[90m")
    sys.stdout.write(
        "Controls: space=play/pause, r=restart speech, enter=print example\n"
    )
    sys.stdout.write(
        "          n=next example, q=quit"
    )
    sys.stdout.write("\033[0m")
    sys.stdout.write("\n")


def parse_extra_speaker_args() -> list:
    args = sys.argv[1:]
    if "--" in args:
        return args[args.index("--")+1:]
    else:
        return []


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print_usage(False)

    try:
        examples_fh = os.fdopen(3)
    except OSError:
        print_usage()
    extra_speaker_args = parse_extra_speaker_args()

    examples = jsonl_iterator(examples_fh)
    current_example = next(examples)
    current_example_printstate = "foreign"
    current_speech_proc = None
    current_speech_proc_state = None

    def speech_proc_signal(sig=signal.SIGKILL):
        if current_speech_proc:
            current_speech_proc.send_signal(sig)

    def speech_proc_state():
        if (
            current_speech_proc is None or
            current_speech_proc.poll() is not None
        ):
            return "stopped"
        else:
            return current_speech_proc_state

    # Let us read characters as soon as they're pressed
    # and suppress outputting them
    tty.setcbreak(sys.stdin.fileno(), termios.TCSANOW)

    idx = 1
    example_id = current_example.get("id", str(idx))
    print_example_header(example_id)
    try:
        while True:
            foreign_sentence = current_example["foreign"]
            native_sentence = current_example["native"]
            option = sys.stdin.read(1)
            if option == " ":
                state = speech_proc_state()
                if state == "playing":
                    current_speech_proc_state = "paused"
                    speech_proc_signal(signal.SIGSTOP)
                elif state == "paused":
                    current_speech_proc_state = "playing"
                    speech_proc_signal(signal.SIGCONT)
                else:
                    current_speech_proc = speak_example(
                        example_id,
                        foreign_sentence,
                        extra_speaker_args
                    )
                    current_speech_proc_state = "playing"
            elif option == "r":
                speech_proc_signal()
                current_speech_proc = speak_example(
                    example_id,
                    foreign_sentence,
                    extra_speaker_args
                )
                current_speech_proc_state = "playing"
            elif option == "\n":
                if current_example_printstate == "foreign":
                    print(foreign_sentence)
                    current_example_printstate = "native"
                elif current_example_printstate == "native":
                    current_example_printstate = "done"
                    print(native_sentence)
            elif option == "n":
                speech_proc_signal()
                idx += 1
                current_example_printstate = "foreign"
                try:
                    current_example = next(examples)
                    example_id = current_example.get("id", str(idx))
                except StopIteration:
                    break
                print_example_header(example_id)
            elif option == "q":
                break
            else:
                # Don't do anything, user typo
                pass
    finally:
        speech_proc_signal()


if __name__ == "__main__":
    main()
