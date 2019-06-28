#ifndef SET_C
#define SET_C


#include <stdint.h>

typedef uint64_t* Set;
typedef void (*EachFunc)(int objid, void *user_data);

void set_size(int nobjs);

Set set_new();
void set_free(Set self);
#define set_tmp(set) Set set = alloca(g_len*8)
Set set_copy(Set q, Set a); // q = a
Set set_and(Set q, Set a, Set b); // q = a&b  (intersect)
Set set_or(Set q, Set a, Set b); // q = a | b  (union)
Set set_sub(Set q, Set a, Set b); // q = a - b (difference)

void set_set(Set self, int obj);
void set_clear(Set self, int obj);
int set_test(Set self, int obj);
void set_each(Set self, EachFunc func, void *user_data);

int set_is_empty(Set self);
int set_is_subset(Set self, Set super);
int set_is_equal(Set self, Set other);

int set_len(Set self);
void set_dump(Set self);

void set_new_tag();

extern int g_len;

#if __INCLUDE_LEVEL__ == 0

//#include <malloc.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

int g_len; // number of 64bit words used to hold the objects
static int g_nobjs; // number of objetcs in the set

void set_size(int nobjs)
{
	g_nobjs = nobjs;
	++nobjs;
	g_len = (nobjs/64) + !!(nobjs%64);
}

Set set_new()
{
	Set self = (Set)malloc(g_len*8);
	memset(self, 0, g_len*8);
	return self;
}

void set_free(Set self)
{
	free(self);
}

Set set_copy(Set q, Set a)
{
	memcpy(q, a, g_len*8);
	return q;
}

Set set_and(Set q, Set a, Set b)
{
	for (int i=0; i < g_len; ++i)
		q[i] = a[i] & b[i];
	return q;
}

Set set_or(Set q, Set a, Set b)
{
	for (int i=0; i < g_len; ++i)
		q[i] = a[i] | b[i];
	return q;
}

void set_each(Set self, EachFunc func, void *user_data)
{
	for (int oid=0; oid <= g_nobjs; ++oid)
		if (set_test(self, oid))
			func(oid, user_data);
}

Set set_sub(Set q, Set a, Set b)
{
	for (int i=0; i < g_len; ++i)
		q[i] = a[i] & ~b[i];
	return q;
}

const char *set_str(Set self)
{
	static char buffer[256][16];
	static int i = 0;
	int ti = (++i) % 16;
	//~ for (int j=0; ++j)
	snprintf(buffer[ti], 256, "set:%d", set_len(self));
	return buffer[ti];
}


void set_set(Set self, int obj)
{
	self[obj>>6] |= ((uint64_t)1) << (obj%64);
}

void set_clear(Set self, int obj)
{
	self[obj>>6] &= ~(((uint64_t)1) << (obj%64));
}

int set_test(Set self, int obj)
{
	return (self[obj>>6] >> (obj%64))&1;
}

int set_is_empty(Set self)
{
	for (int i=0; i < g_len; ++i)
		if (self[i])
			return 0;
	return 1;
}

int set_is_subset(Set self, Set super) 
{
	for (int i=0; i < g_len; ++i)
		if (self[i] & ~super[i])
			return 0;
	return 1;
}

int set_is_equal(Set self, Set other) 
{
	for (int i=0; i < g_len; ++i)
		if (self[i] != other[i])
			return 0;
	return 1;
}


int set_len(Set self)
{
	int len=0;
	for (int i=1; i <= g_nobjs; ++i)
		len +=  (self[i/64] >> (i%64)) & 1;
	return len;
}

void set_dump(Set self)
{
	printf("Set(%d):", set_len(self));
	for (int i=1; i <= g_nobjs; ++i)
		if (set_test(self, i))
			printf("%d ", i);
	printf("\n");
	
}

#endif
#endif
