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
# This will also be cached in the image
# Download installer and verify checksum before executing (docker:S8482)
RUN curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh && \
    echo "053045e1e69ec77358fd44f2ef2cacb768a22d50f433e213624f0157ffbbc883  /tmp/uv-install.sh" | sha256sum --check && \
    sh /tmp/uv-install.sh && \
    rm /tmp/uv-install.sh && \
    echo 'export PATH="/root/.cargo/bin:$PATH"' >> /etc/bash.bashrc

# Set the cargo/bin directory in PATH for all users
ENV PATH="/root/.cargo/bin:${PATH}"
