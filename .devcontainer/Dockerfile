# Keep this in sync with the base image in the main Dockerfile (ARG PY_VER)
FROM python:3.11.13-trixie AS base

# Install system dependencies that Superset needs
# This layer will be cached across Codespace sessions
RUN apt-get update && apt-get install -y \
    libsasl2-dev \
    libldap2-dev \
    libpq-dev \
    tmux \
    gh \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
# Using COPY --from avoids executing unverified downloaded scripts (docker:S8482)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
