#!/bin/bash

_dir="$( cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
runner="${_dir}/fetch1.py"

# loop 10 times and fetch an instance address
i=0
while [ $i -ne 10 ];
do
    printf "\n\n\n!!!!!!"
    printf "\n\n\nDoing number $i"
    printf "\n\n"
    $runner $i
    i=$(($i+1))
done
