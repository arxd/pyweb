import re, sys, inspect, json, urllib, http,traceback
from functools import reduce
from .style import Styles

def parse_doc(obj):
	sections = {}
	if obj.__doc__:
		match = re.split(r'#=+(.*?)=.*', obj.__doc__, re.M)
		for m in range(1, len(match),2):
			sections[match[m].strip().lower()] = match[m+1].strip()
	return sections

g_element_stack = []

class MetaElement(type):
	def __init__(cls, *args, **kwargs):
		cls._extra = parse_doc(cls)
		cls._mod = inspect.getmodule(cls)
		cls._jsvars = {}
		cls._nobjs = 0
		if not hasattr(cls._mod, '_extra'):
			cls._mod._extra = parse_doc(cls._mod)
			cls._mod._jsfile = re.sub('/','__',cls._mod.__file__[cls._mod.__file__.rfind('/src/')+5:-3]) +'.js'
			if cls._mod._jsfile.endswith('pyweb__html.js'):
				cls._mod._jsfile = 'pyweb__html.js'

	def __call__(cls, *args, **kwargs):
		global g_element_stack
		self = cls.__new__(cls, *args, **kwargs)
		cls._nobjs += 1
		self.tag = 'unk'
		self.id = ''
		self.parent = None
		self.attrs = {}
		self.style = {}
		self.styles = Styles(self)
		self.classes = set()
		self._classes = []
		self.space_after = None
		self.inline_style = ''
		self.children = []
		if g_element_stack:
			g_element_stack[-1].append(self)
		g_element_stack.append(self)
		self.__init__(*args, **kwargs)
		for p in filter(lambda x: x.startswith('j_'), self.__dict__):
			v = self.__dict__[p]
			if isinstance(v, EL):
				def find_child(el):
					for ci, child in enumerate(el.children):
						if child == v:
							return [ci]
						child = find_child(child)
						if child:
							return [ci] + child
					return []
				v = tuple(find_child(self))
			elif not (isinstance(v, int) or isinstance(v, str)):
				raise Exception("bad value '%s':%s"%(v, type(v)))
				
			cls._jsvars.setdefault(p, {})
			cls._jsvars[p].setdefault(v, set())
			cls._jsvars[p][v].add(self)
		
		g_element_stack.pop()
		return self


class EL(metaclass=MetaElement):
	"""#== methods ==#
		getachild(path) {
			let el = this.el;
			for(let p in path)
				el = el.children[path[p]];
			return el;
		}
	"""
	def __init__(self, tag="unk!", id="", c=[], space_after=None, text=None, **kwargs):
		self.tag = tag
		self.id = id
		self.space_after = space_after
		
		def apply_default_styles(cls):
			for b in cls.__bases__:
				if issubclass(b, EL) and b != EL:
					apply_default_styles(b)
			if 'style' in cls._extra:
				#~ self.set_style(cls._extra['style'])
				self.styles.set(cls._extra['style'], cls.__name__+"'s doc")
		apply_default_styles(self.__class__)
		
		for k in kwargs:
			if k == 'style':
				#~ self.set_style(kwargs[k])
				self.styles.set(kwargs[k], self.__class__.__name__+' inline')
			elif k == 'classes':
				self.set_class(kwargs[k])
			else:
				self.attrs[k] = kwargs[k]

		if text is not None:
			self.append(CDATA(text))
			
		for child in c:
			self.append(child)
		
	def append(self, child):
		if child.parent:
			del child.parent.children[child.parent.children.index(child)]
		assert(child not in self.children)
		child.parent = self
		self.children.append(child)
	
	def render(self, debug=False, depth=0):
		if len(self.children) == 1 and isinstance(self.children[0], CDATA):
			s = self.start_tag(False)
			s += self.children[0].render()
		else:
			s = self.start_tag(debug)
			prev_child = None
			for child in self.children:
				if debug and (not prev_child or prev_child.space_after != False):
					s += '\n'+'  '*(depth+1 if debug else 0)
				elif debug and prev_child.space_after == False:
					s += '<!--\n'+'  '*(depth-1 if debug else 0) +' -->'
				s += child.render(debug, depth+1)
				prev_child = child
			s += ('\n' + '  '*depth if debug else '')
		s += "</%s>"%self.tag + (' ' if self.space_after else '')
		return s
		
	def start_tag(self, debug=True):
		s = "<%s"%self.tag
		if self.id:
			s += ' id="%s"'%self.id
		for a in self.attrs:
			s += ' %s="%s"'%(a,self.attrs[a])
		clsstr = ' '.join(self.static_classes)
		if clsstr:
			s += ' class="%s"'%(clsstr,)
		if self.inline_style:
			s += ' style="%s"'%(self.inline_style)
		s += '>%s'%('<!--%s %d-->'%(self.__class__.__name__, self.cid) if debug else '')
		return s
		
	def __str__(self):
		return self.start_tag()


class HTML(EL):
	""" #== Style ==#
	border: 0;
	margin: 0;
	font-size:100%;
	"""
	def __init__(self, 
				title="No Title", 
				favicon="", 
				lang='ja-JP', 
				stylesheets=[], 
				javascript=[], onload='window._init()', **kwargs):
		super().__init__(tag='body', onload=onload, **kwargs)
		self.stylesheets = stylesheets
		self.javascript = javascript
		self.title = title
		self.favicon = favicon
		self.lang = lang
	
	def render(self, debug=0, depth=0):
		nl = '' if not debug else '\n'
		s = '<!DOCTYPE html>'+nl
		s += '<html lang="%s">'%(self.lang) +nl
		s += '<head>'+nl
		s += '<meta charset="utf-8">' +nl
		s += '<title>%s</title>'%(self.title) +nl
		s += '<meta name="viewport" content="width=device-width, minimum-scale=1, initial-scale=1, user-scalable=yes">' +nl
		s += '<link href="%s" rel="icon" type="image/png">'%(self.favicon) +nl
		for ss in self.stylesheets:
			s += '<link rel="stylesheet" href="%s">'%(ss) +nl
		for js in self.javascript:
			s += '<script src="%s"></script>'%js
		s += self.inline_css
		s += self.inline_js
		s += super().render(debug, 0) +nl
		s += '</html>' +nl
		return s


class CDATA(EL):
	def __init__(self, text, **kwargs):
		super().__init__(tag='!string!', **kwargs)
		self.text = str(text)
	
	def append(self, child):
		raise Exception("String can't have children %r"%child)
	
	def render(self, debug=0, depth=0):
		return self.text

	def __str__(self):
		return "CDATA:[%s%s]"%('' if not hasattr(self, 'text') else self.text[:20], ('...%d'%len(self.text)) if len(self.text) > 20 else '')


class BR(EL):
	def __init__(self, **kwargs):
		kwargs.setdefault('tag','br')
		kwargs.setdefault('space_after',False)
		super().__init__(**kwargs)
		
	def append(self, child):
		raise Exception("BR can't have children")

	def render(self, debug=0, depth=0):
		return self.start_tag(debug=False)

	
class FLEX(EL):
	def __init__(self, dir='row', reverse=False, wrap=False, justify="space-around", align="center", **kwargs):
		self.styles.set('display:flex;flex-direction:%s%s;'%(dir, '-reverse' if reverse else ''))
		self.styles.set('justify-content:%s;align-items:%s;'%(justify, align))
		if wrap:
			self.styles.set('flex-wrap:wrap;')
		kwargs.setdefault('tag','div')
		super().__init__(**kwargs)


class IDIV(EL):
	""" #== Style ==#
	display:inline-block;
	"""
	def __init__(self, **kwargs):
		kwargs.setdefault('tag','div')
		kwargs.setdefault('space_after', False)
		super().__init__(**kwargs)


class DIV(EL):
	def __init__(self, **kwargs):
		kwargs.setdefault('tag', 'div')
		super().__init__(**kwargs)


class SPAN(EL):
	def __init__(self, **kwargs):
		kwargs.setdefault('tag', 'span')
		super().__init__(**kwargs)


class P(EL):
	def __init__(self, **kwargs):
		kwargs.setdefault('tag','p')
		super().__init__(**kwargs)	


class A(EL):
	"""#==Style==#
	text-decoration:none;
	color:inherit;
	"""
	def __init__(self, href="", **kwargs):
		kwargs.setdefault('tag','a')
		kwargs.setdefault('href', href)
		super().__init__(**kwargs)
		self.j_id = id(self)
		self.j_href = href

class DIMG(DIV):
	"""#==Style==#
		background-position: top;
		background-repeat:no-repeat;
		background-size:100% auto;
	"""
	def __init__(self, src="", **kwargs):
		self.src = src
		self.styles.set('background-image:url("%s")'%src)
		super().__init__(**kwargs)


class IMG(EL):
	def __init__(self, src="", alt="", **kwargs):
		kwargs.setdefault('tag', 'img')
		kwargs.setdefault('alt', alt)
		kwargs.setdefault('src', src)
		super().__init__(**kwargs)
		
	def render(self, debug=False, depth=0):
		return self.start_tag(debug=False)


class TABLE(EL):
	def __init__(self, **kwargs):
		c = []
		if 'c' in kwargs:
			c = kwargs.pop('c')
		super().__init__('table', **kwargs)
		EL('tbody', c=c)


class HTML_TEST(HTML):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
