#!/bin/python

import random
import subprocess
import sys


def play(idx):
    subprocess.run(["mpv", f"{idx}.mp3"], capture_output=True, check=True)


def main():
    with open(sys.argv[1]) as fh:
        sentences = list(enumerate(fh.readlines()))

    total = len(sentences)
    shuffled = random.sample(sentences, k=total)

    count = 0
    while count < total:
        while True:
            idx, sentence = shuffled[count]
            selection = input(f"{total-count:03} enter repeat, p back, n continue> ")
            if selection == "":
                play(idx+1)
            elif selection == "p":
                count -= 1
            elif selection == "n":
                print(sentence)
                count += 1
                break

if __name__ == "__main__":
    main()
