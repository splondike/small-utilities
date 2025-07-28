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
    speech_speed: int,
    extra_args: list
) -> subprocess.Popen:
    maybe_speech_command = os.environ.get("SPEECH_COMMAND")
    if maybe_speech_command:
        base_speech_command = [maybe_speech_command]
    else:
        base_speech_command = DEFAULT_SPEECH_COMMAND
        base_speech_command += ["-s", str(speech_speed)]
    final_speech_command = base_speech_command + extra_args + [sentence]
    return subprocess.Popen(
        final_speech_command + [sentence],
        env={
            **os.environ,
            "EXAMPLE_ID": id,
            "SPEECH_SPEED": str(speech_speed)
        }
    )


def print_example_header(idx: int, speech_speed: int):
    print(f"Example {idx}")
    sys.stdout.write("\033[90m")
    sys.stdout.write(
        "Controls:\n"
        "  space=play/pause r=restart speech\n"
        "  enter=print example q=quit\n"
        "  n=next example p=previous example\n"
        "  g=talk faster+restart j=talk slower\n"
    )
    sys.stdout.write("\033[0m")
    print_speed(speech_speed)


def print_speed(speed):
    sys.stdout.write("\033[90m")
    sys.stdout.write(f"  current speed: {speed}")
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
    current_speech_speed = int(os.environ.get("SPEECH_SPEED", "100"))
    # For the ability to go back to previous examples
    all_examples = [current_example]

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
    print_example_header(example_id, current_speech_speed)
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
                        current_speech_speed,
                        extra_speaker_args
                    )
                    current_speech_proc_state = "playing"
            elif option == "r":
                speech_proc_signal()
                current_speech_proc = speak_example(
                    example_id,
                    foreign_sentence,
                    current_speech_speed,
                    extra_speaker_args
                )
                current_speech_proc_state = "playing"
            elif option in ("g", "j"):
                if option == "g":
                    current_speech_speed += 10
                    print_speed(current_speech_speed)
                elif option == "j":
                    current_speech_speed = max(current_speech_speed - 10, 10)
                    print_speed(current_speech_speed)

                if speech_proc_state() == "playing":
                    speech_proc_signal()
                    current_speech_proc = speak_example(
                        example_id,
                        foreign_sentence,
                        current_speech_speed,
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
            elif option == "p":
                speech_proc_signal()
                if idx == 1:
                    continue
                idx -= 1
                current_example_printstate = "foreign"
                current_example = all_examples[idx - 1]
                example_id = current_example.get("id", str(idx))
                print_example_header(example_id, current_speech_speed)
            elif option == "n":
                speech_proc_signal()
                idx += 1
                current_example_printstate = "foreign"
                try:
                    if idx > len(all_examples):
                        current_example = next(examples)
                        all_examples.append(current_example)
                    else:
                        current_example = all_examples[idx - 1]
                    example_id = current_example.get("id", str(idx))
                except StopIteration:
                    break
                print_example_header(example_id, current_speech_speed)
            elif option == "q":
                break
            else:
                # Don't do anything, user typo
                pass
    finally:
        speech_proc_signal()


if __name__ == "__main__":
    main()
