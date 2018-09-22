import subprocess, json, base64
from urllib.request import urlopen
from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop

class Chrome(object):
	def __init__(self):
		self.cmdid = 1
		self.events = []
		print("Starting chrome... ",end='')
		self.chrome_proc = subprocess.Popen(['google-chrome-stable', '--headless', '--remote-debugging-port=0'], stderr=subprocess.PIPE)
		x = None
		port = ''
		while True:
			c = self.chrome_proc.stderr.read(1).decode()
			if c != ':':
				continue
			port = self.chrome_proc.stderr.read(1).decode()
			if port in '123456789':
				break
		while True:
			c = self.chrome_proc.stderr.read(1).decode()
			if c == '/':
				break
			port += c
		print(port)
		self.port = int(port)

		with urlopen('http://localhost:%d/json'%self.port, timeout=5) as f:
			resp = json.loads(f.read().decode('utf-8'))[0]
			self.ws = resp['webSocketDebuggerUrl']
			print("Connecting to websocket:  %s"%self.ws)
			self.ws = IOLoop.current().run_sync(lambda : websocket_connect(self.ws))
	
	def protocol(self):
		with urlopen('http://localhost:%d/json/protocol'%self.port) as f:
			resp = json.loads(f.read().decode('utf-8'))
			print(resp['version'])
			dom = resp['domains']
			page = None
			for d in dom:
				if d['domain'] == 'Page':
					page = d
				#~ print("%s:%s"%(d['domain'], d['description'] if 'description' in d else ''))
				
			#~ print(page['events'])
			#~ print(page['types'])
			for c in page['commands']:
				print("%30s: %s"%(c['name'], c['description'] if 'description' in c else ''))
	
	def get_msg(self, prefix=''):
		msg = json.loads(IOLoop.current().run_sync(lambda : self.ws.read_message()))
		if 'error' in msg:
			raise Exception("Chrome Error: %r"%msg['error'])
		self.events.append(msg)

		if 'method' in msg:
			if msg['method']=='Page.lifecycleEvent':
				print("MSG:%s: Page.lifecycleEvent: %s"%(prefix, msg['params']['name']))
			else:
				print("MSG:%s: %s"%(prefix, msg['method']))
		else:
			print("MSG:Response %d"%msg['id'])
		return msg
		
	def send(self, method, params):
		self.cmdid += 1
		payload = json.dumps({'method':method, 'id':self.cmdid, 'params':params})
		print("Sending: %s"%payload)
		self.ws.write_message(payload)
		while True:
			msg = self.get_msg('send')
			if 'id' in msg and msg['id'] == self.cmdid:
				break
		return msg['result']
		
	def __call__(self, method, **params):
		return self.send(method, params)
	
	def lifecycle(self, name):
		for evt in self.events:
			if 'method' in evt and evt['method'] == 'Page.lifecycleEvent' and evt['params']['name'] == name:
				print("%s already fired"%name)
				return
		print("Wait for lifecycle %s..."%name)
		while True:
			msg = self.get_msg('lifecycle')
			if msg['method'] == 'Page.lifecycleEvent' and msg['params']['name'] == name:
				break
	
	def wait(self, method):
		for evt in self.events:
			if 'method' in evt and evt['method'] == method:
				print("%s already fired"%method)
				return
		print("Wait for %s..."%method)
		while True:
			msg = self.get_msg('wait')
			if msg['method'] == method:
				break
			
	def close(self):
		if self.chrome_proc.poll():
			print("Already closed")
			return
		print("Closing chrome...",end='')
		self.chrome_proc.terminate()
		self.chrome_proc.wait()
		print("Closed")
		
		
	def pdf(self, url, filename, margin=10, size=(210, 297)):
		if isinstance(margin, tuple) and len(margin) == 2:
			margin = (margin[0], margin[1], margin[0], margin[1])
		elif not (isinstance(margin, tuple) and len(margin) == 4):
			margin = (margin, margin, margin, margin)
		
		#~ self('Network.enable')
		self('Page.enable')
		self('Page.setLifecycleEventsEnabled', enabled=True)
		self('Page.navigate', url=url)
		self.events = []
		self.wait('Page.frameStoppedLoading')
		self.lifecycle('networkIdle')
		pdf = self('Page.printToPDF', printBackground=True, displayHeaderFooter=False,
			paperWidth=size[0]/25.4, paperHeight=size[1]/25.4, 
			marginTop=margin[0]/25.4, marginRight=margin[1]/25.4, marginBottom=margin[2]/25.4, marginLeft=margin[3]/25.4)
		print("Writing %s..."%filename)
		with open(filename, 'wb') as f:
			f.write(base64.b64decode(pdf['data']))
		
		#~ while True:
			#~ self.get_msg('end')


def html2pdf():
	import sys, os.path
	try:
		url = sys.argv[1]
		if ':' in url:
			if not url.endswith('/'):
				url += '/'
			filename = url[url.find('/')+1:].replace('/', '_')
			if not filename:
				filename = 'index'
			url = 'http://'+url
		else:
			filename = url
			url = 'file://'+os.path.abspath(url)
			
		if filename.endswith('.html'):
			filename = filename[:-5]
		filename += '.pdf'
		if len(sys.argv) > 2:
			filename = sys.argv[2]

	except Exception as e:
		print("Usage: pyweb-pdf URL [OUTPUT]\n\n\tpyweb-pdf localhost:8080 bob.pdf\n\tpyweb-pdf products.html")
		raise e
		
	chrome = Chrome()
	chrome.pdf(url, filename)
	chrome.close()
	
