# Enhanced image: based on the official crack-7z-hash image, preinstalls python3.12 + pytest + hca,
# so the Terminal-Bench verifier runs fully offline (without downloading uv/astral.sh inside the container).
# See section 4 of docs/technical/eval_run_guide.md for build instructions.
FROM alexgshaw/crack-7z-hash:20251031

# Preinstall system python3.12 + pip + git (build-time network is reliable, apt source is official Ubuntu)
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip git \
    && rm -rf /var/lib/apt/lists/*

# Preinstall pytest==8.4.1 + pytest-json-ctrf==0.3.5 (pure Python packages, merged directly into site-packages)
COPY pytest-site/ /tmp/pytest-site/
RUN cp -r /tmp/pytest-site/* /usr/lib/python3/dist-packages/ \
    && rm -rf /tmp/pytest-site

# Preinstall hca (haijunbot-ai-assistant) and its dependencies: fully offline install using the cp312 wheelhouse,
# so install() detects that hca already exists and skips (the command -v hca check in harbor_agent.py).
COPY wheelhouse/ /tmp/wheelhouse/
RUN python3 -m pip install --break-system-packages --no-index \
        --find-links=/tmp/wheelhouse haijunbot-ai-assistant \
    && rm -rf /tmp/wheelhouse

# The PyPI release does not bundle builtin prompt resources; copy them from local source into the hca data directory
# (step 4 of install() does the same; preinstalling here lets install() be skipped).
COPY prompts/ /root/.haijunbot/prompts/

# Verify
RUN python3 --version && python3 -m pytest --version && command -v hca
