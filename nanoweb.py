import uasyncio as asyncio
import ujson as json
import uerrno


class HttpError(Exception):
    pass

class Request:
    url = ""
    method = ""
    headers = {}
    path_params = {}
    route = ""
    read = None
    write = None
    close = None
    
    async def writeJSON(self, dataObject,code = 200, message = 'OK'):
        await self.writeResult(json.dumps(dataObject),code,message,'application/json')

    async def writeResult(self, result,code = 200, message = 'OK', content_type = 'text/plain'):
        await self.write("HTTP/1.1 %i %s\r\n" % (code, message))
        await self.write("Content-Type: %s\r\n\r\n" % (content_type))
        await self.write(result)
    
    async def getContent(self, max_read_size = 4094):
        if (not hasattr(self,'is_read')):
            setattr(self,'is_read',True)
            self._content = self.read(max_read_size)
        return self._content

       
    async def readJSON(self):
        if (not hasattr(self,'is_read')):
            setattr(self,'is_read',True)
            self._json = json.loads(await self.read(4096))
        return self._json

async def write(request, data):
    await request.write(
        data.encode('ISO-8859-1') if type(data) == str else data
    )

async def error(request, code, reason):
    await request.write("HTTP/1.1 %s %s\r\n\r\n" % (code, reason))
    await request.write("<h1>%s</h1>" % (reason))


async def send_file(request, filename, segment=64, binary=False):
    try:
        with open(filename, 'rb' if binary else 'r') as f:
            while True:
                data = f.read(segment)
                if not data:
                    break
                await request.write(data)
    except OSError as e:
        if e.args[0] != uerrno.ENOENT:
            raise
        raise HttpError(request, 404, "File Not Found")
# will return None if not a match, an empty dict if a match without inline
# params, or a dict with the inline params filled in
def compare_segments(incoming,route):
    if (len(incoming) != len(route)):
        return None
    params = {}
    wildcardPos = 0
    for pos in range(0,len(route)):
        if route[pos] == incoming[pos]:
            #matches
            matches=1
        elif route[pos] == '*':
            params['$'+wildcardPos] = incoming[pos]
            wildcardPos=wildcardPos+1
        elif route[pos] == '**':
            if pos != len(route)-1:
                # invalid path
                return None
            for newpos in range(0,len(incoming)-len(route)):
                params['$'+wildcardPos] = incoming[pos+newpos]
                wildcardPos=wildcardPos+1
            return params
        elif (route[pos].startswith('<') and route[pos].endswith('>')):
            key=route[pos][1:(len(route[pos])-1)]
            params[key] = incoming[pos]
        else:
            return None #not a match
    return params #match with params
    

class Nanoweb:

    extract_headers = ('Authorization', 'Content-Length', 'Content-Type')
    headers = {}

    routes = {}
    routeSegments = {}
    assets_extensions = ('html', 'css', 'js')

    callback_request = None
    callback_error = staticmethod(error)

    STATIC_DIR = './'
    INDEX_FILE = STATIC_DIR + 'index.html'

    def __init__(self, port=80, address='0.0.0.0'):
        self.port = port
        self.address = address

    def route(self, route):
        """Route decorator"""
        def decorator(func):
            self.routes[route] = func
            # preload route segments
            self.route_segments(route)
            return func
        return decorator

    def route_segments(self, route):
        if not 'route' in self.routeSegments:
            self.routeSegments[route] = route.split('/')
        return self.routeSegments[route]
    async def generate_output(self, request, handler):
        """Generate output from handler
        `handler` can be :
         * dict representing the template context
         * string, considered as a path to a file
         * tuple where the first item is filename and the second
           is the template context
         * callable, the output of which is sent to the client
        """
        while True:
            if isinstance(handler, dict):
                handler = (request.url, handler)

            if isinstance(handler, str):
                await write(request, "HTTP/1.1 200 OK\r\n\r\n")
                await send_file(request, handler)
            elif isinstance(handler, tuple):
                await write(request, "HTTP/1.1 200 OK\r\n\r\n")
                filename, context = handler
                context = context() if callable(context) else context
                try:
                    with open(filename, "r") as f:
                        for l in f:
                            await write(request, l.format(**context))

                except OSError as e:
                    if e.args[0] != uerrno.ENOENT:
                        raise
                    raise HttpError(request, 404, "File Not Found")
            else:
                handler = await handler(request)
                if handler:
                    # handler can returns data that can be fed back
                    # to the input of the function
                    continue
            break

    async def handle(self, reader, writer):
        items = await reader.readline()
        items = items.decode('ascii').split()
        if len(items) != 3:
            return

        request = Request()
        request.read = reader.read
        request.write = writer.awrite
        request.close = writer.aclose

        request.method, request.url, version = items

        try:
            try:
                if version not in ("HTTP/1.0", "HTTP/1.1"):
                    raise HttpError(request, 505, "Version Not Supported")

                while True:
                    items = await reader.readline()
                    items = items.decode('ascii').split(":", 1)

                    if len(items) == 2:
                        header, value = items
                        value = value.strip()

                        if header in self.extract_headers:
                            request.headers[header] = value
                    elif len(items) == 1:
                        break

                if self.callback_request:
                    self.callback_request(request)

                if request.url in self.routes:
                    # 1. If current url exists in routes
                    request.route = request.url
                    await self.generate_output(request,
                                               self.routes[request.url])
                else:
                    url_segments = request.url.split('/')
                    # 2. Search url in routes with wildcard
                    for route, handler in self.routes.items():
                        route_segments = self.route_segments(route)
                        comp = compare_segments(url_segments,route_segments)
                        if not comp == None:
                            request.path_params = comp
                            request.route = route
                            await self.generate_output(request, handler)
                            break
                    else:
                        # 3. Try to load index file
                        if request.url in ('', '/'):
                            await send_file(request, self.INDEX_FILE)
                        else:
                            # 4. Current url have an assets extension ?
                            for extension in self.assets_extensions:
                                if request.url.endswith('.' + extension):
                                    await send_file(
                                        request,
                                        '%s/%s' % (
                                            self.STATIC_DIR,
                                            request.url,
                                        ),
                                        binary=True,
                                    )
                                    break
                            else:
                                raise HttpError(request, 404, "File Not Found")
            except HttpError as e:
                request, code, message = e.args
                await self.callback_error(request, code, message)
        except OSError as e:
            # Skip ECONNRESET error (client abort request)
            if e.args[0] != uerrno.ECONNRESET:
                raise
        finally:
            await writer.aclose()

    async def run(self):
        return await asyncio.start_server(self.handle, self.address, self.port)

