from libc.stdint cimport uint64_t,uint16_t

cdef extern from "set.c":
	ctypedef uint64_t* Set
	ctypedef void (*EachFunc)(int objid, void *user_data)

	void set_size(int nobjs)
	Set set_new()
	void set_free(Set self)
	void set_each(Set self, EachFunc func, void *user_data)
	Set set_and(Set q, Set a, Set b)
	Set set_or(Set q, Set a, Set b)
	Set set_sub(Set q, Set a, Set b)
	
	void set_set(Set self, int obj)
	void set_clear(Set self, int obj)
	bint set_test(Set self, int obj)
	
	bint set_is_empty(Set self)
	bint set_is_subset(Set self, Set super)
	bint set_is_equal(Set self, Set other)
	
	int set_len(Set self)
	
	
cdef extern from "object.c":
	ctypedef uint16_t ObjID
	ctypedef struct Object:
		pass
		
	ObjID obj_new(uint16_t parent)
	void obj_free(ObjID obj)
	void obj_reset()
	int obj_add_child(ObjID self, ObjID child)

cdef extern from "dom.c":
	ctypedef struct Query:
		int type
		int a
		int b
		Set set
		int nsty
		int *styles
		
	void dom_reset()
	void dom_query_new_type(int type)
	void dom_query_add_obj(int qid, ObjID obj)
	void dom_query_dump()
	int dom_num_query()
	Query dom_get_query(int qid)

	int dom_query_num_styles(int qid)
	int dom_query_get_styles(int qid, int sid)

	void dom_style_add_obj(int styid, ObjID obj)
	void dom_style_new()
	void dom_style_dump()
	void dom_style_resolve()

	int style_num_covers(int sid)
	int style_get_cover(int sid, int qid)
	void query_dump(int qid)

	#~ Set dom_tag_set(int tagid)

