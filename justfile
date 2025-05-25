#!/usr/bin/env just --justfile
export PATH := join(justfile_directory(), ".env", "bin") + ":" + env_var('PATH')

setup:
    uv sync
    mkdir -p data
    cp .env.sample .env

download-data:
    bash -x scripts/download_all_data.sh

upgrade:
  uv lock --upgrade
