# Deployment Guide

## Quick Deploy with Docker + Tailscale

### Prerequisites

1. **Docker** installed on your laptop ([get.docker.com](https://get.docker.com))
2. **Docker Compose** v2+ (included with modern Docker)
3. A **Tailscale** account (free at [tailscale.com](https://tailscale.com))
4. A Tailscale **auth key** (see below)

### Getting a Tailscale Auth Key

1. Go to https://login.tailscale.com/admin/settings/keys
2. Click **"Generate auth key"**
3. Choose:
   - **Reusable** if you'll redeploy often
   - **Ephemeral** if you want the node to auto-remove when the container stops
4. Copy the key (starts with `tskey-auth-...`)

### Deploy

```bash
# Clone the repo
git clone https://github.com/MyAgentLLC/Lyra.git
cd Lyra

# Set up your environment
cp .env.example .env
# Edit .env and add your Tailscale auth key
nano .env

# Build and start everything
docker compose up -d

# Watch the logs to see it come online
docker compose logs -f agent
```

The first run will take a few minutes to:
- Download the Ollama Docker image
- Pull the qwen2.5:7b model (~4.5 GB)
- Build the agent Docker image
- Connect to Tailscale

### Access the Command Center

Once running, you can access the command center from **any device on your Tailscale network**:

```
http://lyra-agent:8420
```

Or use the Tailscale IP (shown in the logs):
```
http://100.x.x.x:8420
```

You can also access it locally:
```
http://localhost:8420
```

### Install Tailscale on Your Other Devices

To access the agent from your phone, tablet, or other computers:
1. Install Tailscale on the device ([tailscale.com/download](https://tailscale.com/download))
2. Log in with the same account
3. Navigate to `http://lyra-agent:8420` in a browser

---

## Deploy Without Tailscale (Local Only)

If you just want to run it locally without the VPN:

```bash
git clone https://github.com/MyAgentLLC/Lyra.git
cd Lyra
docker compose up -d
```

Access at `http://localhost:8420`. No Tailscale auth key needed — just leave it blank.

---

## Deploy Without Docker

If you prefer running directly on your machine:

```bash
git clone https://github.com/MyAgentLLC/Lyra.git
cd Lyra
chmod +x setup.sh && ./setup.sh
python3 run.py
```

See the main README for details.

---

## GPU Support (NVIDIA)

To use GPU acceleration for faster LLM inference, uncomment the GPU section in `docker-compose.yml` under the `ollama` service:

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

You'll also need the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installed.

---

## Using a Different Model

To use a different LLM, edit the `ollama-puller` service in `docker-compose.yml`:

```yaml
  ollama-puller:
    command: >
      "ollama pull llama3.1:8b && echo 'Model pulled successfully'"
```

And update `config/config.yaml`:

```yaml
model:
  name: "llama3.1"
```

Recommended models:
| Model | Command | RAM Needed | Notes |
|-------|---------|-----------|-------|
| Qwen 2.5 7B | `ollama pull qwen2.5:7b` | 8GB | Best tool calling |
| Llama 3.1 8B | `ollama pull llama3.1` | 8GB | Good general purpose |
| Llama 3.2 3B | `ollama pull llama3.2:3b` | 4GB | For lower-end laptops |
| Qwen 2.5 14B | `ollama pull qwen2.5:14b` | 16GB | Higher quality |

---

## Phone Control via Docker

ADB inside Docker can't directly access USB devices. Two options:

### Option 1: Network ADB (recommended)
1. On your phone, enable wireless debugging (Android 11+)
2. Get the phone's IP and port
3. Connect from the agent:
```bash
docker exec -it lyra-agent adb connect 192.168.1.100:5555
```

### Option 2: Host ADB bridge
Run ADB on your host machine and forward to the container:
```bash
# On host
adb start-server
# In docker-compose.yml, add:
#   network_mode: host
```

---

## Stopping & Cleaning Up

```bash
# Stop everything
docker compose down

# Stop and remove data (deletes downloaded models!)
docker compose down -v

# Rebuild after code changes
docker compose build --no-cache agent
docker compose up -d
```

---

## Troubleshooting

### Ollama not connecting
```bash
docker compose logs ollama
docker exec -it lyra-ollama ollama list
```

### Tailscale not connecting
```bash
docker exec -it lyra-agent tailscale status
docker exec -it lyra-agent tailscale log
```

### Browser automation not working
```bash
docker exec -it lyra-agent playwright install chromium
```

### Port already in use
Change the port in `docker-compose.yml`:
```yaml
  agent:
    ports:
      - "9000:8420"  # Map to port 9000 instead
```
