# RISE HRMS — Complete Deployment Instructions
# Domain:     https://rise.altzor.com
# Layout:     / (Frontend) -> RISE-Frontend (Port 8001)
#             /api (Backend) -> HRSystem (Port 8000)
# =============================================================================

## HOW IT WORKS
  Internet (HTTPS port 443)
      ↓
  Apache (handles SSL & routes traffic)
      ├── /api  → Gunicorn on 127.0.0.1:8000 (Backend / HRSystem)
      └── /     → Gunicorn on 127.0.0.1:8001 (Frontend / RISE-Frontend)

---

## CURRENT STATUS
Both repos must be cloned via Git to the VM at:
1. Backend: `/var/www/rise/public_html/HRMS/HRSystem`
2. Frontend: `/var/www/rise/public_html/HRMS/RISE-Frontend`

---

## STEP 1: Create the .env files on the server (via SSH)

The `.env` files are NOT in Git. They must be created manually for BOTH apps.

### 1a. Backend `.env`
```bash
nano /var/www/rise/public_html/HRMS/HRSystem/.env
```
Paste the content from `.env.backend.production` (update DB_PASS and JWT_SECRET). Save and exit.

### 1b. Frontend `.env`
```bash
nano /var/www/rise/public_html/HRMS/RISE-Frontend/.env
```
Paste the content from `.env.frontend.production` (update SECRET_KEY). Save and exit.

---

## STEP 2: Set up Python virtual environments

### 2a. Backend VENV
```bash
cd /var/www/rise/public_html/HRMS/HRSystem
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

### 2b. Frontend VENV
```bash
cd /var/www/rise/public_html/HRMS/RISE-Frontend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

---

## STEP 3: Set up the MySQL Database

### 3a. Create the database and user
```bash
mysql -u root -p
```
```sql
CREATE DATABASE hrms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'hrms_user'@'localhost' IDENTIFIED BY 'STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON hrms.* TO 'hrms_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3b. Import the database (Provide hrms_dump.sql to Santosh)
```bash
mysql -u hrms_user -p hrms < /path/to/hrms_dump.sql
```

---

## STEP 4: Set correct file permissions

```bash
sudo chown -R www-data:www-data /var/www/rise/public_html/HRMS
sudo chmod -R 755 /var/www/rise/public_html/HRMS
sudo chmod -R 775 /var/www/rise/public_html/HRMS/HRSystem/uploads
```

---

## STEP 5: Configure Apache

### 5a. Enable required Apache modules
```bash
sudo a2enmod proxy proxy_http ssl rewrite
sudo systemctl restart apache2
```

### 5b. Copy the Apache config file
Upload `rise.altzor.com.conf` to the VM, then:
```bash
sudo cp rise.altzor.com.conf /etc/apache2/sites-available/rise.altzor.com.conf
```

### 5c. Update SSL certificate paths
Edit `/etc/apache2/sites-available/rise.altzor.com.conf` to point to the correct `.crt` and `.key` files.

### 5d. Enable the site
```bash
sudo a2ensite rise.altzor.com.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

---

## STEP 6: Set up Systemd Services (Gunicorn & Dedicated Scheduler)

### 6a. Copy the service files
Upload `rise-hrms-backend.service`, `rise-hrms-frontend.service`, and `rise-hrms-rental-scheduler.service` to the VM, then:
```bash
sudo cp rise-hrms-backend.service /etc/systemd/system/
sudo cp rise-hrms-frontend.service /etc/systemd/system/
sudo cp rise-hrms-rental-scheduler.service /etc/systemd/system/
```

### 6b. Enable and start the services
```bash
sudo systemctl daemon-reload
sudo systemctl enable rise-hrms-backend
sudo systemctl enable rise-hrms-frontend
sudo systemctl enable rise-hrms-rental-scheduler
sudo systemctl start rise-hrms-backend
sudo systemctl start rise-hrms-frontend
sudo systemctl start rise-hrms-rental-scheduler
```

---

## STEP 7: Verify Everything

Check the statuses:
```bash
sudo systemctl status rise-hrms-backend
sudo systemctl status rise-hrms-frontend
sudo systemctl status rise-hrms-rental-scheduler
sudo systemctl status apache2
```

Open `https://rise.altzor.com` in a browser.

---

## FUTURE CODE UPDATES

Backend & Scheduler Updates:
```bash
cd /var/www/rise/public_html/HRMS/HRSystem
git pull
sudo systemctl restart rise-hrms-backend
sudo systemctl restart rise-hrms-rental-scheduler
```

Frontend Updates:
```bash
cd /var/www/rise/public_html/HRMS/RISE-Frontend
git pull
sudo systemctl restart rise-hrms-frontend
```
