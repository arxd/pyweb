from .compiler import Compiler
import sys, yaml, importlib, shutil, os, os.path
from .html import HTML

def _build_cls(outdir, cls, inline):
	print("Building %s %s..."%(cls.__name__,"inline" if inline else "."))
	obj = cls()
	cmp = Compiler()
	cmp.add_tree(obj)
	deps = cmp.get_py_deps()
	cmp.create_tag_sets()
	obj.inline_css = cmp.css_compile()
	obj.inline_js = cmp.js_compile(outdir, inline)
	filename =  os.path.join(outdir, obj.__class__.__name__.lower() + ".html")
	with open(filename, 'w') as fo:
		print("Writing %s..."%filename)
		fo.write(obj.render(debug=not inline))
	return deps

def build(pages, outdir, inline):
	deps = {}
	for page in pages:
		#~ print("Importing %s..."%page)
		#~ mod = importlib.import_module(page)
		cls = getattr(page, page.__name__.upper())
		if cls.__bases__[0].__name__ != 'HTML':
			cls = getattr(page, page.__name__.upper()+"_TEST")
		deps[page] = _build_cls(outdir, cls, inline)
	return deps

def build_all(config, inline):
	outdir = os.path.join('.', config['out'])
	
	#if os.path.isdir(outdir):
	#	shutil.rmtree(outdir)
	#os.mkdir(outdir)
	
	for xtra in config['extra']:
		cpyfrom = os.path.join('.', xtra)
		cpyto = os.path.join(outdir, xtra)
		print("Copy %s => %s"%(cpyfrom, cpyto))
		try:
			if os.path.isdir(cpyfrom):
				shutil.copytree(cpyfrom, cpyto)
			elif os.path.isfile(cpyfrom):
				shutil.copy2(cpyfrom, cpyto)
			else:
				raise Exception("%s file not found"%cpyfrom)
		except FileExistsError:
			pass
			
	print("Importing pages %s ..."%config['pages'])
	pages = [importlib.import_module(page) for page in config['pages']]
	
	return build(pages, outdir, inline)

def cli_build_inline():
	cli_build(True)

def cli_build(inline=False):
	sys.path = ['./src'] + sys.path
	with open("pyweb_config.yaml", 'r') as config:
		config = yaml.load(config)
	if len(sys.argv) == 2:
		build( [importlib.import_module(page) for page in sys.argv[1:]], os.path.join('.', config['out']), inline )
	else:
		build_all(config, inline)
	