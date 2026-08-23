# ── Stage 1: Build dependencies ──
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.11-slim

# Install system dependencies
# - curl, ca-certificates: for Ollama API calls
# - tailscale: for mesh VPN remote access
# - playwright deps: for browser automation
# - adb: for Android phone control
# - procps, iproute2: for Tailscale networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    procps \
    iproute2 \
    iptables \
    adb \
    # Playwright system dependencies (Chromium)
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install Tailscale
RUN curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null \
    && curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | tee /etc/apt/sources.list.d/tailscale.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends tailscale \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Install Playwright Chromium browser
RUN playwright install chromium

# Set up the app
WORKDIR /app
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /root/.agent_screenshots

# Environment defaults
ENV OLLAMA_HOST=http://ollama:11434 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8420

# Expose the command center port
EXPOSE 8420

# Tailscale + agent entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /app/setup.sh

CMD ["/entrypoint.sh"]
