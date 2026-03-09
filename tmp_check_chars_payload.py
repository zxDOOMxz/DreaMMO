import uuid
import httpx
import base64
import json

base = 'http://127.0.0.1:8000/api'
u = 'check_' + uuid.uuid4().hex[:6]
p = 'StrongPass123!'
e = f'{u}@example.com'

httpx.post(base + '/auth/register', json={'username': u, 'email': e, 'password': p}, timeout=20)
login = httpx.post(base + '/auth/login', json={'username': u, 'password': p}, timeout=20)
login.raise_for_status()
token = login.json()['access_token']
payload = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '==').decode())
user_id = int(payload['sub'])
headers = {'Authorization': f'Bearer {token}'}

races = httpx.get(base + '/races', headers=headers, timeout=20).json()['races']
classes = httpx.get(base + '/classes', headers=headers, timeout=20).json()['classes']

httpx.post(
    base + '/characters/create',
    json={'name': 'Char_' + uuid.uuid4().hex[:6], 'race_id': races[0]['id'], 'class_id': classes[0]['id']},
    headers=headers,
    timeout=20,
)
chars = httpx.get(base + '/characters', params={'user_id': user_id}, headers=headers, timeout=20)
print(chars.status_code)
print(chars.text)
