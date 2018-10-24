import subprocess, json, base64
from urllib.request import urlopen
from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop
from tornado.util import TimeoutError
import time
from PIL import Image
from io import BytesIO

class DOMNode(object):
	def __init__(self, chrome, nodeId=0, backendId=0, parent=None):
		self.chrome = chrome
		self.nodeId = nodeId
		self.backendId = backendId
		self.parent = parent
		if nodeId == 0 and backendId == 0:
			self.nodeId = self.chrome('DOM.getDocument')['root']['nodeId']
		self.data = self._call('DOM.describeNode', depth=1, pierce=True)['node']
		#if self.nodeId == 0:
		#	self.data = self.chrome(, backendNodeId=self.backendId, )
		#else:
		#	self.data = self.chrome('DOM.describeNode', nodeId=self.nodeId, depth=1, pierce=True)['node']
		
		#print(repr(self))
		self.nodeName = self.data['nodeName']
		self.backendId = self.data['backendNodeId']
		self.attributes = {}
		if 'attributes' in self.data:
			for i in range(0, len(self.data['attributes']),2):
				self.attributes[self.data['attributes'][i]] = self.data['attributes'][i+1]

		if self.chrome.verbose >= 2:
			print("DOMNode: %s"%self)

	def __getitem__(self, item):
		try:
			if isinstance(item, int):
				return self.child(item)
			return self.attr(item)
		except:
			return None

	def __getattr__(self, attr):
		if attr == 'children':
			self.children = []
			for cld in self.data['children']:
				if cld['nodeType'] == 1:
					self.children.append(DOMNode(self.chrome, cld['nodeId'], cld['backendNodeId'], self))
				elif cld['nodeType'] == 3:
					self.children.append(cld['nodeValue'])
				else:
					if self.chrome.verbose >= 2:
						print("Skipping: %r"%cld)
			return self.children
	def __iter__(self):
		return iter(self.children)

	def _call(self, dest, **kwargs):
		if self.backendId == 0:
			kwargs['nodeId'] = self.nodeId
		else:
			kwargs['backendNodeId'] = self.backendId
		return self.chrome(dest, **kwargs)

	def pos(self):
		#try:
			#content = self._call('DOM.getBoxModel')['model']['content']
			#print("CONTETN", content)
		quad = self._call('DOM.getContentQuads')['quads']
		print("QUADS : %s"%self, quad)
		if not quad:
			quad = [[0,0,0,0]]
		quad = quad[0]

		#except:
		#	print("No box model for %s"%self)
		#	return {'x':0,'y':0,'w':0,'h':0}
		return {
			'x':int(quad[0]),
			'y':int(quad[1]),
			'w':int(quad[2]-quad[0]),
			'h':int(quad[5] - quad[1])}

	def attr(self, key):
		return self.attributes[key]
	
	def wait(self,timeout=1):
		self.chrome.wait(timeout)
		return self

	def scroll_to(self):
		pos = self.pos()
		self.scroll(pos['y']-300)
		return self

	def scroll(self, dist=40000):
		now = time.time()
		pos = self.pos()
		#y = int(pos['y'] + pos['h']/2)

		print("SCROLL %s %s %s"%(self, dist, pos))
		for i in range(1):
			self.chrome('Input.dispatchMouseEvent', 
				type='mouseWheel',
				timestamp=now+0.2*i,
				x=int(pos['x'] + pos['w']/2), 
				y=300,
				deltaY = dist,
				deltaX = 0)
		return self

	def click(self, btn='left'):
		pos = self.pos()
		x = int(pos['x']+pos['w']/2)
		y = int(pos['y']+pos['h']/2)
		now = time.time()
		if self.chrome.verbose >= 1:
			print("CLICK %s %s"%(self,pos))
		self.chrome('Input.dispatchMouseEvent',type="mousePressed", clickCount=1, button=btn, timestamp=now, x=x, y=y)
		self.chrome('Input.dispatchMouseEvent',type="mouseReleased", button=btn, timestamp=now+0.1, x=x, y=y)
		return self

	def focus(self):
		self._call('DOM.focus')
		return self

	def child(self, idx):
		return self.children[idx]

	def query(self, selector):
		nodes = []
		for nodeId in self.chrome('DOM.querySelectorAll', nodeId=self.nodeId, selector=selector)['nodeIds']:
			nodes.append(DOMNode(self.chrome, nodeId))
		return nodes

	def __str__(self):
		#print(self.data)
		atrs = ''
		for kv in self.attributes.items():
			atrs += ' %s="%s"'%kv
		atrs = ' '+atrs if atrs else ''
		nchildren = self.data['childNodeCount'] if 'childNodeCount' in self.data else 0
		return '%d.%d:<%s%s>[%d]'%(self.nodeId, self.backendId, self.nodeName, atrs,nchildren)

	def outerHTML(self):
		if self.nodeId == 0:
			return self.chrome('DOM.getOuterHTML', backendNodeId=self.backendId)['outerHTML']
		return self.chrome('DOM.getOuterHTML', nodeId=self.nodeId)['outerHTML']


class Chrome(object):
	def __init__(self, verbose=1, port=0):
		self.verbose = verbose
		self.cmdid = 1
		self.events = []
		self.port = port
		self.chrome_proc = None
		if not port:
			if self.verbose >= 1:
				print("Starting chrome... ",end='')		
			cmd = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
			cmd += ['--headless']
			cmd += ['--remote-debugging-port=0']
			cmd += [
				'--enable-surface-synchronization',
				'--run-all-compositor-stages-before-draw',
				'--disable-threaded-animation',
				'--disable-threaded-scrolling',
				'--disable-checker-imaging',]

			self.chrome_proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
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
			if self.verbose >= 1:
				print(port)
		
		self.port = int(port)

		if self.verbose >= 1:
			print ("Connecting to websocket @ %d"%self.port)
		with urlopen('http://localhost:%d/json'%self.port, timeout=5) as f:
			resp = json.loads(f.read().decode('utf-8'))[0]
			self.ws = resp['webSocketDebuggerUrl']
			self.ws = IOLoop.current().run_sync(lambda : websocket_connect(self.ws))
	
		#self.getinfo()
		#self.kill()

		self('Page.enable')
		self('DOM.enable')
		self('Network.enable')
		#self('DOMSnapshot.enable')
		#self('HeadlessExperimental.enable')
		self('Page.setLifecycleEventsEnabled', enabled=True)
		#self.resize(500,500)

	def __enter__(self):
		return self
	
	def __exit__(self, *args):
		self.close()

	def resize(self, w, h):
		target = self('Target.getTargets')['targetInfos'][0]
		print(target)
		#wid = self('Browser.getWindowForTarget', targetId=target['targetId'])
		#print("Current size: ", wid['bounds'])
		#,windowId=wid['windowId']
		self('Browser.setWindowBounds', bounds={'width':w,'height':h})

	def getinfo(self):
		self('SystemInfo.getInfo')

	def keyboard(self, msg):
		now = time.time()
		print("Typing %s..."%msg)
		for k in msg:
			if k == '\t':
				self('Input.dispatchKeyEvent', type="rawKeyDown",timestamp = now, code="Tab", key="Tab")
			else:
				self('Input.dispatchKeyEvent', type="char",timestamp = now, text=k)
			now += 0.1
		return self
		
	def get_msg(self, prefix='', timeout=1):
		try:
			msg = IOLoop.current().run_sync(lambda : self.ws.read_message(), timeout=timeout)
		except TimeoutError:
			if self.verbose >= 2:
				print("Timeout")
			return None
		msg = json.loads(msg)
		if 'error' in msg:
			raise Exception("Chrome Error: %r"%msg['error'])
		self.events.append(msg)

		if self.verbose >= 3:
			if 'method' in msg:
				if msg['method']=='Page.lifecycleEvent':
					print("MSG:%s: Page.lifecycleEvent: %s"%(prefix, msg['params']['name']))
				else:
					print("MSG:%s: %s"%(prefix, msg['method']))
			else:
				print("MSG:Response %d"%msg['id'])
		return msg
	
	def scroll_to(self, dom):
		pos = dom.pos()
		self.query('body')[0].scroll(pos['y']-300)

	def screenshot(self, filename=None, show=False):
		imgdata = base64.b64decode(self('Page.captureScreenshot')['data'])
		if filename:
			with open(filename, 'wb') as ofile:
				ofile.write(imgdata)
			if not show:
				return
		img = Image.open(BytesIO(imgdata))
		print(img)
		img.show()
	
	def get_cookies(self):
		return self('Network.getAllCookies')['cookies']

	def set_cookies(self, cookies):
		self('Network.setCookies',cookies=cookies)

	def send(self, method, params):
		self.cmdid += 1
		payload = json.dumps({'method':method, 'id':self.cmdid, 'params':params})
		if self.verbose >= 2:
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
		if self.verbose >= 2:
			print("Wait for lifecycle %s..."%name)
		while True:
			msg = self.get_msg('lifecycle')
			if msg['method'] == 'Page.lifecycleEvent' and msg['params']['name'] == name:
				break
	
	def wait_on(self, method):
		for evt in self.events:
			if 'method' in evt and evt['method'] == method:
				print("%s already fired"%method)
				return
		if self.verbose >= 2:
			print("Wait for %s..."%method)
		while True:
			msg = self.get_msg('wait')
			if msg['method'] == method:
				break

	def query(self, selector):
		return DOMNode(self).query(selector)			
	
	def navigate(self, url):
		if self.verbose >= 1:
			print("Navigate: %s"%url)
		nav = self('Page.navigate', url=url)
		if 'errorText' in nav:
			raise Exception(nav['errorText'])
		self.frameId = nav['frameId']
		self.events = []
		self.wait()
		#self.waiton('Page.frameStoppedLoading')
		#self.lifecycle('networkIdle')
		return self

	def kill(self):
		self('Page.crash')
		target = self('Target.getTargets')['targetInfos']
		print(target)
		
	def wait(self, timeout=1):
		while self.get_msg(timeout=timeout):
			pass
		return self

	def show_page(self):
		def show_node(node, depth=0):
			print("%s%s"%('   '*depth, node))
			if isinstance(node, str):
				return
			for c in node.children:
				show_node(c, depth+1)

		show_node(DOMNode(self))
		#dom = self('DOMSnapshot.captureSnapshot', computedStyles=[])
		#print(dom['strings'])
		#print('')
		#print(dom['documents'])
		#for nt in dom['documents'][0]['nodes']['nodeType']:
		#	print(dom['strings'][nt])
		#	print("---------------")

	def save_to_disk(self, url, filename):
		obj = self('Page.getResourceContent', frameId=self.frameId, url=url)
		if obj['base64Encoded']:
			if self.verbose >= 1:
				print("Writing binary to '%s'"%filename)
			with open(filename, 'wb') as of:
				of.write(base64.b64decode(obj['content']))
		else:
			if self.verbose >= 1:
				print("Writing text to '%s'"%filename)
			with open(filename, 'w', encoding='utf-8') as of:
				of.write(obj['content'])

	def pdf(self, filename, margin=10, size=(210, 297)):
		if isinstance(margin, tuple) and len(margin) == 2:
			margin = (margin[0], margin[1], margin[0], margin[1])
		elif not (isinstance(margin, tuple) and len(margin) == 4):
			margin = (margin, margin, margin, margin)
		
		pdf = self('Page.printToPDF', printBackground=True, displayHeaderFooter=False,
			paperWidth=size[0]/25.4, paperHeight=size[1]/25.4, 
			marginTop=margin[0]/25.4, marginRight=margin[1]/25.4, marginBottom=margin[2]/25.4, marginLeft=margin[3]/25.4)
		print("Writing %s..."%filename)
		with open(filename, 'wb') as f:
			f.write(base64.b64decode(pdf['data']))
		
		#~ while True:
			#~ self.get_msg('end')
	def close_websocket(self):
		print("Closing websocket...")
		self.ws.close()


	def close(self):
		self.close_websocket()
		if not self.chrome_proc:
			return
		if self.chrome_proc.poll():
			print("Already closed")
			return
		if self.verbose >= 1:
			print("Closing chrome...",end='')
		self.chrome_proc.terminate()
		self.chrome_proc.wait()
		if self.verbose >= 1:
			print("Closed")

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

	except:
		print("Usage: pyweb-pdf URL [OUTPUT]\n\n\tpyweb-pdf localhost:8080 bob.pdf\n\tpyweb-pdf products.html")
		sys.exit(1)
		
	chrome = Chrome()
	chrome.pdf(url, filename)
	chrome.close()
	
