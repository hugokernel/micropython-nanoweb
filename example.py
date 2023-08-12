import json
import os
import network
import time
import sys
import uasyncio as asyncio
from nanoweb import HttpError, Nanoweb, send_file
from ubinascii import a2b_base64 as base64_decode

try:
    from secrets import WLAN_SSID, WLAN_PASSWORD
except ImportError:
    print("Create secrets.py with WLAN_SSID and WLAN_PASSWORD information.")
    raise

CREDENTIALS = ('foo', 'bar')
EXAMPLE_ASSETS_DIR = './example-assets/'

def wlan_connection():
    sta_if = network.WLAN(network.STA_IF)

    if not sta_if.isconnected():
        print('Connecting to %s network...' % WLAN_SSID)
        sta_if.active(True)
        sta_if.connect(WLAN_SSID, WLAN_PASSWORD)

        while not sta_if.isconnected():
            time.sleep(0.5)

    print('Connected to %s network' % WLAN_SSID)
    print('Network config:', sta_if.ifconfig())


def get_time():
    uptime_s = int(time.ticks_ms() / 1000)
    uptime_h = int(uptime_s / 3600)
    uptime_m = int(uptime_s / 60)
    uptime_m = uptime_m % 60
    uptime_s = uptime_s % 60
    return (
        '{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(*time.localtime()),
        '{:02d}h {:02d}:{:02d}'.format(uptime_h, uptime_m, uptime_s),
    )

async def api_send_response(request, code=200, message="OK"):
    await request.write("HTTP/1.1 %i %s\r\n" % (code, message))
    await request.write("Content-Type: application/json\r\n\r\n")
    await request.write('{"status": true}')

def authenticate(credentials):
    async def fail(request):
        await request.write("HTTP/1.1 401 Unauthorized\r\n")
        await request.write('WWW-Authenticate: Basic realm="Restricted"\r\n\r\n')
        await request.write("<h1>Unauthorized</h1>")

    def decorator(func):
        async def wrapper(request):
            header = request.headers.get('Authorization', None)
            if header is None:
                return await fail(request)

            # Authorization: Basic XXX
            kind, authorization = header.strip().split(' ', 1)
            if kind != "Basic":
                return await fail(request)

            authorization = base64_decode(authorization.strip()) \
                .decode('ascii') \
                .split(':')

            if list(credentials) != list(authorization):
                return await fail(request)

            return await func(request)
        return wrapper
    return decorator

@authenticate(credentials=CREDENTIALS)
async def api_status(request):
    """API status endpoint"""
    await request.write("HTTP/1.1 200 OK\r\n")
    await request.write("Content-Type: application/json\r\n\r\n")

    time_str, uptime_str = get_time()

    await request.write(json.dumps({
        "time": time_str,
        "uptime": uptime_str,
        'python': '{} {}'.format(
            sys.implementation.name,
            '.'.join(
                str(s) for s in sys.implementation.version
            ),
        ),
        'platform': str(sys.platform),
    }))


@authenticate(credentials=CREDENTIALS)
async def api_ls(request):
    await request.write("HTTP/1.1 200 OK\r\n")
    await request.write("Content-Type: application/json\r\n\r\n")
    await request.write('{"files": [%s]}' % ', '.join(
        '"' + f + '"' for f in sorted(os.listdir('.'))
    ))


@authenticate(credentials=CREDENTIALS)
async def api_download(request):
    await request.write("HTTP/1.1 200 OK\r\n")

    filename = request.url[len(request.route.rstrip("*")) - 1:].strip("/")

    await request.write("Content-Type: application/octet-stream\r\n")
    await request.write("Content-Disposition: attachment; filename=%s\r\n\r\n"
                        % filename)
    await send_file(request, filename)


@authenticate(credentials=CREDENTIALS)
async def api_delete(request):
    if request.method != "DELETE":
        raise HttpError(request, 501, "Not Implemented")

    filename = request.url[len(request.route.rstrip("*")) - 1:].strip("\/")

    try:
        os.remove(filename)
    except OSError as e:
        raise HttpError(request, 500, "Internal error")

    await api_send_response(request)


@authenticate(credentials=CREDENTIALS)
async def upload(request):
    if request.method != "PUT":
        raise HttpError(request, 501, "Not Implemented")

    bytesleft = int(request.headers.get('Content-Length', 0))

    if not bytesleft:
        await request.write("HTTP/1.1 204 No Content\r\n\r\n")
        return

    output_file = request.url[len(request.route.rstrip("*")) - 1:].strip("\/")
    tmp_file = output_file + '.tmp'

    try:
        with open(tmp_file, 'wb') as o:
            while bytesleft > 0:
                chunk = await request.read(min(bytesleft, 64))
                o.write(chunk)
                bytesleft -= len(chunk)
            o.flush()
    except OSError as e:
        raise HttpError(request, 500, "Internal error")

    try:
        os.remove(output_file)
    except OSError as e:
        pass

    try:
        os.rename(tmp_file, output_file)
    except OSError as e:
        raise HttpError(request, 500, "Internal error")

    await api_send_response(request, 201, "Created")


@authenticate(credentials=CREDENTIALS)
async def assets(request):
    await request.write("HTTP/1.1 200 OK\r\n")

    args = {}

    filename = request.url.split('/')[-1]
    if filename.endswith('.png'):
        args = {'binary': True}

    await request.write("\r\n")

    await send_file(
        request,
        './%s/%s' % (EXAMPLE_ASSETS_DIR, filename),
        **args,
    )


async def post_data(request):
    """Post data example

    Display the data sent with the request.

    You can reach this entrypoint with curl:

    By JSON:
        curl -d '{"key1":"value1", "key2":"value2"}' \
            -H "Content-Type: application/json" -X POST http://URL

    Or by url encoded data:
        curl -d "param1=value1&param2=value2" -X POST http://URL

    Because of the very simpler way the data is decoded in this example,
    I recommend you to use the JSON way to send data: it is more safe.

    If you do not want to use the JSON way, it is better to better decoding
    the data (multiple value for a same key, url encoded string, etc...).
    See https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/POST
    """
    await request.write("HTTP/1.1 200 Ok\r\n")

    if request.method != "POST":
        raise HttpError(request, 501, "Not Implemented")

    try:
        content_length = int(request.headers['Content-Length'])
        content_type = request.headers['Content-Type']
    except KeyError:
        raise HttpError(request, 400, "Bad Request")

    data = (await request.read(content_length)).decode()

    if content_type == 'application/json':
        data = json.loads(data)
        print(data)
    elif content_type == 'application/x-www-form-urlencoded':
        for chunk in data.split('&'):
            key, value = chunk.split('=', 1)
            print('%s = %s' % (key, value))


@authenticate(credentials=CREDENTIALS)
async def index(request):
    await request.write(b"HTTP/1.1 200 Ok\r\n\r\n")

    await send_file(
        request,
        './%s/index.html' % EXAMPLE_ASSETS_DIR,
    )


naw = Nanoweb(80)
naw.assets_extensions += ('ico',)
naw.STATIC_DIR = EXAMPLE_ASSETS_DIR

# Declare route from a dict
naw.routes = {
    '/': index,
    '/assets/*': assets,
    '/api/upload/*': upload,
    '/api/status': api_status,
    '/api/ls': api_ls,
    '/api/download/*': api_download,
    '/api/delete/*': api_delete,
    '/post': post_data,
}

# Declare route directly with decorator
@naw.route("/ping")
async def ping(request):
    await request.write("HTTP/1.1 200 OK\r\n\r\n")
    await request.write("pong")


wlan_connection()

loop = asyncio.get_event_loop()
loop.create_task(naw.run())
loop.run_forever()
