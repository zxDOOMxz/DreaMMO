#!/usr/bin/env python3
"""Test NPCs API endpoint"""

import urllib.request
import json

url = "http://localhost:8000/api/npcs/location/1?character_id=1"

try:
    response = urllib.request.urlopen(url)
    data = json.loads(response.read().decode())
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
