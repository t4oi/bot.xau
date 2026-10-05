# Deployment Guide

## Quick Start (VPS)
```bash
# 1. Provision a VPS (Ubuntu 22.04+, 1GB RAM minimum)
# 2. Install Docker
curl -fsSL https://get.docker.com | sh

# 3. Clone & configure
git clone <repo> && cd xauusd_pro_bot
cp .env.example .env
# Edit .env with your credentials (pre-configured if extracted)

# 4. Run
docker-compose up -d
docker-compose logs -f
```

## Systemd Service (without Docker)
```ini
# /etc/systemd/system/xauusd-bot.service
[Unit]
Description=XAUUSD Pro Signal Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/xauusd_pro_bot
ExecStart=/usr/bin/python3 run.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now xauusd-bot
sudo journalctl -u xauusd-bot -f
```

## Health Checks
- `python scripts/health_check.py` — verifies data source + Telegram.
- Docker HEALTHCHECK runs every 60s.
- Bot heartbeat job alerts on Telegram if scan stalls.

## Monitoring
- Logs rotate at 10MB, 7 backups (`logs/bot.log`).
- SQLite DB at `data/xauusd_bot.db` — back it up.
- Web dashboard on port 8080 (put behind nginx + SSL for production).

## Nginx Reverse Proxy (optional)
```nginx
server {
    listen 443 ssl;
    server_name bot.yourdomain.com;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
    }
}
```

## Security Checklist
- [ ] Change `WEB_PASSWORD` in `.env`
- [ ] Rotate Telegram bot token if it was ever in a public repo
- [ ] Use firewall (ufw) — only open 8080 to your IP, or 443 via nginx
- [ ] Keep `.env` out of git (already in .gitignore)
- [ ] Regularly back up `data/` and `logs/`
