#!/usr/bin/env python3
"""Create Cloudflare Tunnel for knownothing.cn, route nvda.knownothing.cn -> local web server."""
import json, urllib.request, urllib.error, secrets, base64
from pathlib import Path

ENV = {}
with open("/home/ubuntu/.cloudflare/.env") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            ENV[k] = v
TOKEN = ENV.get("CLOUDEFLARE_TOKEN") or ENV.get("CLOUDFLARE_API_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

DOMAIN = "knownothing.cn"
SUBDOMAIN = "nvda"
TUNNEL_NAME = "nvda-dash"
LOCAL_URL = "http://127.0.0.1:18765"

def call(method, url, body=None):
    req = urllib.request.Request(url, headers=HEADERS, method=method,
                                  data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())

# Step 1: get zone + account
print("=== Step 1: Find zone ===")
r = call("GET", f"https://api.cloudflare.com/client/v4/zones?name={DOMAIN}")
assert r['success'], r
zone = r['result'][0]
ZONE_ID = zone['id']
ACC_ID = zone['account']['id']
print(f"  Zone ID: {ZONE_ID}")
print(f"  Account ID: {ACC_ID}")
print(f"  Zone status: {zone['status']}")
if zone['status'] != 'active':
    print(f"  ⚠️  Zone is '{zone['status']}'. DNS record will be created but tunnel won't resolve until status = active.")

# Step 2: create or find tunnel
print("\n=== Step 2: Create or reuse tunnel ===")
r = call("GET", f"https://api.cloudflare.com/client/v4/accounts/{ACC_ID}/cfd_tunnel?name={TUNNEL_NAME}&is_deleted=false")
assert r['success'], r
existing = [t for t in r['result'] if t['name'] == TUNNEL_NAME]
if existing:
    TUNNEL_ID = existing[0]['id']
    print(f"  Reusing tunnel: {TUNNEL_ID}")
else:
    secret = base64.b64encode(secrets.token_bytes(32)).decode()
    r = call("POST", f"https://api.cloudflare.com/client/v4/accounts/{ACC_ID}/cfd_tunnel",
             {"name": TUNNEL_NAME, "tunnel_secret": secret, "config_src": "cloudflare"})
    assert r['success'], r
    TUNNEL_ID = r['result']['id']
    print(f"  Created tunnel: {TUNNEL_ID}")

# Step 3: get connector token
print("\n=== Step 3: Get connector token ===")
r = call("GET", f"https://api.cloudflare.com/client/v4/accounts/{ACC_ID}/cfd_tunnel/{TUNNEL_ID}/token")
assert r['success'], r
conn_token = r['result']
token_path = Path("/home/ubuntu/.cloudflare/tunnel_token.txt")
token_path.write_text(conn_token)
token_path.chmod(0o600)
print(f"  Connector token len: {len(conn_token)}")
print(f"  Saved to: {token_path}")

# Step 4: configure tunnel ingress
print("\n=== Step 4: Configure tunnel ingress ===")
hostname = f"{SUBDOMAIN}.{DOMAIN}"
config = {
    "config": {
        "ingress": [
            {"hostname": hostname, "service": LOCAL_URL},
            {"service": "http_status:404"},
        ]
    }
}
r = call("PUT", f"https://api.cloudflare.com/client/v4/accounts/{ACC_ID}/cfd_tunnel/{TUNNEL_ID}/configurations", config)
assert r['success'], r
print(f"  Routing {hostname} -> {LOCAL_URL}")

# Step 5: DNS CNAME
print("\n=== Step 5: DNS CNAME record ===")
target = f"{TUNNEL_ID}.cfargotunnel.com"
r = call("GET", f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records?name={hostname}")
assert r['success'], r
records = r['result']
payload = {"type": "CNAME", "name": SUBDOMAIN, "content": target, "proxied": True, "ttl": 1}
if records:
    rec_id = records[0]['id']
    r = call("PUT", f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{rec_id}", payload)
    print(f"  Updated CNAME {hostname} -> {target}")
else:
    r = call("POST", f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records", payload)
    print(f"  Created CNAME {hostname} -> {target}")
assert r['success'], r

print(f"\n✅ DONE.")
print(f"   Tunnel ID: {TUNNEL_ID}")
print(f"   Target URL: https://{hostname}/nvda_chain/")
print(f"\nNext: run cloudflared with the saved token.")
