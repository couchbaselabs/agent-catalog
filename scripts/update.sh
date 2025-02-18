#!/bin/bash

LINE_LENGTH=$(tput cols)
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='
echo "Running ./scripts/update.sh"
printf '%*s\n' "$LINE_LENGTH" '' | tr ' ' '='

poetry update
