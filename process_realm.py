#!/usr/bin/env python3
import json
import re
import os

# Load .env.dev
env = {}
with open('/home/minsantecohis/csu-analytics/.env.dev') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            if '=' in line:
                k, v = line.split('=', 1)
                # Strip quotes from values
                v = v.strip('"\'')
                env[k] = v

# Load realm.json
with open('/home/minsantecohis/csu-analytics/keycloak/realm/realm.json') as f:
    content = f.read()

# Replace variables
def replace_vars(match):
    var = match.group(1)
    return env.get(var, match.group(0))

content = re.sub(r'\$\{([^}]+)\}', replace_vars, content)

# Write processed file
with open('/tmp/realm-processed.json', 'w') as f:
    f.write(content)

print("Processed realm.json written to /tmp/realm-processed.json")

# Check superset redirect URIs
data = json.loads(content)
for c in data['clients']:
    if 'superset' in c.get('clientId', '').lower():
        print(f"Client: {c['clientId']}")
        for uri in c.get('redirectUris', []):
            print(f"  Redirect URI: {uri}")