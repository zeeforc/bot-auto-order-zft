# Design Document

## Overview

This design describes the infrastructure and configuration changes needed to deploy the T-Store Auto Order Bot to production. The deployment follows a phased approach to minimize downtime: DNS setup → Nginx + SSL → Pakasir production switch → systemd service → bot token switch → pricing update → verification.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                 │
└───────────┬──────────────────────────────────┬──────────────────┘
            │                                  │
            ▼                                  ▼
┌───────────────────┐              ┌───────────────────────┐
│  Telegram Servers │              │  Pakasir Gateway      │
│  (Bot Polling)    │              │  POST /webhook/pakasir│
└────────┬──────────┘              └──────────┬────────────┘
         │                                    │
         │                                    ▼
         │                         ┌──────────────────────┐
         │                         │  Nginx (port 443)    │
         │                         │  SSL Termination     │
         │                         │  zfts.store          │
         │                         └──────────┬───────────┘
         │                                    │ proxy_pass
         │                                    ▼
         │                         ┌──────────────────────┐
         ├────────────────────────▶│  Bot Application     │
         │  (polling)              │  (systemd managed)   │
         │                         │                      │
         │                         │  ┌────────────────┐  │
         │                         │  │ aiogram 3.x    │  │
         │                         │  │ (Telegram)     │  │
         │                         │  └────────────────┘  │
         │                         │                      │
         │                         │  ┌────────────────┐  │
         │                         │  │ FastAPI :8080  │  │
         │                         │  │ (Webhooks)     │  │
         │                         │  └────────────────┘  │
         │                         └──────────┬───────────┘
         │                                    │
         │                                    ▼
         │                         ┌──────────────────────┐
         │                         │  Supabase PostgreSQL  │
         │                         │  (Cloud DB)           │
         │                         └──────────────────────┘
         │
┌────────┴──────────┐
│  VPS Firewall     │
│  Allow: 22,80,443 │
│  Block: 8080 ext  │
└───────────────────┘
```

## Components

### 1. DNS Configuration

**File changes:** None (external DNS provider configuration)

**Actions:**

- Create A record: `zfts.store` → `43.159.47.246`
- Create A record: `www.zfts.store` → `43.159.47.246`

**Verification:** `dig zfts.store +short` returns `43.159.47.246`

---

### 2. Nginx Reverse Proxy Configuration

**File:** `/etc/nginx/sites-available/zfts.store`

```nginx
server {
    listen 80;
    server_name zfts.store www.zfts.store;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name zfts.store www.zfts.store;

    # SSL certificates (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/zfts.store/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zfts.store/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Webhook endpoint - forward to bot FastAPI
    location /webhook/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Default response
    location / {
        return 200 'T-Store Bot Active';
        add_header Content-Type text/plain;
    }
}
```

**Symlink:** `/etc/nginx/sites-enabled/zfts.store` → `/etc/nginx/sites-available/zfts.store`

---

### 3. SSL Certificate Setup

**Tool:** certbot with nginx plugin

**Command sequence:**

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d zfts.store -d www.zfts.store --non-interactive --agree-tos -m <owner-email>
```

**Auto-renewal:** Certbot installs a systemd timer (`certbot.timer`) that runs `certbot renew` twice daily.

---

### 4. Systemd Service Unit

**File:** `/etc/systemd/system/tstore-bot.service`

```ini
[Unit]
Description=T-Store Auto Order Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/home/botuser/bot-auto-order
Environment=PATH=/home/botuser/bot-auto-order/.venv/bin:/usr/bin:/bin
EnvironmentFile=/home/botuser/bot-auto-order/.env
ExecStart=/home/botuser/bot-auto-order/.venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Activation:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable tstore-bot
sudo systemctl start tstore-bot
```

---

### 5. Firewall Rules

**Tool:** ufw (Uncomplicated Firewall)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (redirect to HTTPS)
sudo ufw allow 443/tcp   # HTTPS (Pakasir webhook)
sudo ufw deny 8080/tcp   # Block direct access to webhook server
sudo ufw enable
```

**Note:** Port 8080 is currently open on the VPS. This must be closed to external traffic — only Nginx on localhost should access it.

---

### 6. Environment Configuration Changes

**File:** `.env` on VPS (`/home/botuser/bot-auto-order/.env`)

Changes required for production:

| Variable               | Current (Dev)                     | Production                                               |
| ---------------------- | --------------------------------- | -------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`   | Test bot token (@zftestorder_bot) | Production bot token (@zftstore_bot)                     |
| `TELEGRAM_WEBHOOK_URL` | `https://your-domain.com/webhook` | `https://zfts.store/webhook`                             |
| `ENVIRONMENT`          | `development`                     | `production`                                             |
| `DEBUG`                | `False`                           | `False`                                                  |
| `PAKASIR_PROJECT_SLUG` | `bot-auto-order-zft`              | Same (or updated if Pakasir changes slug for production) |

All other values (DATABASE_URL, ADMIN_IDS, PAKASIR_API_KEY, WEBHOOK_PORT) remain unchanged.

---

### 7. Database Migration Strategy

**Migration 006** adds 'refunded' to the orders status CHECK constraint.

**Execution:**

```bash
# Connect to Supabase and run migration
psql "$DATABASE_URL" -f migrations/006_refunded_status.sql
```

**Safety:** The migration uses `DROP CONSTRAINT IF EXISTS` followed by `ADD CONSTRAINT`, which is safe for existing data. PostgreSQL DDL is transactional — if it fails, no changes are applied.

---

### 8. Pakasir Production Switch

**Actions in Pakasir Dashboard:**

1. Switch project `bot-auto-order-zft` from Sandbox to Production mode
2. Update webhook/callback URL to `https://zfts.store/webhook/pakasir`
3. Verify API key remains the same (or update `.env` if a new production key is issued)

**Code impact:** None — the `PakasirProvider` class already handles both sandbox and production transparently. The API endpoints and behavior are identical; only the payment processing is real.

---

### 9. Deployment Sequence (Minimal Downtime)

The deployment follows this order to minimize disruption:

```
Phase A (No downtime - preparation):
  1. Setup DNS (A records)
  2. Wait for DNS propagation
  3. Install Nginx
  4. Obtain SSL certificate
  5. Configure Nginx reverse proxy
  6. Run migration 006
  7. Update product prices in database

Phase B (Brief downtime ~10-30 seconds):
  8. Stop screen session (kill existing bot process)
  9. Update .env with production bot token + environment=production
  10. Start bot via systemd service
  11. Verify bot responds to /start

Phase C (No downtime - external config):
  12. Switch Pakasir to production mode
  13. Update Pakasir webhook URL to https://zfts.store/webhook/pakasir
  14. Close port 8080 in firewall

Phase D (Verification):
  15. End-to-end test with real payment
  16. Verify admin notifications
```

---

### 10. Sandbox Preservation Strategy

To maintain sandbox testing capability after production deployment:

- The Sandbox_Bot (@zftestorder_bot) token is preserved in documentation
- A separate `.env.sandbox` file can be created for future test runs
- The same codebase supports both modes via the `ENVIRONMENT` variable
- Sandbox testing can be done by running a second instance with the test token on a different port

---

## Correctness Properties

Since this is primarily an infrastructure/deployment feature (not application logic), most acceptance criteria are verified through integration tests with 1-3 representative examples rather than property-based tests.

### Verifiable Properties

1. **Nginx proxy correctness:** A POST request to `https://zfts.store/webhook/pakasir` with a JSON body arrives at the FastAPI handler with identical body content and preserved headers.

2. **Systemd restart reliability:** When the bot process is killed (SIGKILL), systemd restarts it within 5 seconds and the bot becomes responsive to Telegram commands.

3. **Firewall isolation:** Port 8080 is not reachable from external IPs while remaining accessible from 127.0.0.1.

4. **Migration safety:** After running migration 006, existing orders retain their current status values and the new 'refunded' status is accepted.

5. **SSL validity:** The certificate presented at https://zfts.store is valid, not expired, and issued by Let's Encrypt.

6. **End-to-end payment flow:** A QRIS payment through Pakasir production triggers a webhook that results in order status update and account delivery.

## Dependencies

- Domain registrar access for DNS management
- Pakasir dashboard access for production switch
- Production bot token for @zftstore_bot (from BotFather)
- VPS root/sudo access for Nginx, certbot, systemd, and firewall configuration
- Real product prices determined by store owner

## Risks and Mitigations

| Risk                                        | Impact                          | Mitigation                                                         |
| ------------------------------------------- | ------------------------------- | ------------------------------------------------------------------ |
| DNS propagation delay                       | Webhook unreachable temporarily | Setup DNS first, wait for propagation before switching Pakasir     |
| Pakasir production key differs from sandbox | Payments fail                   | Verify API key in Pakasir dashboard before going live              |
| Bot crash loop in production                | Service unavailable             | RestartSec=5 with systemd + journalctl monitoring                  |
| SSL certificate expiry                      | Webhook rejected                | Certbot auto-renewal + monitoring via `certbot renew --dry-run`    |
| Pending orders during switch                | Customer confusion              | 30-minute cleanup task handles stale orders; brief downtime window |
