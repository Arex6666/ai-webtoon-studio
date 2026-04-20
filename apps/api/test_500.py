import urllib.request
import json
import sys

req = urllib.request.Request(
    'http://localhost:8000/api/v1/agent/episode/1/generate-video',
    data=json.dumps({'project_id': 'test', 'image_urls': ['http://test.com/img.jpg'], 'provider': 'doubao'}).encode(),
    headers={'Content-Type': 'application/json'}
)
try:
    r = urllib.request.urlopen(req)
    print(r.read().decode())
except urllib.error.HTTPError as e:
    print(e.read().decode())
    sys.exit(0)
