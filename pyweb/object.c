#ifndef OBJECT_C
#define OBJECT_C

#include <stdint.h>

#define OBJ (g_objs[self])

typedef uint16_t ObjID;
typedef struct s_Object Object;

struct s_Object {
	ObjID id;
	ObjID parent;
	ObjID nchild;
	ObjID child[];
};

ObjID obj_new(uint16_t parent);
void obj_reset(void);

void obj_free(ObjID obj);
int obj_add_child(ObjID self, ObjID child);
ObjID obj_parent(ObjID self);
extern int obj_num;


#if __INCLUDE_LEVEL__ == 0

#include <malloc.h>

int obj_num = 0;
Object** g_objs = 0;

ObjID obj_new(uint16_t parent)
{
	++obj_num;
	if (!(g_objs = realloc(g_objs, sizeof(Object*)*(obj_num+1))))
		return 0;
	
	if(!(g_objs[obj_num] = malloc(sizeof(Object))))
		return 0;

	g_objs[obj_num]->id = obj_num;
	g_objs[obj_num]->parent = parent;
	g_objs[obj_num]->nchild = 0;
	return obj_num;
}

void obj_reset(void)
{
	for (int o =1; o <= obj_num; ++o) {
		free(g_objs[o]);
	}
	free(g_objs);
	g_objs = 0;
	obj_num = 0;
}

void obj_free(ObjID obj)
{
	
}

ObjID obj_parent(ObjID self)
{
	return g_objs[self]->parent;
}

int obj_add_child(ObjID self, ObjID child)
{
	++OBJ->nchild;
	if(!(g_objs[self] = realloc(g_objs[self], sizeof(Object) + sizeof(ObjID)*OBJ->nchild)))
		return 0;
	OBJ->child[OBJ->nchild-1] = child;
	return OBJ->nchild;
}




#endif
#endif
