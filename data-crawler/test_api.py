import urllib.request
import json

req = urllib.request.Request(
    'http://127.0.0.1:5000/api/refresh',
    data=b'{"sym":"A32"}',
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code}")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
