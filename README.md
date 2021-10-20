# Nanoweb

Nanoweb is a full asynchronous web server for micropython created in order to benefit from
a correct ratio between memory size and features.

It is thus able to run on an ESP8266.

## Features

* Completely asynchronous
* Declaration of routes via a dictionary or directly by decorator
* Management of static files (see assets_extensions)
* Callbacks functions when a new query or an error occurs
* Extraction of HTML headers
* User code dense and conci
* Routing wildcards
* Named route parameters
* Direct JSON read/write support


## Use

```Python
import uasyncio
from nanoweb import Nanoweb

async def api_status(request):
    """API status endpoint"""
    await request.write("HTTP/1.1 200 OK\r\n")
    await request.write("Content-Type: application/json\r\n\r\n")
    await request.write('{"status": "running"}')

naw = Nanoweb()

# Declare route from a dict
naw.routes = {
    '/api/status': api_status,
}

# Declare route directly with decorator
@naw.route("/ping")
def ping(request):
    await request.write("HTTP/1.1 200 OK\r\n\r\n")
    await request.write("pong")


# Declare route with named 
@naw.route("/pin/<pin>")
def pin(request):
    await request.writeJSON({'requested-pin':request.path_params[pin]})
    
# Read JSON from incoming request 
@naw.route("/update")
def pin(request):
    value = await request.readJSON()
    request.writeJSON({'result':'success','update':value})
    
loop = asyncio.get_event_loop()
loop.create_task(naw.run())
loop.run_forever()
```
