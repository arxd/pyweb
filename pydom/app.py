import logging
from pydom import Button, App, AppServer

class React(object):
	def __init__(self, name):
		self.name = name
	
	def set(self, value):
		print(f"Setting {self.name} = {value}")
		
	def __getattribute__(self, item):
		print(f"GET: {item}")
		#if isinstance(self.__dict__[item], React):
		#	return 
		#return super().__getitem__(i)
		return super().__getattribute__(item) 
		
	def __setattr__(self, item, value):
		print(f"SET: {item} = {value}")
		obj = self.__dict__.get(item, None)
		if isinstance(obj, React):
			obj.set(value)
			
		return super().__setattr__(item, value)
		
class MyApp(App):
	def __init__(self):
		super().__init__()
		self.go = Button(icon="check", text="Go", style="round raised primary", enabled=False, handler=self)
		#self.x = React('bob')
		
	def on_click(self, btn):
		self.log(f"HI")
			


if __name__ == "__main__":
	logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
	MyApp().run()
