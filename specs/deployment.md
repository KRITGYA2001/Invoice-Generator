# Deployment Guide

## Stack

| Layer | Technology |
|---|---|
| Cloud | Oracle Cloud Free Tier |
| OS | Ubuntu 22.04 LTS |
| Web server | Nginx (reverse proxy) |
| App server | Gunicorn (WSGI) |
| Database | PostgreSQL (same VM) |
| SSL | Let's Encrypt via Certbot |
| Process manager | systemd |

---

## 1. Oracle Cloud VM Setup

### Create the Instance
- Shape: VM.Standard.E2.1.Micro (Always Free) or Ampere A1 (4 OCPU / 24 GB — also free tier)
- Image: Canonical Ubuntu 22.04
- Download the private key (.key file) at creation time — you cannot download it later

### SSH into the VM
```bash
ssh -i /path/to/your.key ubuntu@<VM_PUBLIC_IP>
```

### Open Firewall Ports (Oracle Cloud Security List)
Oracle Cloud has TWO firewalls — both must allow traffic:

**1. Oracle Security List** (in VCN → Subnets → Security Lists):
Add ingress rules for:
- Port 22 (SSH) — already open by default
- Port 80 (HTTP)
- Port 443 (HTTPS)

**2. Ubuntu UFW** (on the VM itself):
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## 2. Ubuntu System Setup

```bash
sudo apt update && sudo apt upgrade -y

# Python, pip, venv
sudo apt install -y python3 python3-pip python3-venv

# PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Nginx
sudo apt install -y nginx

# WeasyPrint system dependencies (required for PDF generation)
sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libffi-dev shared-mime-info

# Git
sudo apt install -y git

# Other utilities
sudo apt install -y curl unzip
```

---

## 3. PostgreSQL Setup

```bash
sudo -u postgres psql

# Inside psql:
CREATE DATABASE invoice_generator;
CREATE USER invoice_user WITH PASSWORD 'your_strong_password_here';
ALTER ROLE invoice_user SET client_encoding TO 'utf8';
ALTER ROLE invoice_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE invoice_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE invoice_generator TO invoice_user;
\q
```

---

## 4. Project Setup

### Clone the Repository
```bash
cd /home/ubuntu
git clone https://github.com/your-org/Invoice-Generator.git
cd Invoice-Generator
```

### Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn          # add to requirements.txt if not already there
```

### Create the .env File
```bash
nano .env
```

Paste and fill in:
```env
SECRET_KEY=your-long-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-vm-ip,yourdomain.com,www.yourdomain.com

DB_NAME=invoice_generator
DB_USER=invoice_user
DB_PASSWORD=your_strong_password_here
DB_HOST=localhost
DB_PORT=5432

CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=BillMint <no-reply@yourdomain.com>
```

> **Generate a secret key:**
> ```bash
> python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

> **Gmail note:** Use an App Password (not your account password). Enable 2FA → Google Account → Security → App Passwords.

### Run Migrations and Collect Static Files
```bash
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser   # optional: create first admin user
```

### Set Directory Permissions
```bash
sudo chown -R ubuntu:ubuntu /home/ubuntu/Invoice-Generator
chmod -R 755 /home/ubuntu/Invoice-Generator
```

---

## 5. Gunicorn

### Test Gunicorn Manually First
```bash
cd /home/ubuntu/Invoice-Generator
source venv/bin/activate
gunicorn --bind 0.0.0.0:8000 invoice_generator.wsgi:application
```
Visit `http://<VM_IP>:8000` — if it loads, Gunicorn is working. Stop it with Ctrl+C.

### Create a systemd Service
```bash
sudo nano /etc/systemd/system/billmint.service
```

```ini
[Unit]
Description=BillMint Gunicorn Daemon
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/Invoice-Generator
ExecStart=/home/ubuntu/Invoice-Generator/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/home/ubuntu/Invoice-Generator/billmint.sock \
    invoice_generator.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

### Enable and Start the Service
```bash
sudo systemctl daemon-reload
sudo systemctl start billmint
sudo systemctl enable billmint
sudo systemctl status billmint
```

---

## 6. Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/billmint
```

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 20M;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias /home/ubuntu/Invoice-Generator/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/Invoice-Generator/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/Invoice-Generator/billmint.sock;
    }
}
```

### Enable the Site
```bash
sudo ln -s /etc/nginx/sites-available/billmint /etc/nginx/sites-enabled/
sudo nginx -t          # test config — must say "syntax is ok"
sudo systemctl restart nginx
```

---

## 7. SSL with Let's Encrypt (Certbot)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot will:
1. Verify domain ownership (HTTP challenge — port 80 must be open)
2. Issue the certificate
3. **Automatically modify the Nginx config** to redirect HTTP → HTTPS and add SSL directives

### Auto-Renewal
Certbot installs a systemd timer that renews certificates automatically before expiry. Verify it:
```bash
sudo certbot renew --dry-run
sudo systemctl status certbot.timer
```

---

## 8. Directory Structure on the VM

```
/home/ubuntu/Invoice-Generator/
├── venv/                  ← Python virtual environment
├── staticfiles/           ← collectstatic output (served by Nginx)
├── media/                 ← user-uploaded files (served by Nginx)
├── billmint.sock          ← Gunicorn Unix socket (auto-created)
├── .env                   ← production secrets (never commit this)
├── manage.py
├── invoice_generator/
│   ├── settings.py
│   ├── wsgi.py
│   └── urls.py
└── <app dirs>/
```

---

## 9. Maintenance Commands

All commands assume you are in `/home/ubuntu/Invoice-Generator` with the venv active:
```bash
cd /home/ubuntu/Invoice-Generator && source venv/bin/activate
```

### Deploy a Code Update
```bash
git pull origin master
pip install -r requirements.txt          # if dependencies changed
python manage.py migrate                 # if migrations changed
python manage.py collectstatic --noinput # if static files changed
sudo systemctl restart billmint
```

### View Application Logs
```bash
# Gunicorn / app logs
sudo journalctl -u billmint -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Restart Services
```bash
sudo systemctl restart billmint     # restart app (after code changes)
sudo systemctl restart nginx        # restart web server (after nginx config changes)
```

### Check Service Status
```bash
sudo systemctl status billmint
sudo systemctl status nginx
sudo systemctl status postgresql
```

### Django Shell
```bash
python manage.py shell
```

### Database Backup
```bash
sudo -u postgres pg_dump invoice_generator > backup_$(date +%Y%m%d).sql
```

### Database Restore
```bash
sudo -u postgres psql invoice_generator < backup_20260520.sql
```

---

## 10. Environment Variables Reference

| Variable | Production Value | Notes |
|---|---|---|
| `SECRET_KEY` | Long random string | Generate with Django util |
| `DEBUG` | `False` | **Must be False in production** |
| `ALLOWED_HOSTS` | `yourdomain.com,www.yourdomain.com,<VM_IP>` | Comma-separated |
| `DB_NAME` | `invoice_generator` | PostgreSQL DB name |
| `DB_USER` | `invoice_user` | PostgreSQL user |
| `DB_PASSWORD` | Strong password | |
| `DB_HOST` | `localhost` | Same VM |
| `DB_PORT` | `5432` | Default PostgreSQL port |
| `CORS_ALLOWED_ORIGINS` | `https://yourdomain.com` | HTTPS URLs only in prod |
| `EMAIL_HOST` | `smtp.gmail.com` | Or your SMTP provider |
| `EMAIL_HOST_PASSWORD` | Gmail App Password | Not your account password |

---

## 11. Common Issues

### 502 Bad Gateway
Gunicorn isn't running or the socket path is wrong.
```bash
sudo systemctl status billmint
sudo journalctl -u billmint --no-pager -n 50
```

### Static Files Not Loading (404)
`collectstatic` wasn't run, or the `alias` path in Nginx is wrong.
```bash
python manage.py collectstatic --noinput
ls staticfiles/   # should have files
```

### WeasyPrint PDF Errors
Missing system libraries. Install:
```bash
sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2
```

### Permission Denied on Socket
Nginx user (`www-data`) can't read the socket. Fix:
```bash
sudo usermod -aG ubuntu www-data
sudo systemctl restart nginx
```

### Oracle Cloud Port Not Reachable
Check both firewalls — the Oracle Security List **and** UFW on the VM. Oracle's firewall is separate from the OS firewall.

### Database Migration Fails
```bash
python manage.py showmigrations    # see pending
python manage.py migrate --run-syncdb
```
