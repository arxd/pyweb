from re import compile as re
import traceback

class CSSVal(list):
	tokens = {
		'`n': re(r'([+-]?(?:0|[1-9]\d*)\.?(?:\d+)?)'),
		'`p': re(r'([+-]?(?:0|[1-9]\d*)\.?(?:\d+)?)(%)'),
		'`l': re(r'([+-]?(?:0|[1-9]\d*)\.?(?:\d+)?)(cm|mm|ch|ex|px|pt|em|rem|vmin|vh|vw)'),
		'`t':re(r'([+-]?(?:0|[1-9]\d*)\.?(?:\d+)?)(s)'),
		'`a':re(r'([+-]?(?:0|[1-9]\d*)\.?(?:\d+)?)(deg)'),
		'`s':re(r'(".*?")'),
		'`e':re(r'([a-zA-Z_-]+)(?=(?:$|[( ),]))'),
		'`x':re(r'(#(?:(?:[0-9a-fA-F]{2}){3}|(?:[0-9a-fA-F]{3})))'),
		'`v':re(r'(\$[a-zA-Z-]+)'),
	}
	def __init__(self, sval):
		if isinstance(sval, str):
			self.parse(sval)
		else:
			super().__init__(sval)
			
	def parse(self, sval):
		def parse_space(pos):
			while pos < len(sval) and sval[pos] == ' ':
				pos += 1
			return pos

		def parse_val(pos):
			best = None
			for k, regex in CSSVal.tokens.items():
				m = regex.match(sval, pos)
				if m and (not best or m.end() > best[1]):
					best = ([k] + list(m.groups()), m.end())
			if not best:
				raise Exception("Bad CSS '%s!!!%s'"%(sval[:pos], sval[pos:]))
			return (best[0], parse_space(best[1]))

		def parse_tuple(pos=0):
			val = [' ']
			while True:
				if pos == len(sval) or sval[pos] in '),':
					return val, pos
					
				if sval[pos] == '(':
					if v[0] not in '`e`v':
						raise Exception("Bad function name '%s:%s' in '%s!!!%s'"%(val[-1][0], val[-1][1], sval[:pos], sval[pos:]))
					func, end = parse_list(parse_space(pos+1))
					if end == len(sval) or sval[end] != ')':
						raise Exception("Missing ')' '%s!!!%s'"%(sval[:pos], sval[pos:]))
					if len(func) == 1:
						raise Exception("Empty function")
					func[0] = val.pop()[1]
					val.append(func)
					pos = parse_space(end+1)
				
				else:
					v, pos = parse_val(pos)
					val.append(v)
			
		def parse_list(pos=0):
			val = [',']
			while True:
				v, end = parse_tuple(pos)
				val.append(v if len(v) > 2 else v[1])
				if end == len(sval) or sval[end] != ',':
					return (val, end)
				pos = parse_space(end+1)
				
		out = parse_list()[0]
		if len(out) < 2:
			raise Exception("Bad CSS '%s'"%sval)
		self. clear()
		self += out if len(out) > 2 else out[1]
	
	def vars(self):
		vset = set()
		def vars_r(sub):
			if sub[0] == ' ' or sub[0] == ',':
				for v in sub[1:]:
					vars_r(v)
			elif sub[0] == '`v':
				vset.add(sub[1])
		vars_r(self)
		return vset
	
	def sub(self, name, val):
		def sub_r(sub):
			if isinstance(sub, list):
				ocpy = []
				if sub[0] == '`v' and name == sub[1]:
					return val
				else:
					return [sub_r(x) for x in sub]
			else:
				return sub
		return CSSVal(sub_r(self))
	
	def match(self, pattern):
		pass
			
	def __str__(self):
		def str_r(lst):
			if lst[0] in '`p`l`t`a':
				return '%s%s'%(lst[1],lst[2])
			elif lst[0] in '`n`e`x`v`s':
				return lst[1]
			elif lst[0] == ' ':
				return ' '.join([str_r(s) for s in lst[1:]])
			elif lst[0] == ',':
				return ','.join([str_r(s) for s in lst[1:]])
			else:
				return lst[0] + '(' + ','.join([str_r(s) for s in lst[1:]]) + ')'
		return str_r(self)
		

class Styles(dict):
	def __init__(self, obj):
		super().__init__()
		self.obj = obj
		
	def set(self, svals, where=None):
		if not where:
			st = traceback.extract_stack(limit = 2)[0]
			where = "%s:%s"%(st.filename,st.lineno)

		lines = []
		for line in svals.split('\n'):
			try:
				lines.append(line[0:line.index('//')].strip())
			except:
				lines.append(line.strip())
		svals = ' '.join(lines)
		for v in svals.split(';'):
			v = v.strip()
			if not v:
				continue
			
			m = re(r'([$]?[a-zA-Z-]+)\s*:\s*(.*)').match(v)
			if not m:
				print("%s: Bad Name >>%s<<\n%s"%(where, v,'\n'.join(lines)))
				raise Exception()
			try:
				self[m.group(1)] = Value(self, m.group(2))
				#print("%s : %s == %s"%(where, m.group(1), self[m.group(1)] ))
				#print(self)
			except Exception as e:
				print("%s: Bad Value >>%s<<\n%s"%(where, m.group(2),'\n'.join(lines)))
				raise e
		return self
	
	def resolved(self, name, skip_self=False, depth=0):
		if (skip_self or name not in self ) and not self.obj.parent:
			raise Exception("Couldn't resolve %s"%name)
		if skip_self or name not in self:
			return self.obj.parent.styles.resolved(name,depth=depth+1)
		
		val = self[name]
		while True:
			vars = None
			for cond, v in val.items():
				vars = v.vars()
				if vars:
					break;
			if not vars:
				break
			nval = Value(self)
			vname = vars.pop()
			subval, dpth = self.resolved(vname, skip_self = (name==vname), depth=depth)
			for c2, v2 in subval.items():
				nval[c2] = val[cond].sub(vname, v2)
			val.update(cond, nval)
		return val, depth
	
	#~ def lookup(self, name, skip_self=False, depth=0):
		#~ if name in self and not skip_self:
			#~ return (super().__getitem__(name), depth)
		#~ if self.obj.parent:
			#~ return self.obj.parent.styles.lookup(name,depth = depth+1)
		#~ raise KeyError("Couldn't resolve '%s'"%name)
		
	def __setitem__(self, name, val):
		if name not in self:
			return super().__setitem__(name, Value(self, val) if isinstance(val, str) else val)
		else:
			self[name].update('default', val)
		
	def __str__(self):
		s = "==== Styles for %s ===\n"%self.obj
		for kv in self.items():
			s += '%s\n%s'%kv
		return s
		

class Value(dict):
	def __init__(self, styles, sval = ''):
		super().__init__()
		self.styles = styles
		if not sval:
			return
		if not isinstance(sval, str):
			raise Exception("Not a str %r"%sval)
		
		
		lines = []
		for line in sval.split('\n'):
			try:
				lines.append(line[0:line.index('//')].strip())
			except:
				lines.append(line.strip())
		sval = ' '.join(lines)
			
		if not sval.startswith('|'):
			sval = '|default ' + sval
		
		for val in sval.replace('\t',' ').split('|')[1:]:
			if ' ' not in val:
				raise Exception("Missing a value after the condition >>%s<<"%val)
			sp = val.index(' ')				
			cond = val[0:sp].strip()
			if cond == 'hover':
				cond = 'hover0'
			css = CSSVal(val[sp:].strip())
			if not css:
				raise Exception("Parse Error >>%s<<"%val[sp:].strip())
			if not cond:
				raise Exception("Don't put space after the | >>%s<<"%val)
			self[cond] = css
	
	def update(self, condition, other):
		for cond, val in other.items():
			#~ print("update %s(%r) -> %s"%(cond, val, condition))
			if condition == 'default':
				if cond == 'default':
					self[condition] = val
				elif cond.startswith('>'):
					if cond not in self:
						self[cond] = val
				elif cond == 'hover0':
					self[condition] = val
				elif cond.startswith('hover'):
					raise Exception("Not impl")
				else:
					raise Exception("unknown condition '%s'"%cond)
			elif condition.startswith('>'):
				if cond == 'default':
					self[condition] = val
				elif cond.startswith('>'):
					if int(cond[1:-2]) > int(condition[1:-2]):
						self[cond] = val
				elif cond.startswith('hover'):
					raise Exception("Not impl hover-> >px")
				else:
					raise Exception("unknown condition '%s'"%cond)
			elif condition == 'hover0':
				if cond == 'default':
					self[condition] = val
				elif cond.startswith('hover'):
					self[condition] = val
				elif cond.startswith('>'):
					raise Exception("not impl > -> hover")
				else:
					raise Exception("unknown condition '%s'"%cond)					
			else:
				raise Exception("Unknown condition '%s'"%condition)
		
	#~ def resolve(self, name):
		#~ vars = None
		#~ for cond, val in self.items():
			#~ vars = val.vars()
			#~ if vars:
				#~ break;
		#~ if not vars:
			#~ return self
		#~ nval = Value(self.styles)
		#~ vname = vars.pop()
		#~ subval, depth = self.styles.lookup(vname, skip_self = (name==vname), depth=0)
		#~ if 'hover0' in subval:
			#~ raise Exception("Deep Hover '%r' %d"%(subval, depth))
		#~ for c2, v2 in subval.items():
			#~ nval[c2] = val.sub(vname, v2)
		#~ self.update(cond, nval)
		#~ print("UPDATED %s: %r / %r"%(cond, self,nval))
		#~ self.resolve(name)
			
	def __str__(self):
		s = ''
		for k,v in self.items():
			s += '%20s | %s\n'%('' if k == 'default' else k,v)
		return s


