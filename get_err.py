import urllib.request
from urllib.error import HTTPError
try:
    urllib.request.urlopen('http://localhost:8000/content/trending?limit=5')
except HTTPError as e:
    print(e.read().decode())
