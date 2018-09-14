from .compiler import Compiler
import sys, yaml, importlib, shutil, os, os.path
from .html import HTML

def _build_cls(outdir, cls):
	print("Building %s..."%cls.__name__)
	obj = cls()
	cmp = Compiler()
	cmp.add_tree(obj)
	deps = cmp.get_py_deps()
	cmp.create_tag_sets()
	obj.inline_css = cmp.css_compile()
	obj.inline_js = cmp.js_compile(outdir)
	filename =  os.path.join(outdir, obj.__class__.__name__.lower() + ".html")
	with open(filename, 'w') as fo:
		print("Writing %s..."%filename)
		fo.write(obj.render(debug=1))
	return deps

def build(pages, outdir):
	deps = {}
	for page in pages:
		#~ print("Importing %s..."%page)
		#~ mod = importlib.import_module(page)
		cls = getattr(page, page.__name__.upper())
		if not issubclass(cls, HTML):
			cls = getattr(mod, mod.__name__.upper()+"_TEST")
		deps[page] = _build_cls(outdir, cls)
	return deps

def build_all():
	sys.path = ['./src'] + sys.path
	with open("pyweb_config.yaml", 'r') as config:
		config = yaml.load(config)
	outdir = os.path.join('.', config['out'])
	
	if os.path.isdir(outdir):
		shutil.rmtree(outdir)
	os.mkdir(outdir)
	
	for xtra in config['extra']:
		cpyfrom = os.path.join('.', xtra)
		cpyto = os.path.join(outdir, xtra)
		print("Copy %s => %s"%(cpyfrom, cpyto))
		if os.path.isdir(cpyfrom):
			shutil.copytree(cpyfrom, cpyto)
		elif os.path.isfile(cpyfrom):
			shutil.copy2(cpyfrom, cpyto)
		else:
			raise Exception("%s file not found"%cpyfrom)
			
	print("Importing pages %s ..."%config['pages'])
	pages = [importlib.import_module(page) for page in config['pages']]
	
	return config, build(pages, outdir)

def cli_build():
	build_all()