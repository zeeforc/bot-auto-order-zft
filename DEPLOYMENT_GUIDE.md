# 🚀 Deployment Guide — T-Store Bot ke VPS Production

> Panduan lengkap deploy bot + setup domain callback untuk Tripay.
> Ditulis untuk VPS Ubuntu 22.04/24.04, 2 vCPU, 2GB RAM, 30GB SSD.

---

## Gambaran Besar (Big Picture)

```
[User Telegram] → [Telegram Server] → [Bot di VPS (polling)]
                                              ↓
[User bayar QRIS] → [Tripay] → POST callback → [VPS:443 via nginx] → [Bot FastAPI :8080]
                                              ↓
                                    [Bot kirim akun ke user]
```

Yang terjadi:

1. Bot jalan di VPS, polling Telegram (nerima pesan user)
2. User order → bot minta QRIS ke Tripay API
3. User bayar → Tripay kirim POST ke `https://zfts.store/webhook/tripay`
4. Nginx di VPS terima request HTTPS → forward ke bot (port 8080)
5. Bot proses → deliver akun ke user

---

## Step-by-Step

### PHASE 1: Login & Setup Dasar VPS

#### 1.1 Login ke VPS

```bash
# Dari PC lu (Windows Terminal / PowerShell / PuTTY)
ssh root@103.76.108.195
# Masukkan password dari provider VPS
```

Kalau pakai panel web-based, biasanya ada fitur "Console" / "Terminal" langsung di browser.

#### 1.2 Update System

```bash
apt update && apt upgrade -y
```

#### 1.3 Install Dependencies

```bash
# Python 3.10+ (Ubuntu 22.04 udah include Python 3.10)
apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx
```

#### 1.4 Buat User Khusus (Jangan run bot sebagai root)

```bash
adduser botuser
usermod -aG sudo botuser
su - botuser
```

---

### PHASE 2: Upload Project ke VPS

#### Opsi A: Via Git (Recommended)

```bash
# Sebagai botuser
cd ~
git clone https://github.com/USERNAME/bot-auto-order.git
cd bot-auto-order
```

#### Opsi B: Via SCP (Upload langsung dari PC)

```bash
# Dari PC lu (bukan di VPS)
scp -r C:\bot-auto-order root@103.76.108.195:/home/botuser/bot-auto-order
```

#### Opsi C: Via Panel Web

Kalau panel VPS lu support file manager, upload ZIP lalu extract di VPS.

---

### PHASE 3: Setup Python Environment

```bash
cd ~/bot-auto-order

# Buat virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

### PHASE 4: Setup .env Production

```bash
nano .env
```

Isi dengan credential production:

```dotenv
# Telegram
TELEGRAM_BOT_TOKEN=8804782399:AAG6_vQ55TXVZHDJmU94wHeT1Yzrx9pZtRo
TELEGRAM_WEBHOOK_URL=https://zfts.store/webhook

# Database (Supabase Pooler)
DATABASE_URL=postgresql://postgres.hozgmucnwgvhmyjblwmw:tuTlgzUq7uhLJW69@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres

# Tripay PRODUCTION (isi setelah merchant approved)
TRIPAY_API_KEY="ISI_PRODUCTION_KEY"
TRIPAY_API_SECRET="ISI_PRODUCTION_PRIVATE_KEY"
TRIPAY_MERCHANT_CODE="T50387"
QRIS_METHOD=QRIS

# Mode
DEBUG=False
ENVIRONMENT=production

# Admin
ADMIN_IDS=6405535980

# Webhook
WEBHOOK_SECRET=ISI_PRODUCTION_PRIVATE_KEY
WEBHOOK_PORT=8080
```

Simpan: `Ctrl+O` → Enter → `Ctrl+X`

---

### PHASE 5: Setup Domain + SSL (HTTPS)

Tripay production **wajib HTTPS** untuk callback. Kita pakai Nginx + Let's Encrypt (gratis).

#### 5.1 Arahkan Domain ke IP VPS

Di DNS manager domain `zfts.store` (Cloudflare / Niagahoster / dll):

```
Type: A
Name: @ (atau kosong)
Value: 103.76.108.195
TTL: Auto

Type: A
Name: www
Value: 103.76.108.195
TTL: Auto
```

Tunggu propagasi DNS (5-30 menit). Cek: `ping zfts.store` → harus resolve ke `103.76.108.195`.

#### 5.2 Setup Nginx sebagai Reverse Proxy

```bash
# Sebagai root
sudo nano /etc/nginx/sites-available/zfts.store
```

Isi:

```nginx
server {
    listen 80;
    server_name zfts.store www.zfts.store;

    # Webhook endpoint → forward ke bot FastAPI
    location /webhook/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Callback-Signature $http_x_callback_signature;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8080;
    }

    # Default (optional: landing page)
    location / {
        return 200 'T-Store Bot Active';
        add_header Content-Type text/plain;
    }
}
```

Aktifkan:

```bash
sudo ln -s /etc/nginx/sites-available/zfts.store /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t          # Test config (harus "OK")
sudo systemctl reload nginx
```

#### 5.3 Pasang SSL (HTTPS) via Let's Encrypt

```bash
sudo certbot --nginx -d zfts.store -d www.zfts.store
# Ikuti prompt: masukkan email, agree ToS, pilih redirect HTTP→HTTPS
```

Setelah selesai, Nginx otomatis serve HTTPS. Certbot auto-renew tiap 90 hari.

**Test:** Buka browser → `https://zfts.store/health` → harus muncul `{"status": "ok"}`

---

### PHASE 6: Setup Bot sebagai Service (Auto-Start)

Biar bot jalan terus meskipun VPS restart:

```bash
sudo nano /etc/systemd/system/tstore-bot.service
```

Isi:

```ini
[Unit]
Description=T-Store Auto Order Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/bot-auto-order
Environment=PATH=/home/botuser/bot-auto-order/.venv/bin:/usr/bin
ExecStart=/home/botuser/bot-auto-order/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Aktifkan:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tstore-bot    # Auto-start saat boot
sudo systemctl start tstore-bot     # Start sekarang
sudo systemctl status tstore-bot    # Cek status (harus "active (running)")
```

Lihat log:

```bash
sudo journalctl -u tstore-bot -f    # Live log (Ctrl+C untuk keluar)
```

---

### PHASE 7: Setup Firewall

```bash
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP (redirect ke HTTPS)
sudo ufw allow 443/tcp     # HTTPS (Tripay callback masuk sini)
sudo ufw enable
sudo ufw status
```

**JANGAN** buka port 8080 ke public — Nginx yang handle HTTPS di port 443, lalu forward internal ke 8080.

---

### PHASE 8: Set Callback URL di Tripay

Setelah merchant approved + domain + SSL ready:

1. Login Tripay Dashboard → **Merchant** → T50387 → **Edit**
2. Set:
   - **URL Callback:** `https://zfts.store/webhook/tripay`
   - **Website:** `https://zfts.store`
   - **Whitelist IP:** `103.76.108.195`
3. Simpan (jangan ubah-ubah lagi setelah ini biar ga kena review)

---

### PHASE 9: Test Production

```bash
# 1. Cek bot jalan
sudo systemctl status tstore-bot

# 2. Cek webhook reachable dari luar
curl https://zfts.store/health
# Expected: {"status":"ok","service":"T-Store Webhook"}

# 3. Test dari Telegram
# - /start → list produk muncul
# - Order via QRIS → QR image muncul (bukan text "SANDBOX MODE")
# - Bayar pakai e-wallet → callback masuk → akun terkirim

# 4. Cek log realtime
sudo journalctl -u tstore-bot -f
```

---

## Troubleshooting

| Masalah           | Cek                                                                                 |
| ----------------- | ----------------------------------------------------------------------------------- |
| Bot ga jalan      | `sudo systemctl status tstore-bot` → lihat error                                    |
| Webhook ga masuk  | `curl https://zfts.store/health` → kalau timeout, cek nginx + firewall              |
| SSL error         | `sudo certbot renew --dry-run`                                                      |
| Tripay 403        | Signature salah — cek `TRIPAY_API_SECRET` match dengan private key production       |
| Tripay 400        | Credential mismatch — pastikan merchant code, API key, environment semua production |
| Domain ga resolve | Cek DNS A record → `dig zfts.store` atau `nslookup zfts.store`                      |
| Port 8080 blocked | Ga masalah — Nginx forward dari 443 ke 8080 internal. Jangan expose 8080 ke public  |

---

## Command Berguna di VPS

```bash
# Restart bot
sudo systemctl restart tstore-bot

# Lihat log (live)
sudo journalctl -u tstore-bot -f

# Lihat log (last 100 lines)
sudo journalctl -u tstore-bot -n 100

# Stop bot
sudo systemctl stop tstore-bot

# Update code (kalau pakai git)
cd ~/bot-auto-order
git pull
sudo systemctl restart tstore-bot

# Cek disk usage
df -h

# Cek RAM usage
free -h

# Cek proses bot
ps aux | grep python
```

---

## Checklist Sebelum Go Live

- [ ] VPS login OK
- [ ] Python + dependencies installed
- [ ] .env production credentials filled
- [ ] DNS A record pointing to VPS IP
- [ ] Nginx configured + SSL active
- [ ] `https://zfts.store/health` returns OK
- [ ] Bot service running (`systemctl status`)
- [ ] Tripay merchant approved (status: Aktif)
- [ ] Tripay callback URL set to `https://zfts.store/webhook/tripay`
- [ ] TRIPAY_API_KEY = production key (bukan DEV-)
- [ ] TRIPAY_MERCHANT_CODE = T50387
- [ ] Test order QRIS → QR muncul → bayar → akun terkirim
- [ ] Harga produk udah diset ke harga asli (bukan Rp 1.000 testing)

---

## Timeline Rekomendasi

| Hari             | Kerjaan                                                 |
| ---------------- | ------------------------------------------------------- |
| Hari 1           | Login VPS, install deps, upload project, test bot jalan |
| Hari 1           | Setup domain DNS + Nginx + SSL                          |
| Hari 2-3         | Tunggu merchant Tripay approved                         |
| Setelah approved | Isi production key, set callback URL, test real payment |
| Go live          | Set harga asli, broadcast ke user                       |
