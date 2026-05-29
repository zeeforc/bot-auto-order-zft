# Requirements Document

## Introduction

This document specifies the requirements for deploying the T-Store Auto Order Bot from sandbox/development mode to full production. The deployment involves configuring DNS, reverse proxy with SSL, switching payment gateway to production mode, setting up process management, and ensuring zero-downtime transition while maintaining sandbox testing capability.

## Glossary

- **Bot**: The T-Store Auto Order Telegram bot application (Python 3.13 + aiogram 3.x + FastAPI + asyncpg)
- **VPS**: The Tencent Cloud Lighthouse virtual private server (Debian 13.2, 2vCPU/2GB RAM, IP: 43.159.47.246)
- **Nginx**: The reverse proxy server that terminates SSL and forwards requests to the Bot
- **Pakasir**: The QRIS payment gateway provider used for processing payments
- **Webhook_Server**: The FastAPI server component of the Bot that receives payment callbacks on port 8080
- **Systemd_Service**: The Linux systemd unit that manages the Bot process lifecycle
- **Certbot**: The Let's Encrypt client used to obtain and renew SSL certificates
- **DNS_Provider**: The domain registrar or DNS management service for zfts.store
- **Production_Bot**: The Telegram bot instance @zftstore_bot used for live customers
- **Sandbox_Bot**: The Telegram bot instance @zftestorder_bot used for testing

## Requirements

### Requirement 1: DNS Configuration

**User Story:** As a store owner, I want my domain zfts.store to resolve to the VPS IP address, so that customers and payment gateways can reach the bot via a memorable domain name.

#### Acceptance Criteria

1. WHEN a DNS A record is created for zfts.store pointing to 43.159.47.246, THE DNS_Provider SHALL propagate the record within 30 minutes
2. WHEN a DNS lookup is performed for zfts.store, THE DNS_Provider SHALL return the IP address 43.159.47.246
3. WHEN a DNS lookup is performed for www.zfts.store, THE DNS_Provider SHALL return the IP address 43.159.47.246

### Requirement 2: Nginx Reverse Proxy

**User Story:** As a store owner, I want Nginx to act as a reverse proxy in front of the bot, so that external HTTPS traffic is properly terminated and forwarded to the internal webhook server.

#### Acceptance Criteria

1. WHEN an HTTPS request arrives at port 443 with path /webhook/pakasir, THE Nginx SHALL forward the request to the Webhook_Server at 127.0.0.1:8080
2. WHEN an HTTPS request arrives at port 443 with path /health, THE Nginx SHALL forward the request to the Webhook_Server at 127.0.0.1:8080
3. WHEN an HTTP request arrives at port 80, THE Nginx SHALL redirect the request to HTTPS (port 443)
4. THE Nginx SHALL preserve the original client IP address via X-Real-IP and X-Forwarded-For headers
5. THE Nginx SHALL pass through all original request headers including Content-Type and custom headers

### Requirement 3: SSL/TLS Certificate

**User Story:** As a store owner, I want HTTPS enabled on my domain, so that payment webhook communication is encrypted and Pakasir accepts the callback URL.

#### Acceptance Criteria

1. WHEN Certbot is executed for zfts.store, THE Certbot SHALL obtain a valid Let's Encrypt TLS certificate
2. THE Certbot SHALL configure automatic certificate renewal before expiration (every 90 days)
3. WHEN a client connects to https://zfts.store, THE Nginx SHALL present a valid TLS certificate for the domain
4. IF the certificate renewal fails, THEN THE Certbot SHALL log the failure and retry on the next scheduled attempt

### Requirement 4: Pakasir Production Mode

**User Story:** As a store owner, I want the Pakasir payment gateway switched to production mode, so that real customer payments are processed through live QRIS codes.

#### Acceptance Criteria

1. WHEN the Pakasir project is switched from Sandbox to Production, THE Pakasir SHALL process real QRIS payments from customer wallets
2. WHEN a payment is completed in production mode, THE Pakasir SHALL send a webhook POST to https://zfts.store/webhook/pakasir with the payment status
3. WHEN the webhook URL is updated to https://zfts.store/webhook/pakasir, THE Pakasir SHALL deliver callbacks exclusively to the HTTPS endpoint
4. IF the webhook delivery fails, THEN THE Pakasir SHALL retry the callback according to the provider retry policy

### Requirement 5: Bot Token Switch

**User Story:** As a store owner, I want to switch from the test bot to the production bot, so that customers interact with the official @zftstore_bot identity.

#### Acceptance Criteria

1. WHEN the TELEGRAM_BOT_TOKEN environment variable is set to the Production_Bot token, THE Bot SHALL authenticate as @zftstore_bot
2. WHEN the Bot starts with the production token, THE Bot SHALL register all commands (user and admin) on the Production_Bot
3. WHILE the Production_Bot is active, THE Sandbox_Bot SHALL remain available for future testing by running a separate instance with the test token

### Requirement 6: Systemd Service Management

**User Story:** As a store owner, I want the bot managed by systemd, so that it automatically restarts on crash or server reboot without manual intervention.

#### Acceptance Criteria

1. THE Systemd_Service SHALL start the Bot automatically when the VPS boots
2. WHEN the Bot process crashes or exits unexpectedly, THE Systemd_Service SHALL restart the Bot within 5 seconds
3. WHEN the Systemd_Service starts the Bot, THE Bot SHALL run under a dedicated non-root user account
4. WHEN an administrator runs `systemctl status tstore-bot`, THE Systemd_Service SHALL report the current process state and uptime
5. WHEN an administrator runs `journalctl -u tstore-bot`, THE Systemd_Service SHALL provide access to the Bot application logs

### Requirement 7: Firewall Configuration

**User Story:** As a store owner, I want the VPS firewall properly configured, so that only necessary ports are exposed and the internal webhook port is not directly accessible from the internet.

#### Acceptance Criteria

1. THE VPS SHALL allow inbound traffic on port 22 (SSH), port 80 (HTTP), and port 443 (HTTPS)
2. THE VPS SHALL block direct inbound traffic to port 8080 from external sources
3. WHILE the firewall is active, THE VPS SHALL allow localhost traffic from Nginx to port 8080

### Requirement 8: Database Migration

**User Story:** As a store owner, I want the refunded status migration applied to the production database, so that refund functionality works correctly for live orders.

#### Acceptance Criteria

1. WHEN migration 006 is executed, THE Bot SHALL support the 'refunded' status value in the orders table
2. WHEN migration 006 is executed, THE Bot SHALL preserve all existing order data without modification
3. IF migration 006 fails, THEN THE Bot SHALL continue operating with the existing status values without data loss

### Requirement 9: Production Pricing

**User Story:** As a store owner, I want product prices updated to real values, so that customers are charged the correct amounts for their purchases.

#### Acceptance Criteria

1. WHEN the store goes live, THE Bot SHALL display real product prices (not test prices of Rp 1.000)
2. WHEN a customer places an order, THE Bot SHALL calculate the total using the production price for the selected product and quantity
3. WHEN a QRIS payment is generated, THE Pakasir SHALL create a payment request with the correct production amount

### Requirement 10: End-to-End Production Verification

**User Story:** As a store owner, I want to verify the complete order flow works in production, so that I have confidence the system is ready for real customers.

#### Acceptance Criteria

1. WHEN a customer sends /start to the Production_Bot, THE Bot SHALL display the product catalog with real prices
2. WHEN a customer completes an order, THE Bot SHALL generate a valid production QRIS code via Pakasir
3. WHEN a real payment is made via QRIS, THE Pakasir SHALL deliver a webhook callback to https://zfts.store/webhook/pakasir
4. WHEN the webhook is received, THE Bot SHALL update the order status to paid and deliver the purchased account to the customer
5. WHEN the order is delivered, THE Bot SHALL notify the admin via Telegram with order details

### Requirement 11: Minimal Downtime Deployment

**User Story:** As a store owner, I want the production switch to happen with minimal downtime, so that the transition does not disrupt any in-progress orders.

#### Acceptance Criteria

1. WHEN switching from screen session to Systemd_Service, THE Bot SHALL experience less than 30 seconds of downtime
2. WHEN the Bot restarts with the new configuration, THE Bot SHALL cancel stale pending orders older than 30 minutes via the existing cleanup task
3. IF an order is in pending state during the switch, THEN THE Bot SHALL allow the customer to re-order after the switch completes
