# distutils: sources = [pyweb/object.c, pyweb/set.c, pyweb/dom.c]
# distutils: include_dirs = pyweb

cimport compiler_c as cc
import re, json
from html import EL

cdef void callback(int objid, void *f):
	(<object>f)(objid)
	
def clsname(id):
	s = ''
	while id:
		s += chr(id%26+ord('a'))
		id //= 26
	return (s+'aa')[:2]


class Compiler:
	def __init__(self):
		self.tags = []
		self.tagset = []
		

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
		
		def write_constructor(cls):
			fout = ""
			if cls == EL:
				return  'constructor(el){this.el = el;}\n'
				
			def getval(val):
				if isinstance(val, str):
					return '"%s"'%(re.sub('"', '\\"', val))
				elif isinstance(val, tuple):
					return 'this.getachild(%r)'%list(val)#this.el' + ''.join(['.children[%d]'%x for x in val]) 
				else:
					return str(val)
					
			fout += 'constructor(el) {\n'
			fout += '  super(el);\n'
			for jsvar in cls._jsvars:
				#~ print("%s: %r\n"%(jsvar, cls._jsvars[jsvar]))
				if len(cls._jsvars[jsvar]) == 1:
					fout += "  this.%s = %s;\n"%(jsvar[2:], getval(cls._jsvars[jsvar].popitem()[0]))
				else:
					com = None
					for v in cls._jsvars[jsvar]:
						if not com or len(cls._jsvars[jsvar][v]) > len(cls._jsvars[jsvar][com]):
							com = v
					fout += "  this.%s = this.el.hasAttribute('data-%s')? JSON.parse(this.el.getAttribute('data-%s')): %s;\n"%(jsvar[2:], jsvar, jsvar, getval(com))
					for v in cls._jsvars[jsvar]:
						if v == com:
							continue
						for obj in cls._jsvars[jsvar][v]:
							obj.attrs['data-'+jsvar] = json.dumps(v).replace('"', '&quot;')
							
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
		
		
	def js_compile(self, outdir=""):
		jsdata = self.js_build()
		if outdir:
			for f in jsdata[:-1]:
				filename = outdir+'/'+f[0].split(':')[1]
				print("Writing %s..."%filename)
				with open(filename, 'w') as fout:
					fout.write(f[1])
			return '<script type="module">' + jsdata[-1][1] + '</script>'
		return ""
			
	
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
		