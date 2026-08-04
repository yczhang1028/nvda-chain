#!/bin/bash
# Setup Cloudflare tunnel for knownothing.cn
set -e
set -a
source /home/ubuntu/.cloudflare/.env
set +a
# CLOUDEFLARE_TOKEN is now in env

TOKEN="$CLOUDEFLARE_TOKEN"
DOMAIN="knownothing.cn"
SUBDOMAIN="nvda"
TUNNEL_NAME="nvda-dash"
LOCAL_URL="http://127.0.0.1:18765"

echo "=== Step 1: Get account & zone ID ==="
ZONE_RESP=$(curl -s "https://api.cloudflare.com/client/v4/zones?name=$DOMAIN" \
  -H "Authorization: Bearer $TOKEN")
ACCOUNT_ID=$(echo "$ZONE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'][0]['account']['id'])")
ZONE_ID=$(echo "$ZONE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'][0]['id'])")
ZONE_STATUS=$(echo "$ZONE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'][0]['status'])")
echo "Account ID: $ACCOUNT_ID"
echo "Zone ID:    $ZONE_ID"
echo "Zone status: $ZONE_STATUS"

echo ""
echo "=== Step 2: Create or find tunnel ==="
TUNNEL_LIST=$(curl -s "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel?name=$TUNNEL_NAME&is_deleted=false" \
  -H "Authorization: Bearer $TOKEN")
TUNNEL_ID=$(echo "$TUNNEL_LIST" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result',[]); print(r[0]['id'] if r else '')")

if [ -z "$TUNNEL_ID" ]; then
  echo "Creating new tunnel '$TUNNEL_NAME'..."
  SECRET=$(python3 -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
  CREATE_RESP=$(curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$TUNNEL_NAME\",\"tunnel_secret\":\"$SECRET\",\"config_src\":\"cloudflare\"}")
  echo "$CREATE_RESP" | python3 -m json.tool
  TUNNEL_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['id'])")
fi
echo "Tunnel ID: $TUNNEL_ID"

echo ""
echo "=== Step 3: Get connector token ==="
CONN_TOKEN=$(curl -s "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/token" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])")
echo "Connector token length: ${#CONN_TOKEN}"

# Save token to file for systemd service
echo "$CONN_TOKEN" > /home/ubuntu/.cloudflare/tunnel_token.txt
chmod 600 /home/ubuntu/.cloudflare/tunnel_token.txt
echo "Saved to /home/ubuntu/.cloudflare/tunnel_token.txt"

echo ""
echo "=== Step 4: Configure tunnel ingress (route subdomain to local) ==="
CONFIG=$(cat <<EOF
{
  "config": {
    "ingress": [
      {
        "hostname": "$SUBDOMAIN.$DOMAIN",
        "service": "$LOCAL_URL",
        "path": ""
      },
      {
        "service": "http_status:404"
      }
    ]
  }
}
EOF
)
CONFIG_RESP=$(curl -s -X PUT "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$CONFIG")
echo "$CONFIG_RESP" | python3 -m json.tool

echo ""
echo "=== Step 5: Create DNS record (CNAME -> tunnel) ==="
# Check if record exists
EXIST=$(curl -s "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$SUBDOMAIN.$DOMAIN" \
  -H "Authorization: Bearer $TOKEN")
REC_ID=$(echo "$EXIST" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result',[]); print(r[0]['id'] if r else '')")
DNS_PAYLOAD="{\"type\":\"CNAME\",\"name\":\"$SUBDOMAIN\",\"content\":\"$TUNNEL_ID.cfargotunnel.com\",\"proxied\":true,\"ttl\":1}"

if [ -z "$REC_ID" ]; then
  echo "Creating CNAME record..."
  DNS_RESP=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$DNS_PAYLOAD")
else
  echo "Updating existing CNAME record $REC_ID..."
  DNS_RESP=$(curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$REC_ID" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$DNS_PAYLOAD")
fi
echo "$DNS_RESP" | python3 -m json.tool

echo ""
echo "✅ DONE. Next: run cloudflared with the token saved above."
echo "URL will be: https://$SUBDOMAIN.$DOMAIN/nvda_chain/"
