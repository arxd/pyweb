
from .html import HTML, EL, DIV, IDIV, FLEX, CDATA, BR, SPAN, P, A, DIMG, TABLE, IMG, HTML_TEST
from .compiler import Compiler
import sys, yaml, importlib

def serve():
	sys.path = ['.'] + sys.path
	from pyweb_config import config
	

def _build_cls(cls):
	print("Building %s..."%cls.__name__)
	obj = cls()
	cmp = Compiler()
	cmp.add_tree(obj)
	cmp.create_tag_sets()
	obj.inline_css = cmp.css_compile()
	obj.inline_js = cmp.js_compile('.')
	filename = obj.__class__.__name__.lower() + ".html"
	with open(filename, 'w') as fo:
		print("Writing %s..."%filename)
		fo.write(obj.render(debug=1))


def build():
	sys.path = ['./src'] + sys.path
	with open("pyweb_config.yaml", 'r') as config:
		config = yaml.load(config)
	
	for page in config['pages']:
		print("Importing %s..."%page)
		mod = importlib.import_module(page)
		cls = getattr(mod, mod.__name__.upper())
		if not issubclass(cls, HTML):
			cls = getattr(mod, mod.__name__.upper()+"_TEST")
		_build_cls(cls)

