"""HTTP checks against a synthetic volume on the isolated network."""
import gzip
import requests
base = 'http://lightserv-port-volume:1337'
r = requests.get(base+'/info'); assert r.status_code == 200 and r.json()['type'] == 'image'
assert requests.head(base+'/info').status_code == 200
r = requests.options(base+'/info', headers={'Origin':'https://example.test','Access-Control-Request-Method':'GET'})
assert r.status_code == 204 and 'HEAD' in r.headers['Access-Control-Allow-Methods']
for path in ('chunk', 'compressed'):
    r = requests.get(base+'/'+path)
    assert r.content == b'0123456789', (path,r.content)
for value,expected in [('bytes=2-5',b'2345'),('bytes=7-',b'789'),('bytes=-3',b'789')]:
    r = requests.get(base+'/chunk',headers={'Range':value})
    assert r.status_code == 206 and r.content == expected
assert requests.get(base+'/chunk',headers={'Range':'bytes=100-'}).status_code == 416
assert requests.get(base+'/missing').status_code == 404
assert requests.get(base+'/').status_code == 404
assert requests.get(base+'/.secret').status_code == 404
assert requests.post(base+'/chunk',data=b'bad').status_code == 405
print('PASS: metadata, GET/HEAD/OPTIONS, gzip, bounded/open/suffix/invalid ranges, missing files, write rejection')
