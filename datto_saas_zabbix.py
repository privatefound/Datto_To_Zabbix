import requests
import json
import time
import socket
import struct
from requests.auth import HTTPBasicAuth

# --- CONFIGURAZIONE DATTO ---
BASE_URL = "https://api.datto.com"
DATTO_PUBLIC_KEY = "YOUR_DATTO_PUBLIC_KEY"
DATTO_SECRET_KEY = "YOUR_DATTO_SECRET_KEY"

# --- CONFIGURAZIONE ZABBIX ---
ENABLE_ZABBIX = True
ZABBIX_SERVER_IP = "YOUR_ZABBIX_SERVER_IP"
ZABBIX_HOST_NAME = "Datto-SaaS-Monitor"

# --- CHIAVI ZABBIX ---
KEY_DISCOVERY      = "datto.saas.discovery"
KEY_STATUS         = "datto.saas.status"        # item prototype: datto.saas.status[{#TENANT}]
KEY_BACKUP_PCT     = "datto.saas.backup_pct"    # item prototype: datto.saas.backup_pct[{#TENANT}]

KEY_COUNT_PERFECT    = "datto.saas.stats.perfect_count"
KEY_COUNT_IMPERFECT  = "datto.saas.stats.imperfect_count"
KEY_COUNT_INCOMPLETE = "datto.saas.stats.incomplete_count"
KEY_COUNT_TOTAL      = "datto.saas.stats.total_count"


def get_auth():
    return HTTPBasicAuth(DATTO_PUBLIC_KEY, DATTO_SECRET_KEY)


def fetch_saas_domains():
    """Scarica la lista di tutti i domini/tenant SaaS da Datto."""
    url = f"{BASE_URL}/v1/saas/domains"
    print("--- Scaricamento domini SaaS Protection ---")
    try:
        response = requests.get(url, auth=get_auth(), timeout=30)
        response.raise_for_status()
        data = response.json()
        # L'endpoint restituisce direttamente un array
        if isinstance(data, list):
            print(f"   -> {len(data)} domini trovati.")
            return data
        # Formato alternativo con wrapper
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
            print(f"   -> {len(items)} domini trovati.")
            return items
    except Exception as e:
        print(f"Errore download domini SaaS: {e}")
    return []


def map_status(backup_percentage):
    """
    Mappa la percentuale di backup a uno stato testuale.
      100%        -> Perfect
      0% < x < 100% -> Imperfect
      0%          -> Incomplete
      None        -> Unknown
    """
    if backup_percentage is None:
        return "Unknown"
    pct = float(backup_percentage)
    if pct >= 100.0:
        return "Perfect"
    elif pct > 0.0:
        return "Imperfect"
    else:
        return "Incomplete"


def send_to_zabbix(metrics):
    """Invia metriche a Zabbix usando il protocollo Zabbix Sender nativo (no dipendenze esterne)."""
    if not metrics:
        return
    payload = json.dumps({"request": "sender data", "data": metrics}).encode("utf-8")
    header  = b"ZBXD\x01" + struct.pack("<Q", len(payload))
    try:
        with socket.create_connection((ZABBIX_SERVER_IP, 10051), timeout=10) as s:
            s.sendall(header + payload)
            resp_header = s.recv(13)
            if resp_header.startswith(b"ZBXD\x01"):
                resp_len  = struct.unpack("<Q", resp_header[5:13])[0]
                resp_body = s.recv(resp_len)
                print(f"ZABBIX RISPOSTA: {resp_body.decode('utf-8')}")
            else:
                print("Risposta Zabbix non valida.")
    except Exception as e:
        print(f"Errore Zabbix Send: {e}")


if __name__ == "__main__":
    if not ENABLE_ZABBIX:
        print("Zabbix disabilitato. Uscita.")
        exit(0)

    print("\n1. Inizio raccolta dati SaaS Protection da Datto...\n")

    domains = fetch_saas_domains()

    if not domains:
        print("Nessun dato recuperato. Uscita.")
        exit(1)

    discovery_payload = []
    status_metrics    = []

    count_perfect    = 0
    count_imperfect  = 0
    count_incomplete = 0
    count_total      = 0

    print(f"\n--- ELABORAZIONE TENANT (Totale trovati: {len(domains)}) ---")
    print(f"{'TENANT / DOMINIO':<45} | {'STATUS':<12} | {'BACKUP %':>8}")
    print("-" * 75)

    for domain_data in domains:
        customer_name = domain_data.get("saasCustomerName") or domain_data.get("domain", "Unknown")
        domain        = domain_data.get("domain", "")
        product_type  = domain_data.get("productType", "")

        # Filtra solo tenant Office365 (modifica o rimuovi se vuoi monitorare anche Google Workspace)
        if product_type not in ("Office365",):
            continue

        stats      = domain_data.get("backupStats") or {}
        backup_pct = stats.get("backupPercentage")
        status     = map_status(backup_pct)

        count_total += 1

        if status == "Perfect":
            count_perfect += 1
        elif status == "Imperfect":
            count_imperfect += 1
        elif status == "Incomplete":
            count_incomplete += 1

        # Discovery: usa il nome cliente come chiave primaria, dominio come macro aggiuntiva
        discovery_payload.append({
            "{#TENANT}":   customer_name,
            "{#DOMAIN}":   domain,
            "{#PRODUCT}":  product_type,
        })

        # Metriche per singolo tenant
        status_metrics.append({"host": ZABBIX_HOST_NAME, "key": f"{KEY_STATUS}[{customer_name}]",    "value": str(status)})
        status_metrics.append({"host": ZABBIX_HOST_NAME, "key": f"{KEY_BACKUP_PCT}[{customer_name}]", "value": str(backup_pct if backup_pct is not None else 0)})

        # Stampa
        label = (customer_name[:42] + "..") if len(customer_name) > 42 else customer_name
        pct_str = f"{float(backup_pct):.1f}%" if backup_pct is not None else "N/A"
        print(f"{label:<45} | {status:<12} | {pct_str:>8}")

    print("-" * 75)
    print(f"STATS: Tot:{count_total} | Perfect:{count_perfect} | Imperfect:{count_imperfect} | Incomplete:{count_incomplete}")

    # Contatori globali
    status_metrics.append({"host": ZABBIX_HOST_NAME, "key": KEY_COUNT_PERFECT,    "value": str(count_perfect)})
    status_metrics.append({"host": ZABBIX_HOST_NAME, "key": KEY_COUNT_IMPERFECT,  "value": str(count_imperfect)})
    status_metrics.append({"host": ZABBIX_HOST_NAME, "key": KEY_COUNT_INCOMPLETE, "value": str(count_incomplete)})
    status_metrics.append({"host": ZABBIX_HOST_NAME, "key": KEY_COUNT_TOTAL,      "value": str(count_total)})

    if discovery_payload:
        print(f"\n[1] Invio Discovery ({len(discovery_payload)} tenant)...")
        disc_metric = [{"host": ZABBIX_HOST_NAME, "key": KEY_DISCOVERY, "value": json.dumps({"data": discovery_payload})}]
        send_to_zabbix(disc_metric)

        print("Attesa tecnica 5 secondi per elaborazione server...")
        time.sleep(5)

        print(f"[2] Invio Metriche Stati e Contatori ({len(status_metrics)} items)...")
        send_to_zabbix(status_metrics)
    else:
        print("Nessun tenant Office365 attivo trovato.")
