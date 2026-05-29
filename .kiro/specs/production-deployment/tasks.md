# Tasks

## Phase A: Infrastructure Preparation (No Downtime)

- [ ] 1. Configure DNS A records for zfts.store and www.zfts.store pointing to 43.159.47.246
- [ ] 2. Verify DNS propagation using `dig zfts.store +short` returns correct IP
- [ ] 3. Install Nginx on VPS: `sudo apt install -y nginx`
- [ ] 4. Create Nginx site configuration at `/etc/nginx/sites-available/zfts.store` with reverse proxy to 127.0.0.1:8080
- [ ] 5. Enable Nginx site: symlink to sites-enabled, remove default, test config with `nginx -t`, reload
- [ ] 6. Install certbot: `sudo apt install -y certbot python3-certbot-nginx`
- [ ] 7. Obtain SSL certificate: `sudo certbot --nginx -d zfts.store -d www.zfts.store`
- [ ] 8. Verify HTTPS works: `curl -I https://zfts.store/health` returns 200
- [ ] 9. Run migration 006 on production database: `psql "$DATABASE_URL" -f migrations/006_refunded_status.sql`
- [ ] 10. Update product prices in database to real production values

## Phase B: Bot Service Switch (~10-30s Downtime)

- [ ] 11. Create systemd service file at `/etc/systemd/system/tstore-bot.service`
- [ ] 12. Stop existing screen session running the bot
- [ ] 13. Update `.env` on VPS: set TELEGRAM_BOT_TOKEN to @zftstore_bot token, ENVIRONMENT=production, TELEGRAM_WEBHOOK_URL=https://zfts.store/webhook
- [ ] 14. Enable and start systemd service: `systemctl daemon-reload && systemctl enable tstore-bot && systemctl start tstore-bot`
- [ ] 15. Verify bot is running: `systemctl status tstore-bot` shows active, send /start to @zftstore_bot

## Phase C: Payment Gateway & Firewall (No Downtime)

- [ ] 16. Switch Pakasir project from Sandbox to Production mode in Pakasir dashboard
- [ ] 17. Update Pakasir webhook/callback URL to `https://zfts.store/webhook/pakasir` in Pakasir dashboard
- [ ] 18. Configure firewall: allow 22/80/443, deny 8080 from external, enable ufw

## Phase D: Verification

- [ ] 19. Test end-to-end: place order via @zftstore_bot → verify QRIS generated → make real payment → verify webhook received → verify account delivered → verify admin notified
- [ ] 20. Verify systemd auto-restart: kill bot process, confirm it restarts within 5 seconds
- [ ] 21. Verify port 8080 is not accessible from external IP
- [ ] 22. Create `.env.sandbox` backup file for future sandbox testing reference
