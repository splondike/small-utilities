#!/bin/bash

export ANTHROPIC_API_KEY=$(./openai-password.gitignored)
export OPENAI_API_KEY=$(./openai-password.gitignored)
$@
