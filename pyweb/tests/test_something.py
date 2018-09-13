from unittest import TestCase

import pyweb

class TestSomething(TestCase):
	def test_is_string(self):
		s = pyweb.HTML()
		self.assertTrue(s.tag == 'body')
