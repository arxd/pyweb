from http.server import HTTPServer, BaseHTTPRequestHandler
import importlib, sys, traceback, os.path, json
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import tornado.web
from tornado.ioloop import IOLoop
import tornado.httpserver


APP = None
#~ APP_MOD = None
#~ APP_NAME = sys.argv[1]

HTML ="""<!DOCTYPE html>
<html lang="%s">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, minimum-scale=1, initial-scale=1, user-scalable=yes">
<link href="images/favicon.png" rel="icon" type="image/png">
<title>%s</title>
<script>
window.EL = function(tag, text="", c=[], cls="", style="")
{
	var el = document.createElement(tag);
	if (cls)
		el.className = cls;
	if (style)
		el.style = style;
	if (text)
		el.appendChild(document.createTextNode(text));
	for (let i=0; i < c.length; ++i)
		el.appendChild(c[i]);
	return el;
}

window.DIV = function(cls, text, c=[], style="")
{
	return EL("div", text=text, c=c, cls=cls, style=style);
}

window.CALL = function(method, args, callback) 
{
	var xhr = new XMLHttpRequest();
	xhr.open("POST",method, true);
	xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
	xhr.onreadystatechange = function () {
		if(xhr.readyState === XMLHttpRequest.DONE) {
			if( xhr.status === 200) {
				if (callback)
					callback(JSON.parse(xhr.responseText));
			} else {
				alert(xhr.responseText);
			}
		}
	};
	xhr.send(JSON.stringify(args));
}

window.CSS = function(href)
{
	var s = document.createElement('link');
	s.setAttribute('type', 'text/css');
	s.setAttribute('rel', 'stylesheet');
	s.setAttribute('href', href);
	document.head.appendChild(s);
}

</script>
<script type="module">
import "/client.js";
</script>

</head>
<body onload="window.main()">
</body>
</html>
"""
class BaseHandler(tornado.web.RequestHandler):
	def resp(self, code, ext):
		self.set_status(code)
		self.set_header("Content-Type", {
				'js':'application/javascript',
				'mjs':'application/javascript',
				'css':'text/css',
				'png':'image/png',
				'jpg':'image/jpeg',
				'html':'text/html',
				'json':'application/json'}[ext])
		self.set_header("Cache-Control","no-cache, must-revalidate")
		self.set_header("Pragma", "no-cache")
		self.set_header("Expires", "Sat, 26 Jul 1997 05:00:00 GMT")
		#self.end_headers()
	
	def get(self, path):
		ext = path.rfind('.')
		if ext < 0:
			self.resp(200, "html")
			self.finish(Handler.html.encode('utf8'))
			return

		ext = path[ext+1:]
		filename = os.path.join(Handler.base, path[1:])
		if ext not in ['jpg', 'png', 'css', 'js','html','json', 'mjs'] or not os.path.isfile(filename):
			self.resp(404, "html")
			self.finish(("<html><head></head><body><h1>404:%s</h1><h2>%s</h2></body></html>"%(path,filename)).encode('utf8'))
		else:
			self.resp(200, ext)
			with open(filename, 'rb') as f:
				self.finish(f.read())


class Handler(BaseHTTPRequestHandler):
	def resp(self, code, ext):
		self.send_response(code)
		self.send_header("Content-Type", {
				'js':'application/javascript',
				'mjs':'application/javascript',
				'css':'text/css',
				'png':'image/png',
				'jpg':'image/jpeg',
				'html':'text/html',
				'json':'application/json'}[ext])
		self.send_header("Cache-Control","no-cache, must-revalidate")
		self.send_header("Pragma", "no-cache")
		self.send_header("Expires", "Sat, 26 Jul 1997 05:00:00 GMT")
		self.end_headers()
		
	def do_GET(self):
		path = self.path.split('?')[0]
		ext = path.rfind('.')
		if ext < 0:
			self.resp(200, "html")
			self.wfile.write(Handler.html.encode())
			return

		ext = path[ext+1:]
		filename = os.path.join(Handler.base, path[1:])
		if ext not in ['jpg', 'png', 'css', 'js','html','json', 'mjs'] or not os.path.isfile(filename):
			self.resp(404, "html")
			self.wfile.write(("<html><head></head><body><h1>404:%s</h1><h2>%s</h2></body></html>"%(path,filename)).encode())
		else:
			self.resp(200, ext)
			with open(filename, 'rb') as f:
				self.wfile.write(f.read())

	#~ def do_POST(self):
		#~ if RELOAD:
			#~ reload()
		#~ r = self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8')
		#~ args = json.loads(r)
		#~ try:
			#~ resp = getattr(APP, "rpc_"+self.path[1:])(**args)
			#~ self.resp(200, "application/json")
			#~ self.wfile.write(json.dumps(resp).encode())
		#~ except Exception:
			#~ self.resp(500, "application/json")
			#~ tb = traceback.format_exc()
			#~ print("-"*60)
			#~ print(tb)
			#~ print("-"*60)
			#~ self.wfile.write(tb.encode())

def app_serve():
	global APP
	sys.path = ['.'] + sys.path
	APP = importlib.import_module('server')
	varnames = APP.Server.__init__.__code__.co_varnames[1:]
	defaults = APP.Server.__init__.__defaults__

	def argval(arg):
		if ',' in arg:
			return [argval(x) for x in arg.split(',') if x.strip()]
		try:
			return float(arg)
		except:
			return arg.strip()
		
	args = {}
	for d in range(len(defaults)):
		args.setdefault(varnames[-len(defaults)+d], defaults[d])
	# positional args
	i = 1
	while i < len(sys.argv) and '=' not in sys.argv[i]:
		args[varnames[i-1]] = argval(sys.argv[i])
		i += 1
	# kw args
	for arg in sys.argv[i:]:
		name,val = arg.split('=')
		args[name] = argval(val)
	
	if set(varnames) != set(args.keys()):
		vars = [x if i < len(varnames) - len(defaults) else '[%s]'%x for i, x in enumerate(varnames)]
		print("Usage: pyweb-app %s"% ' '.join(vars))
		sys.exit(1)
		
	app = APP.Server(**args)
	title = 'pyweb-app' if not hasattr(app, 'title') else app.title
	lang = 'ja-JP' if not hasattr(app, 'lang') else app.lang
	host,port = ('localhost:8080' if not hasattr(app, 'host') else app.host).split(':')
	Handler.html = HTML%(lang,title)
	Handler.base = os.path.abspath('.')
	
	application = tornado.web.Application([("(.*)", BaseHandler)])
	server =  tornado.httpserver.HTTPServer(application)
	server.listen(int(port), address=host)
	print("Serving http://%s:%s..."%(host, port))
	IOLoop.current().start()
	
	#~ server = HTTPServer( (host,int(port)), Handler)
	#~ try:
		#~ server.serve_forever()
	#~ except KeyboardInterrupt:
		#~ print("\b\b",end='')