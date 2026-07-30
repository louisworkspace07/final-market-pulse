import urllib.request
req = urllib.request.Request('http://127.0.0.1:5000/api/refresh_stream?sym=A32')
with urllib.request.urlopen(req) as response:
    while True:
        chunk = response.read(10)
        if not chunk:
            break
        print(repr(chunk))
