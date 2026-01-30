#!/bin/bash

if [ -f devcontainer.env ]; then
  export $(echo $(cat devcontainer.env | sed 's/#.*//g'| xargs) | envsubst)
fi

direnv allow
poetry config virtualenvs.create false
poetry install

