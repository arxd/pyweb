import importlib,  traceback, os, os.path, json, subprocess, re,sys,glob, yaml
from http.server import HTTPServer, BaseHTTPRequestHandler
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from .build import build_all, build

#~ G_INDEX_MODS = []
#~ G_INDEX_MOD = None
#~ G_INDEX_DATA = None


class Watchdog(FileSystemEventHandler):
	def on_modified(self, event):
		affected_pages = []
		affected_module = None
		for page, deps in Handler.deps.items():
			for d in deps:
				if d.__file__ == event.src_path:
					affected_module = d
					affected_pages.append(page)
				
		if not affected_pages:
			return
		importlib.invalidate_caches()
		importlib.reload(affected_module)
		build(affected_pages, os.path.join('.', Handler.config['out']))
		#~ for page in affected_pages:
			#~ os.remove(os.)
			
class Handler(BaseHTTPRequestHandler):
	def resp(self, code, type):
		self.send_response(code)
		self.send_header("Content-Type", type)
		self.end_headers()
	
	def do_GET(self):
		if self.path == '/':
			self.path = '/index.html'
		exti = self.path.rfind('.')
		ext = self.path[exti+1:]
		filename = os.path.join('.', Handler.config['out'], self.path[1:])
		
		#~ if not os.path.isfile(filename) and self.path[1:-5] in Handler.config['pages']:
			#~ print("REBUILD", self.path)
			#subprocess.run('python3 setup.py build min', shell=True)
			
		if ext not in ['jpg', 'png', 'css', 'js','html','json'] or not os.path.isfile(filename):
			self.resp(404, "text/html")
			self.wfile.write(("<html><head></head><body><h1>404:%s</h1></body></html"%self.path).encode())
		else:
			self.resp(200, {
				'js':'application/javascript',
				'css':'text/css',
				'png':'image/png',
				'jpg':'image/jpeg',
				'html':'text/html',
				'json':'application/json'}[ext])
			with open(filename, 'rb') as f:
				self.wfile.write(f.read())
		
def serve():
	if sys.version_info[0] < 3:
		print ("Must be using Python 3")
		sys.exit(1)
	
	Handler.config, Handler.deps = build_all()	
	host, port = Handler.config['serve'].split(':')
	
	print("Serving at http://%s:%s..."%(host, port))
	observer = Observer()
	event_handler = Watchdog()
	observer.schedule(event_handler, "./src/")
	observer.start()
	try:
		server = HTTPServer( (host,int(port)), Handler)
		server.serve_forever()
	except KeyboardInterrupt:
		pass
	print("Goodbye")
	observer.stop()
	observer.join()	
	
	