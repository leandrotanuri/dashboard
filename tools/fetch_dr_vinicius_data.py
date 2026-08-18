import sys, json, time, requests, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')

with open('token.json') as f:
    t = json.load(f)

r = requests.post(t['token_uri'], data={
    'client_id': t['client_id'], 'client_secret': t['client_secret'],
    'refresh_token': t['refresh_token'], 'grant_type': 'refresh_token',
})
token = r.json()['access_token']

DR_VIN_ID  = '1hajaZpK-2cGY4TEpVGTfM7DljZk0M9fiLO6qylC29Gw'
SHEETS_URL = 'https://sheets.googleapis.com/v4/spreadsheets'

def read_range(sid, range_):
    url = f'{SHEETS_URL}/{sid}/values/{urllib.parse.quote(range_, safe="")}'
    r = requests.get(url, headers={'Authorization': f'Bearer {token}'})
    return r.json().get('values', [])

for tab in ['\U0001f4c8 Abr', '\U0001f4c8 Mai']:
    print(f'=== {tab} ===')
    rows = read_range(DR_VIN_ID, f"'{tab}'!B4:N35")
    for row in rows:
        print(row)
    print()
