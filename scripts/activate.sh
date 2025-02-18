#!/bin/bash

LINE_LENGTH=$(tput cols)
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='
echo "Running ./scripts/activate.sh"
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='

echo "To activate your virtual environment, copy and paste the command below into your shell: "
poetry env activate
