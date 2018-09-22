import subprocess, json, base64, sys
from urllib.request import urlopen
from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop

class Chrome(object):
	def __init__(self):
		self.cmdid = 1
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
	
	def on_message(self, method, params):
		print("MSG:%s"%method)
	
	def get_msg(self):
		msg = json.loads(IOLoop.current().run_sync(lambda : self.ws.read_message()))
		if 'error' in msg:
			raise Exception("Chrome Error: %r"%msg['error'])
		return msg
		
	def send(self, method, params):
		self.cmdid += 1
		payload = json.dumps({'method':method, 'id':self.cmdid, 'params':params})
		print("Sending: %s"%payload)
		self.ws.write_message(payload)
		while True:
			msg = self.get_msg()
			if 'id' in msg and msg['id'] == self.cmdid:
				break
			self.on_message("send: "+msg['method'], msg['params'])
		return msg['result']
		
	def __call__(self, method, **params):
		return self.send(method, params)
		
	def wait(self, method):
		print("Wait for %s..."%method)
		while True:
			msg = self.get_msg()
			if msg['method'] == method:
				break
			self.on_message("wait: "+msg['method'], msg['params'])
		
	def close(self):
		if self.chrome_proc.poll():
			print("Already closed")
			return
		print("Closing chrome...",end='')
		self.chrome_proc.terminate()
		self.chrome_proc.wait()
		print("Closed")
		
		
	def html2pdf(url, filename, margin=10, size=(210, 297)):
		if isinstance(margin, tuple) and len(margin) == 2:
			margin = (margin[0], margin[1], margin[0], margin[1])
		elif not (isinstance(margin, tuple) and len(margin) == 4):
			margin = (margin, margin, margin, margin)
			
		self('Page.enable')
		self('Page.navigate', url=url)
		self.wait('Page.frameStoppedLoading')
		pdf = self('Page.printToPDF', printBackground=True, displayHeaderFooter=False,
			paperWidth=size[0]/25.4, paperHeight=size[1]/25.4, 
			marginTop=margin[0]/25.4, marginRight=margin[1]/25.4, marginBottom=margin[2]/25.4, marginLeft=margin[3]/25.4)
		print("Writing %s..."%filename)
		with open(filename, 'wb') as f:
			f.write(base64.b64decode(pdf['data']))


def html2pdf():
	try:
		url = sys.argv[1]
		if len(sys.argv) > 2:
			filename = sys.argv[2]
		else:
			mtch = re.match(".*?/?([a-zA-Z0-9 _]*)\.html")
			if mtch:
				filename = mtch.group(1)
			else:
				filename = 'output'
	except:
		print("Usage: pyweb-pdf URL [OUTPUT]\n\tpyweb-pdf localhost:8080 bob.pdf\n\tpyweb-pdf products.html")
	
	chrome = Chrome()
	chrome.pdf(url, filename+'.pdf')
	chrome.close()
	
