# 🌌 Datto SaaS Backup Monitor for Zabbix

A Python-based monitoring solution that integrates **Datto SaaS Protection** with **Zabbix**.
This script automatically discovers Office 365 tenants backed up by Datto, retrieves their backup status and coverage percentage, and sends the metrics directly to a Zabbix server using the native Zabbix Sender protocol.

## 💠 Features

- 🔭 **Automated Tenant Discovery**: Uses Zabbix Low-Level Discovery (LLD) to automatically find and monitor Office 365 tenants.
- ⚡ **Agentless Integration**: Sends data using the native Zabbix Sender protocol (using raw sockets) without requiring the `zabbix_sender` binary.
- 🎯 **Detailed Metrics**: Monitors the exact backup percentage and qualitative status (Perfect, Imperfect, Incomplete).
- 🌍 **Global Statistics**: Provides aggregated counters for the overall health of your backups.
- 🔔 **Customizable Alerts**: Includes templates for high-priority ("Incomplete" backups) and warning-level ("Imperfect" backups) triggers.

---

## 🧩 Prerequisites

- 🐍 **Python 3.x**
- 📦 `requests` library (`pip install -r requirements.txt`)
- 🔐 A Datto API Public and Secret Key.
- 🌐 A Zabbix Server reachable on port **10051** by the machine running this script.

---

## 🛸 Setup & Execution

### 🎛️ 1. Configure the Script

Edit `datto_saas_zabbix.py` with your Datto credentials and Zabbix server IP details:

```python
# --- DATTO CONFIGURATION ---
BASE_URL = "https://api.datto.com"
DATTO_PUBLIC_KEY = "YOUR_DATTO_PUBLIC_KEY"
DATTO_SECRET_KEY = "YOUR_DATTO_SECRET_KEY"

# --- ZABBIX CONFIGURATION ---
ENABLE_ZABBIX = True
ZABBIX_SERVER_IP = "YOUR_ZABBIX_SERVER_IP"
ZABBIX_HOST_NAME = "Datto-SaaS-Monitor"
```

### 🖥️ 2. Install on the Server

```bash
# Copy files to your monitoring server
scp datto_saas_zabbix.py requirements.txt user@your-server:/opt/datto-monitor/

# Create Venv
python3 -m venv /opt/datto-monitor/venv
source /opt/datto-monitor/venv/bin/activate

# Install dependencies
pip3 install -r /opt/datto-monitor/requirements.txt

# Run the script manually to test
python3 /opt/datto-monitor/datto_saas_zabbix.py

# Schedule via CRONTAB (example)
crontab -e

0 8 * * * /opt/datto-monitor/venv/bin/python /opt/datto-monitor/datto_saas_zabbix.py >> /opt/datto-monitor/cron_log.txt 2>&1

```

It is recommended to schedule this script via **cron** to run periodically (e.g., once an hour or daily).

---

## 🧠 Zabbix Configuration Guide

### 📂 Quick Start: Import Template (Recommended)

Instead of manually creating each item, you can now import the provided template directly into Zabbix:

1. Download the `zabbix_datto_template.xml` file.
2. In Zabbix, go to **Data collection → Hosts** (or **Configuration → Hosts** in older versions).
3. Click the **Import** button in the top right corner.
4. Select the `zabbix_datto_template.xml` file and click **Import**.
5. This will automatically create the **Datto-SaaS-Monitor** host with all its items, discovery rules, and triggers pre-configured.

---

### 🏛️ 1. Manual Host Creation (Optional)

1. Go to **Configuration → Hosts → Create host**
2. Fill in:
   - **Host name**: `Datto-SaaS-Monitor` *(must exactly match the `ZABBIX_HOST_NAME` in the script)*
   - **Visible name**: `Datto-SaaS-Monitor`
   - **Groups**: choose or create a group (e.g., `Backup Monitors`)
3. **Interfaces** tab: add an **Agent** interface: IP `127.0.0.1`, port `10050` *(required by Zabbix even if not directly polled)*
4. Click **Add**.

### 🛰️ 2. LLD Rule Creation (Discovery)

This rule automatically discovers Office 365 tenants and creates items for each.

1. Navigate to your new host → **Discovery rules → Create discovery rule**
2. Fill in:
   - **Name**: `Datto SaaS - Tenant Discovery`
   - **Type**: `Zabbix trapper`
   - **Key**: `datto.saas.discovery`
    *(data is dynamically pushed by the script)*
   - **Keep lost resources period**: `7d` *(removes tenants not seen for 7 days)*
3. Click **Add**.

### 🧬 3. Item Prototypes (within the LLD Rule)

From the newly created LLD Rule → **Item prototypes → Create item prototype**

#### 🔖 3.1 – Backup status (String)
- **Name**: `Backup status - {#TENANT}`
- **Type**: `Zabbix trapper`
- **Key**: `datto.saas.status[{#TENANT}]`
- **Type of information**: `Text`


#### 🌡️ 3.2 – Backup percentage (Number)
- **Name**: `Backup percentage - {#TENANT}`
- **Type**: `Zabbix trapper`
- **Key**: `datto.saas.backup_pct[{#TENANT}]`
- **Type of information**: `Numeric (float)`
- **Units**: `%`


### 🧨 4. Trigger Prototypes (within LLD)

From the LLD Rule → **Trigger prototypes → Create trigger prototype**

#### 💥 4.1 – Incomplete Alert (High)
- **Name**: `INCOMPLETE Backup: {#TENANT}`
- **Severity**: `High`
- **Expression**: `last(/Datto-SaaS-Monitor/datto.saas.status[{#TENANT}])="Incomplete"`

#### 🚧 4.2 – Imperfect Alert (Warning)
- **Name**: `IMPERFECT Backup: {#TENANT}`
- **Severity**: `Warning`
- **Expression**: `last(/Datto-SaaS-Monitor/datto.saas.status[{#TENANT}])="Imperfect"`

### 📊 5. Simple Items – Global Counters

These items provide aggregated statistics across all monitored tenants. Create them directly under **Items** on the host, with **Update interval** set to `0`.

- **Name**: `SaaS - Tenants with Perfect backup`
  **Type**: `Zabbix trapper` | **Key**: `datto.saas.stats.perfect_count` | **Type of info**: `Numeric (unsigned)`

- **Name**: `SaaS - Tenants with Imperfect backup`
  **Type**: `Zabbix trapper` | **Key**: `datto.saas.stats.imperfect_count` | **Type of info**: `Numeric (unsigned)`

- **Name**: `SaaS - Tenants with Incomplete backup`
  **Type**: `Zabbix trapper` | **Key**: `datto.saas.stats.incomplete_count` | **Type of info**: `Numeric (unsigned)`

- **Name**: `SaaS - Total monitored tenants`
  **Type**: `Zabbix trapper` | **Key**: `datto.saas.stats.total_count` | **Type of info**: `Numeric (unsigned)`

### 🌋 6. Global Triggers (Optional)

You can optionally create host-level triggers for global visibility:

- 💥 `Datto SaaS: there are tenants with INCOMPLETE backup` (High): `last(/Datto-SaaS-Monitor/datto.saas.stats.incomplete_count)>0`
- 🚧 `Datto SaaS: there are tenants with IMPERFECT backup` (Warning): `last(/Datto-SaaS-Monitor/datto.saas.stats.imperfect_count)>0`

---

## 🗂️ Keys Summary Reference

| Key | Zabbix Type | Description |
|---|---|---|
| `datto.saas.discovery` | LLD Rule (Trapper) | Automatic tenant discovery |
| `datto.saas.status[{#TENANT}]` | Item Prototype (Text) | Status: Perfect/Imperfect/Incomplete/Unknown |
| `datto.saas.backup_pct[{#TENANT}]` | Item Prototype (Float) | Backup percentage last 24h |
| `datto.saas.stats.perfect_count` | Item (Unsigned) | Global perfect backups count |
| `datto.saas.stats.imperfect_count` | Item (Unsigned) | Global imperfect backups count |
| `datto.saas.stats.incomplete_count` | Item (Unsigned) | Global incomplete backups count |
| `datto.saas.stats.total_count` | Item (Unsigned) | Global total monitored tenants |

---

## 📜 License
MIT License
