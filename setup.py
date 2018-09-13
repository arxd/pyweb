from setuptools import setup
from Cython.Build import cythonize
from distutils.extension import Extension

def readme():
	with open('README.md') as f:
		return f.read()

setup(
	name='pyweb',
	version='0.1',
	description='Python build environment for html+css+js web pages',
	long_description=readme(),
	test_suite='nose.collector',
	tests_require=['nose'],
	url='http://github.com/arxd/pyweb',
	#dependency_links=['http://github.com/arxd/pyweb/tarball/master#egg=package-1.0'],
	author='A Programmer',
	author_email='nah',
	license='MIT',
	packages=['pyweb'],
	install_requires=['cython', 'pyyaml'],
	zip_safe=False,
	ext_modules = cythonize([Extension("pyweb.compiler", ["pyweb/compiler.pyx"])]),
	entry_points = {
		'console_scripts': [
			'pyweb-build=pyweb:build',
			'pyweb-serve=pyweb:serve',
			
		],
	}
)