import importlib,  traceback, os, os.path, json, subprocess, re,sys,glob, yaml, shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from .build import build_all, build

#~ G_INDEX_MODS = []
#~ G_INDEX_MOD = None
#~ G_INDEX_DATA = None


class Watchdog(FileSystemEventHandler):
	def on_modified(self, event):
		outdir = os.path.abspath(os.path.join('.', Handler.config['out']))
		affected_pages = []
		#~ affected_modules = set()
		for page, deps in Handler.deps.items():
			for d in deps:
				if d.__file__ == event.src_path:
					#~ affected_module = d
					affected_pages.append(page)
		
		if affected_pages:
			for page in affected_pages:
				for p in Handler.config['pages']:
					if p in page.__file__:
						break
				filename = os.path.join(outdir, p+'.html')
				print("Removing %s"%filename)
				try:
					os.remove(filename)
				except:
					pass
					
		elif event.src_path == './pyweb_config.yaml':
			subprocess.call("pyweb-build", shell=True)
			
		else:
			changed = os.path.abspath(event.src_path)
			for xtra in Handler.config['extra']:
				xtra = os.path.abspath(xtra)
				if changed.startswith(xtra):
					cpyfrom = changed[xtra.rfind('/')+1:]
					cpyto = outdir
					print("Copy %s -> %s"%(cpyfrom, cpyto))
					shutil.copy2(cpyfrom, cpyto)
					break
				
			#~ changed = os.path.abspath(event.src_path)
			#~ print(changed)
		#~ for page in affected_pages:
			#~ os.remove(os.)
			
class Handler(BaseHTTPRequestHandler):
	def resp(self, code, type):
		self.send_response(code)
		self.send_header("Content-Type", type)
		self.end_headers()
	
	def do_GET(self):
		path = self.path.split('?')[0]
		if path == '/':
			path = '/index.html'
		ext = path.rfind('.')
		if ext < 0:
			ext = 'html'
			path += '.html'
		else:
			ext = path[ext+1:]
			
		filename = os.path.join('.', Handler.config['out'], path[1:])
		print(filename, ext, path)
		
		if not os.path.isfile(filename) and path[1:-5] in Handler.config['pages']:
			print("REBUILD", path)
			subprocess.run('pyweb-build %s'%path[1:-5], shell=True)
			
		if ext not in ['jpg', 'png', 'css', 'js','html','json'] or not os.path.isfile(filename):
			self.resp(404, "text/html")
			self.wfile.write(("<html><head></head><body><h1>404:%s</h1></body></html>"%path).encode())
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
	
	sys.path = ['./src'] + sys.path
	with open("pyweb_config.yaml", 'r') as config:
		Handler.config = yaml.load(config)
	
	Handler.deps = build_all(Handler.config)
	host, port = Handler.config['serve'].split(':')
	
	print("Serving at http://%s:%s..."%(host, port))
	observer = Observer()
	event_handler = Watchdog()
	observer.schedule(event_handler, "./", recursive=True)
	#~ watches = set(['./src/'])
	#~ for watch in  Handler.config['extra']:
		#~ print(watch)
		#~ print(os.path.dirname(os.path.abspath(watch)))
	observer.start()
	try:
		server = HTTPServer( (host,int(port)), Handler)
		server.serve_forever()
	except KeyboardInterrupt:
		pass
	print("Goodbye")
	observer.stop()
	observer.join()	
	
	