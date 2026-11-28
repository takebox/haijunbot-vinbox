# Use Python 3.12 as the base image
FROM python:3.12 AS base

# Create application and workspace directories
RUN mkdir -p /app /workspace

# Set working directory to app directory (for building and installing HaijunBot)
WORKDIR /app

# Build arguments: proxy configuration support (optional)
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG NO_PROXY="localhost,127.0.0.1"

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

# If proxy is provided, set proxy environment variables
RUN if [ -n "$HTTP_PROXY" ]; then \
        echo "Using proxy: HTTP_PROXY=$HTTP_PROXY, HTTPS_PROXY=$HTTPS_PROXY"; \
    fi

# Install system dependencies (Python 3.12 is already included in the base image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Basic tools
    git \
    curl \
    wget \
    ca-certificates \
    # Node.js and npm (frontend build)
    nodejs \
    npm \
    # Locale support (input methods)
    locales \
    # Python build dependencies (for compiling Python extensions, most already included in base image)
    build-essential \
    libssl-dev \
    libffi-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    # libclang dependency (for C/C++ code analysis, supports clang 16-21)
    # Install clang-19 and corresponding libclang (haijunbot-c2rust supports 16-21)
    llvm-19 \
    clang-19 \
    libclang-19-dev \
    # C/C++ static analysis and formatting tools
    clang-tidy \
    clang-format \
    clangd \
    # Fish shell
    fish \
    # Other tool dependencies
    unzip \
    # timeout command
    coreutils \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen \
    && sed -i '/zh_CN.UTF-8/s/^# //g' /etc/locale.gen \
    && locale-gen \
    && python3 --version

# Create haijunbot user (UID 1000, GID 1000)
RUN groupadd -g 1000 haijunbot \
    && useradd -u 1000 -g 1000 -m -s /usr/bin/fish haijunbot \
    && mkdir -p /home/haijunbot/.config/fish /home/haijunbot/.local/share/fish \
    && mkdir -p /workspace \
    && chown -R haijunbot:haijunbot /home/haijunbot /workspace \
    && echo "✅ haijunbot user created successfully"









# Switch back to root user to install system-level tools
USER root



# Set environment variables
ENV PATH="/app/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
    USER=haijunbot \
    HOME=/home/haijunbot \
    TERM=xterm-256color

# Copy project files to app directory
COPY . /app

# Upgrade pip and install HaijunBot (using -e for editable mode, so auto-updates take effect)
# Also install clang dependencies (for C/C++ code analysis)
RUN pip install --upgrade pip setuptools wheel \
    && pip install -e ".[clang19]" \
    && echo "HaijunBot installed" \
    && find /usr/local/lib/python3.12 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.12 -type f -name "*.pyc" -delete 2>/dev/null || true \
    && find /usr/local/lib/python3.12 -type f -name "*.pyo" -delete 2>/dev/null || true \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -rf /root/.cache/pip 2>/dev/null || true

# Install Python static analysis, formatting, and LSP tools
RUN pip install \
    ruff \
    mypy \
    python-lsp-server \
    && echo "✅ Python tools installed successfully" \
    && find /usr/local/lib/python3.12 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.12 -type f -name "*.pyc" -delete 2>/dev/null || true \
    && find /usr/local/lib/python3.12 -type f -name "*.pyo" -delete 2>/dev/null || true \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -rf /root/.cache/pip 2>/dev/null || true

# Install frontend dependencies
WORKDIR /app/src/haijunbot/haijunbot_service/frontend
RUN npm install \
    && echo "✅ Frontend dependencies installed successfully" \
    && rm -rf /root/.npm

# Switch back to /app directory
WORKDIR /app

# Clean up all temporary files and caches to free disk space
RUN rm -rf /tmp/* /var/tmp/* \
    && rm -rf /root/.cache/* \
    && find /usr/local/lib/python3.12 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.12 -type f -name "*.pyc" -delete 2>/dev/null || true \
    && find /usr/local/lib/python3.12 -type f -name "*.pyo" -delete 2>/dev/null || true \
    && find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /app -type f -name "*.pyc" -delete 2>/dev/null || true \
    && find /app -type f -name "*.pyo" -delete 2>/dev/null || true

# Set fish as the default shell (subsequent RUN commands will use fish)
SHELL ["/usr/bin/fish", "-c"]

# Create fish configuration directory
RUN mkdir -p /root/.config/fish; \
    and echo "✅ Fish shell configuration completed"

# Verify installed tools
RUN echo "=== Verify tool installation ==="; \
    and python --version; \
    and git --version; \
    and clang-19 --version | head -1; \
    and clang-tidy --version | head -1; \
    and clang-format --version | head -1; \
    and clangd --version | head -1; \
    and ruff --version; \
    and mypy --version; \
    and pylsp --version; or echo "pylsp installed"; \
    and pip --version; \
    and fish --version; \
    and echo "=== All tools installed successfully ==="

# Set default user to haijunbot
USER haijunbot

# Set default working directory to /workspace (user workspace)
WORKDIR /workspace

# Set default command: start gateway and frontend services (listen on 0.0.0.0 for external container access)
CMD ["haijunbot-service", "run", "--gateway-host", "0.0.0.0", "--gateway-port", "8000", "--frontend-host", "0.0.0.0", "--frontend-port", "5173"]

