![img1](/img/ntfy_message.PNG)

> **Note:** This project was developed with AI assistance.

# snmp-2-ntfy

Get instant push notifications from your Dell iDRAC and TrueNAS server alerts.

## What it does

Listens for SNMP traps from Dell iDRAC and TrueNAS and forwards them as notifications to [ntfy](https://ntfy.sh). Get alerts for hardware issues like temperature warnings, fan failures, power supply problems, disk failures, ZFS pool problems, and more - directly to your phone or desktop.

```
iDRAC / TrueNAS → SNMP trap (UDP 162) → Container → ntfy → Your Phone
```

## Quick Start

**1. Download `docker-compose.yml`:**

```bash
curl -O https://raw.githubusercontent.com/brettsimons/snmp-2-ntfy/main/docker-compose.yml
```

**2. Configure:**

Edit the environment variables in `docker-compose.yml` — at minimum set `NTFY_URL`, `NTFY_TOKEN`, and `SNMP_COMMUNITIES`.

**3. Run:**

```bash
docker compose up -d
```

The pre-built image `ghcr.io/brettsimons/snmp-2-ntfy:latest` is pulled automatically.

## Alert Severity

### iDRAC

- **Critical/Non-Recoverable** → 🚨 urgent
- **Warning** → ⚠️ high  
- **OK** → ✅ default
- **Unknown** → ❓ default

### TrueNAS

- **Critical/Alert/Emergency** → 🚨 urgent
- **Warning/Error** → ⚠️ high
- **Notice** → default
- **Info** → low

## Topic Routing

By default, the SNMP community string is used as the ntfy topic. This lets you route different servers to different ntfy topics by setting different community strings.

For example, with `NTFY_URL=https://ntfy.sh` and `SNMP_COMMUNITIES=idrac-r740,truenas-main`:
- Traps with community `idrac-r740` → `https://ntfy.sh/idrac-r740`
- Traps with community `truenas-main` → `https://ntfy.sh/truenas-main`

Set `NTFY_TOPIC` to override this and send all traps to a single topic regardless of community.

## Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NTFY_URL` | **yes** | - | ntfy base URL (e.g., `https://ntfy.sh`) |
| `NTFY_TOKEN` | **yes** | - | Bearer token for authentication |
| `SNMP_COMMUNITIES` | **yes** | - | Comma-separated list of accepted SNMP communities |
| `NTFY_TOPIC` | no | - | Override topic for all traps (default: use SNMP community) |
| `SNMP_LISTEN_ADDRESS` | no | `0.0.0.0` | Listen on all interfaces |
| `SNMP_LISTEN_PORT` | no | `162` | SNMP port |
| `IDRAC_LABEL` | no | `iDRAC` | Server name in iDRAC notifications |
| `TRUENAS_LABEL` | no | `TrueNAS` | Server name in TrueNAS notifications |
| `LOG_LEVEL` | no | `INFO` | DEBUG, INFO, WARNING, ERROR |

## Testing

Send a test iDRAC SNMP trap locally:

```bash
snmptrap -v 2c -c public localhost:162 '' \
  1.3.6.1.4.1.674.10892.5.3.2.5.0.10395 \
  1.3.6.1.4.1.674.10892.5.3.1.1.0 s "TST0001" \
  1.3.6.1.4.1.674.10892.5.3.1.2.0 s "Test Alert" \
  1.3.6.1.4.1.674.10892.5.3.1.3.0 i 3 \
  1.3.6.1.4.1.674.10892.5.3.1.4.0 s "SVCTAG1" \
  1.3.6.1.4.1.674.10892.5.3.1.5.0 s "server.example.com"
```

Send a test TrueNAS SNMP trap locally:

```bash
snmptrap -v 2c -c public localhost:162 '' \
  1.3.6.1.4.1.50536.2.1.1 \
  1.3.6.1.4.1.50536.2.2.1 s "test-alert-001" \
  1.3.6.1.4.1.50536.2.2.2 i 3 \
  1.3.6.1.4.1.50536.2.2.3 s "Test alert from TrueNAS"
```

Check logs:
```bash
docker logs snmp-2-ntfy
```

## Building Locally

To build the image yourself instead of using the pre-built one:

```bash
docker build -t snmp-2-ntfy .
```

Then replace the `image:` line in `docker-compose.yml` with `build: .`.

## Running Without Docker

```bash
pip install -r requirements.txt
export NTFY_URL=https://ntfy.sh
export NTFY_TOKEN=your_token
export SNMP_COMMUNITIES=public
sudo python trap_receiver.py  # Port 162 requires root
```

## License

MIT
