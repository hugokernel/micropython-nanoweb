import uasyncio
from nanoweb import Nanoweb

CREDENTIALS = ('foo', 'bar')

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
    await request.write('{"status": "running"}')

naw = Nanoweb()

# Declare route from a dict
naw.routes = {
    '/status.html': {'name': 'Nanoweb'},
    '/status/*': ('/status.html', {'name': 'Nanoweb'}),
    '/api/status': api_status,
}

# Declare route directly with decorator
@naw.route("/ping")
def ping(request):
    await request.write("HTTP/1.1 200 OK\r\n\r\n")
    await request.write("pong")

loop = uasyncio.get_event_loop()
loop.create_task(naw.run())
loop.run_forever()
