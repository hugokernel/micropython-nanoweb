# Nanoweb

Nanoweb is a full asynchronous web server for micropython created in order to benefit from
a correct ratio between memory size and features.

It is thus able to run on an ESP8266, ESP32, Raspberry Pico, etc...

## Features

* Completely asynchronous
* Declaration of routes via a dictionary or directly by decorator
* Management of static files (see assets_extensions)
* Callbacks functions when a new query or an error occurs
* Extraction of HTML headers
* User code dense and conci
* Routing wildcards

## Use

See the [example.py](example.py) file for an advanced example where you will be able to:

* Make a JSON response
* Use pages protected with credentials
* Upload file
* Use `DELETE` method
* Read `POST` data

And this is a simpler example:

```Python
import uasyncio
from nanoweb import Nanoweb

naw = Nanoweb()

async def api_status(request):
    """API status endpoint"""
    await request.write("HTTP/1.1 200 OK\r\n")
    await request.write("Content-Type: application/json\r\n\r\n")
    await request.write('{"status": "running"}')

# You can declare route from the Nanoweb routes dict...
naw.routes = {
    '/api/status': api_status,
}

# ... or declare route directly from the Nanoweb route decorator
@naw.route("/ping")
async def ping(request):
    await request.write("HTTP/1.1 200 OK\r\n\r\n")
    await request.write("pong")

loop = asyncio.get_event_loop()
loop.create_task(naw.run())
loop.run_forever()
```

## Contribute

* Your code must respects `flake8` and `isort` tools
* Format your commits with `Commit Conventional` (https://www.conventionalcommits.org/en/v1.0.0/)
