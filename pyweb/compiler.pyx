# distutils: sources = [pyweb/object.c, pyweb/set.c, pyweb/dom.c]
# distutils: include_dirs = pyweb

cimport compiler_c as cc
import re, json, os.path
from html import EL
import http.client, urllib, base64
from subprocess import Popen, PIPE, call

cdef void callback(int objid, void *f):
	(<object>f)(objid)
	
def clsname(id):
	s = ''
	while id:
		s += chr(id%26+ord('a'))
		id //= 26
	return (s+'aa')[:2]

def file_changed(filename, data):
	if not os.path.exists(filename):
		print(filename, "doesn't exist")
		return True
	with open(filename) as inf:
		filedata = inf.read()
		print(data[:20], len(data), filedata[:20], len(filedata))
		if data != filedata:
			for i in range(len(data)):
				if data[i] != filedata[i]:
					break;
			print("Different %s | %s"%(data[i-50:i+50], filedata[i-50:i+50]))
		return data != filedata

def closure_cmd(args, filenames, type='compiled_code', level="SIMPLE_OPTIMIZATIONS"):
	code = ""
	#~ for x in args:
		#~ print(x[0])
		#~ print('')
		#~ code += '\n'+x[1]
	
	print("Closure... %s"%(type))
	if type != 'compiled_code':
		return ""
	closure_jar = "/home/hegemon/.bin/closure-compiler-v20181008.jar"
	cmd = ['java','-jar', closure_jar, '--language_in','ECMASCRIPT6', '--js_output_file','/tmp/out.js']
	for f in filenames:
		cmd.append('--js')
		cmd.append(os.path.abspath(f))
	print(cmd)
	call(cmd)#, stdout=PIPE, stderr=PIPE)
	#(out,err) = cc.communicate()
	#print("--------out---------")
	#print(out)
	#print("--------ERRR---------")
	#print(err)
	with open('/tmp/out.js', encoding="utf8") as inf:
		return inf.read()
	#return out.decode('utf8')
	
def closure_http(args, filenames, type='compiled_code', level="SIMPLE_OPTIMIZATIONS"):
	print("Closure... %s"%(type))
	conn = http.client.HTTPSConnection('closure-compiler.appspot.com')
	conn.connect()
	headers = { "Content-type": "application/x-www-form-urlencoded" }
	conn.request("POST", '/compile', urllib.parse.urlencode(args+ [
			('compilation_level', level),
			('output_format', 'text'),
			('language', 'ECMASCRIPT6'),
			('formatting', 'pretty_print' if level == 'SIMPLE_OPTIMIZATIONS' else 'print_input_delimiter'),
			('output_info',type),
		]), headers)
	resp = conn.getresponse()
	if resp.status != 200:
		raise Exception("Server Error: %d"%resp.status)
	resp  = resp.read().decode("utf-8")
	return resp

class Compiler:
	def __init__(self):
		self.tags = []
		self.tagset = []
		cc.dom_reset()

	def stype(self, qid):
		q = cc.dom_get_query(qid)
		if q.type == 0:
			return "%s"%self.tags[qid]
		if q.type == 1:
			return ".%s"%clsname(qid)
		if q.type == 2:
			return "%s%s"%(self.stype(q.a), self.stype(q.b))
		if q.type == 3:
			return "%s %s"%(self.stype(q.a), self.stype(q.b))

	def add_tree(self, root):
		self.root = root
		self.modules = []
		self.classes = []
		self.objects = []
		
		def scrape_class(cls):
			if cls != object:
				scrape_class(cls.__bases__[0])
				if cls._mod not in self.modules:
					self.modules.append(cls._mod)
				if cls not in self.classes:
					self.classes.append(cls)
				
		def scrape_el(el):
			if type(el).__name__ != 'CDATA' and el not in self.objects:
				self.objects.append(el)
				el.cid = cc.obj_new(el.parent.cid if el.parent else 0)
				el.static_classes = set()
			scrape_class(el.__class__)
			for child in el.children:
				scrape_el(child)
		
		scrape_el(self.root)
		cc.set_size(len(self.objects))
	
	def create_tag_sets(self):
		self.tags = ['']
		for o in self.objects:
			if o.tag not in self.tags:
				self.tags.append(o.tag)
				cc.dom_query_new_type(0)
			tid = self.tags.index(o.tag)
			cc.dom_query_add_obj(tid, o.cid)
	
	def collect_raw_css(self):
		raw_css = ''
		for mod in self.modules:
			if 'css' in mod._extra:
				raw_css += ''.join([x.strip() for x in mod._extra['css'].split('\n')])
		for cls in self.classes:
			if 'css' in cls._extra:
				raw_css += ''.join([x.strip() for x in cls._extra['css'].split('\n')])
				
		return raw_css

	
	def collect_styles(self):
		self.styles = ['']
		for obj in self.objects:
			for name in obj.styles:
				if not name.startswith('$'):
					value, depth = obj.styles.resolved(name)
					for cond, val in value.items():
						sty = (cond, "%s:%s;"%(name, val))
						if sty not in self.styles:
							self.styles.append(sty)
							cc.dom_style_new()
						styid = self.styles.index(sty)
						cc.dom_style_add_obj(styid, obj.cid)
		#~ print("Collect_styles =============")
		#~ for s in self.styles:
			#~ print(s)
			
	def organize_selectors(self):
		scond = {}
		for i in range(1, cc.dom_num_query()+1):
			x = cc.dom_get_query(i)
			#~ cc.query_dump(i)
			if x.nsty:
				selector = self.stype(i)
				for t in range(x.nsty):
					m = self.styles[x.styles[t]]
					scond.setdefault(m[0], {})
					scond[m[0]].setdefault(selector, [])
					scond[m[0]][selector].append(m[1])
		#~ for cond in scond:
			#~ print("---- COND %s"%cond)
			#~ print(scond[cond])
		return scond
		
	def gen_css(self, scond):
		def cond_pos(c):
			if c == 'default':
				return -100
			if c.startswith('hover'):
				return 100000000
			return int(c[1:-2])
			
		css = ""
		for cond in sorted(scond.keys(), key=cond_pos):
			if cond.startswith('>'):
				css += '@media not screen and (max-width:%s){'%(cond[1:])
			for sel, styles in scond[cond].items():
				css += sel
				if cond.startswith('hover'):
					css += ':hover'
				css += '{' + ''.join(styles) + '}'
			
			if cond.startswith('>'):
				css +='}'
		return css
		
	def assign_classes(self):
		for i in range(1, cc.dom_num_query()+1):
			x = cc.dom_get_query(i)
			if x.nsty and x.type == 1:
				def addobj(objid):
					self.objects[objid-1].static_classes.add(clsname(i))
				cc.set_each(x.set, callback, <void*>addobj)
				
	def css_compile(self):
		self.collect_styles()
		cc.dom_style_resolve()
		scond = self.organize_selectors()
		css = self.gen_css(scond)
		self.assign_classes()
		css += self.collect_raw_css()
		return "<style>"+css+"</style>"
	
	
	def js_build(self):
		modules = {}
		init_classes = []
		jsdata = []
		
		def collect_class(cls, build):
			if cls != object:
				build = collect_class(cls.__bases__[0], build or 'constructor' in cls._extra)
				if build or 'js' in cls._mod._extra:
					modules.setdefault(cls._mod, {})
				if build:
					modules[cls._mod].setdefault(cls, set())
			return build
		

		def collect_obj(el, total, js):
			for child in el.children:
				total, js = collect_obj(child, total, js)
			if collect_class(el.__class__, False):
				js += 1
				modules[el.__class__._mod][el.__class__].add(el)
				try:
					el.attrs['data-i'] = init_classes.index(el.__class__)
				except:
					el.attrs['data-i']  = len(init_classes)
					init_classes.append(el.__class__)
					
			total += 1
			return total, js
			
		total, js = collect_obj(self.root, 0, 0)
		
		def write_imports(classes):
			fout = ""
			impts = {}
			for cls in classes:
				modname = cls._mod._jsfile
				impts.setdefault(modname, set())
				impts[modname].add(cls.__name__.upper())
			for impt in impts:
				fout += "import {%s} from './%s'\n"%(','.join(impts[impt]), impt)
			return fout
		
		def get_rel_path(objA, objB):
			apath = []
			while (objA):
				apath.append(objA)
				objA = objA.parent
			path = []
			while objB not in apath:
				par = objB.parent
				path.append(par.children.index(objB))
				objB = par
			path += [-1]*apath.index(objB)
			path.reverse()
			return path
		
		def jsval_to_str(obj, val):
			class Encoder(json.JSONEncoder):
				def default(self, o):
					if isinstance(o, EL):
						return {"__el__":get_rel_path(obj, o)}
					return json.JSONEncoder.default(self, o)
			val = json.dumps(val, cls=Encoder)
			return base64.b64encode(val.encode('utf8')).decode('ascii')
		
		def get_jsvars(cls):
			jvars = {}
			for o in modules[cls._mod][cls]:
				for jvar in [x[2:] for x in o.__dict__ if x.startswith('j_')]:
					jval = jsval_to_str(o, o.__dict__['j_'+jvar])
					jvars.setdefault(jvar, {})
					jvars[jvar].setdefault(jval, set())
					jvars[jvar][jval].add(o)
			return jvars
					
		
		def write_constructor(cls):
			fout = ""
			if cls == EL:
				return  'constructor(el){this.el = el;}\n'
					
			fout += 'constructor(el) {\n'
			fout += '  super(el);\n'
			class_vars = get_jsvars(cls)
			for jsvar, jsvalsd in class_vars.items():
				if len(jsvalsd) == 1:
					fout += '  this.%s = this.decode_data_value('%jsvar
					fout += '"' + jsvalsd.popitem()[0] + '");\n'
				else:
					com = None
					for val, objs in jsvalsd.items():
						if not com or len(objs)*len(val) > len(com) * len(jsvalsd[com]):
							com = val
					fout += "  this.%s = this.decode_data_value("%jsvar
					fout += " this.el.hasAttribute('data-j%s')? "%jsvar
					fout += " this.el.getAttribute('data-j%s')"%jsvar
					fout += '  : "'+com+'");\n'
			
					for val, objs in jsvalsd.items():
						if val == com:
							continue
						for obj in objs:
							obj.attrs['data-j%s'%jsvar] = val
							
			if 'constructor' in cls._extra:
				fout += cls._extra['constructor']
			return fout + '}\n\n'
			
		def write_class(cls):
			fout = '\nclass %s%s {\n'%(cls.__name__.upper(), ' extends '+cls.__bases__[0].__name__.upper() if cls != EL else "")
			fout += write_constructor(cls)
			if 'methods' in cls._extra:
				fout += cls._extra['methods']
			return fout + '}\n\n'
		
		for mod in modules:
			fout = ""
			fout += write_imports([cls.__bases__[0] for cls in modules[mod] if cls.__bases__[0] != object and cls.__bases__[0]._mod != mod])
			if 'js' in mod._extra:
				fout += mod._extra['js']
			for cls in modules[mod]:
				fout += write_class(cls)
			if len(modules[mod]):
				fout += "export { " + ','.join([cls.__name__.upper() for cls in modules[mod]]) + '};\n'
			jsdata.append( ('js_code:./'+mod._jsfile, fout) )
			
		fout = ''
		fout += write_imports(init_classes)
		fout += "function _init() {\n"
		fout += "let classes = ["+','.join([cls.__name__.upper() for cls in init_classes]) +'];\n'
		fout += """
			document.querySelectorAll("*[data-i]").forEach( (el)=> {
				el.jsobj = new classes[Number.parseInt(el.getAttribute('data-i'),10)](el);
			});
			"""
		fout += "}\nwindow['_init'] = _init;\n"
		jsdata.append( ('js_code:./_init.js', fout))
		
		return jsdata
		
		
	def js_compile(self, outdir, compile=False):
		jsdata = self.js_build()
		filenames = []
		must_build = False
		for f in jsdata:
			filenames.append(str(os.path.join(outdir, f[0].split(':')[1])))
			changed = file_changed(filenames[-1], f[1])
			changed = True
			must_build |= changed
			if changed:
				print("Writing %s..."%filenames[-1])
				with open(filenames[-1], 'w') as fout:
					fout.write(f[1])
				
		if not compile:
			return '<script type="module">' + jsdata[-1][1] + '</script>'
		else:
			if must_build:
				if call(['which', 'closure-compiler']):
					print("Closure not found, using HTTP")
					closure = closure_http
				else:
					closure = closure_cmd
				
				#closure = closure_http
				rep = closure(jsdata, filenames, type="errors")
				if rep.strip():
					print(rep)
					raise Exception("Bad JS")
				rep = closure(jsdata, filenames, type="warnings")
				level = 'SIMPLE_OPTIMIZATIONS'
				rep = closure(jsdata, filenames, type="compiled_code", level=level)
			else:
				with open('/tmp/out.js') as inf:
					rep = inf.read()
			return '<script>'+rep+'</script>'
	
	def get_py_deps(self):
		return self.modules
		deps = []
		for m in self.modules:
			if m._jsfile == 'pyweb__html.js':
				continue
			deps.append(m.__file__)
		return deps
		
	def dump(self):
		print("%d objs"%len(self.objects))
		print("%d styles"%len(self.styles))
		print(self.css)
		for o in self.objects:
			print("%r : %r"%(o, o.static_classes))
		#~ cc.dom_query_dump()
		
	def __str__(self):
		s = ""
		s += "%r"%self.tags
		return s
		