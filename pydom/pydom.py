
from aiohttp import web
import mimetypes, asyncio
import logging, os, json
from datetime import datetime

HTML = """
<!doctype html>
<html>
<head>
<title>{title}</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<meta name="description" content="{desc}">
<link rel="icon" type="image/png" href="/favicon.png">
<link href="https://fonts.googleapis.com/icon?family=Material+Icons"
      rel="stylesheet">
<style>
body, html {{margin:0; padding:0; width: 100%; height: 100%;}}
</style>
{head}
<script type="module">
import {{WebMain}} from './web.js';
window.main = new WebMain();
</script>
</head>
<body onload="window.main.onload()">
</body>
</html>
"""

class AppServer(web.Application):
	def __init__(self, app):
		super().__init__()
		self.clients = {}
		self.app = app
		self.log = logging.getLogger()
		self.router.add_route('*', '/ws', self.websocket)
		self.router.add_route('GET', '/', self.root_page)
		self.router.add_route('GET', '/{rsc}', self.file)

		self.on_startup.append(self.start_background_tasks)
		self.on_shutdown.append(self.cleanup_background_tasks)
		

	def get_client(self, request, auth):
		self.clients[auth['id']] = {'user':auth['id'], 'key':'abcd', 'ws':[]}
		return self.clients[auth['id']]
	
	async def websocket(self, request):
		if "Upgrade" not in request.headers:
			return web.Response(text="", status=404)

		ws = web.WebSocketResponse(heartbeat=50.0)
		await ws.prepare(request)
		try:
			auth = (await ws.receive(timeout=3.0)).json()
			self.log.info(f"User Connected:{auth}   {len(self.clients)} other users")
			client = self.get_client(request, auth)

		except:
			self.log.error("User didn't send the right info")
			await ws.close(code=4000)
			return ws

		client['ws'].append(ws)
		client['health'] = self.now()

		self.log.info("%s: WS connect %d", client['user'], len(client['ws']))
		await ws.send_str(json.dumps({'html':self.app.html_str()}))

		async for msg in ws:
			if msg.type == WSMsgType.TEXT:
				client['health'] = self.now()
				#data = json.loads(msg.data)
				print("MSG", msg)
				#await ws.send_str(json.dumps(reply))
			else:
				self.log.error("%s:Strange message: %s: %r", client['user'], msg.type, msg.data)
				await ws.close(code=5001)

		self.log.info("%s:WS Close (%s)", client['user'], ws.closed)
		if ws in client['ws']:
			self.log.info("Removed")
			client['ws'].remove(ws)
		return ws

	def now(self):
		return datetime.utcnow().timestamp() - self.startup_time


	async def root_page(self, request):
		tmpl = {
			'title':'No Title',
			'desc':'No Description',
			'head': '',
		}
		#tmpl.update(self.main())
		#print(tmpl)
		return web.Response(content_type="text/html", text=HTML.format(**tmpl))
	
	async def file(self, request):
		filename = os.getcwd()+'/'+request.match_info['rsc']
		if not os.path.exists(filename):
			raise web.HTTPNotFound()
		
		with open(filename, 'rb') as f:
			body = f.read()
		return web.Response(content_type=mimetypes.guess_type(filename)[0], body=body)
	
	def run(self):
		web.run_app(self)
	
	async def ws_health_check(self):
		check_interval = 5.1 #seconds
		try:
			while True:
				self.log.info(f"{self.now():.1f}")
				await asyncio.sleep(check_interval)
		except asyncio.CancelledError:
			pass
		self.log.info("Health check Cancelled")
	
	async def start_background_tasks(self, app):
		self.startup_time = datetime.utcnow().timestamp()
		self.ws_health_check = app.loop.create_task(self.ws_health_check())

	async def cleanup_background_tasks(self, app):
		self.log.info("Cleanup_background_tasks")
		self.ws_health_check.cancel()
		await self.ws_health_check
		for k, v in self.clients.items():
			self.log.info(f"{v['user']}:close {len(v['ws'])} WS sockets")
			while v['ws']: # actually get removed in at the end of websocket()
				await v['ws'][0].close(code=5000)
		self.log.info("Good Bye...")


	
class Element(object):
	def __init__(self, **kwargs):
		self.props = kwargs.get('props',{})
		self.tag = kwargs.get('tag', 'div')
		self.children = []
		self.handlers = set()

	def addEventListener(self, client):
		self.handlers.append(client)

	def html(self):
		if self.tag == 'cdata':
			return ''.join(map(str, self.children))
		attrs = [f' {k}="{v}"' for k,v in self.props.items()]
		s = f"<{self.tag}{''.join(attrs)}>"
		for child in self.children:
			s += child.html()
		s += f"</{self.tag}>"
		return s
		

class Button(Element):
	def __init__(self, **kwargs):
		kwargs['tag'] = 'input'
		kwargs.setdefault('props',{})
		kwargs['props'].setdefault('type', 'button')
		super().__init__(tag="input", **kwargs)
		
		

class App(Element):
	def __init__(self, **kwargs):
		kwargs['tag'] = 'body'
		super().__init__(**kwargs)
		
	def log(self, str):
		print(str)
	
	def route(self, url):
		print(f"ROUTE: {url}")
	
	def run(self, port=8080):
		AppServer(self).run()
