#ifndef DOM_C
#define DOM_C

#include "set.c"
#include "object.c"

#define Q_TAG 0
#define Q_CLS 1
#define Q_AND 2
#define Q_HIER 3

typedef int Qid;
typedef struct s_Query Query;
typedef struct s_Style Style;

struct s_Query { // div.a span.b
	int type; // 0:tag 1:class 2:tag/cls 3:parent/child
	int a, b;
	Set set;
	int nsty;
	int *styles;
};

struct s_Style {
	int sid;
	int nq;
	Set set;
	Qid *q;
};


void dom_query_new_type(int type);
void dom_query_add_obj(int qid, ObjID obj);

void dom_style_add_obj(int styid, ObjID obj);
void dom_style_new();
void dom_style_resolve();

void dom_style_dump();
void dom_query_dump();

int dom_num_query(void);
Query dom_get_query(int qid);

int style_num_covers(int sid);
int style_get_cover(int sid, int qid);

int dom_query_num_styles(int qid);
int dom_query_get_styles(int qid, int sid);

void query_dump(int qid);

#if __INCLUDE_LEVEL__ == 0

#include <malloc.h>
#include <stdlib.h>

static Style* g_sty = 0;
static int g_nsty = 0;

static Query* g_q = 0;
static int g_nq = 0;


void dom_query_new_type(int type)
{
	++g_nq;
	g_q = realloc(g_q, sizeof(Query)*(g_nq+1));
	g_q[g_nq].set = set_new();
	g_q[g_nq].a = g_q[g_nq].b = 0;
	g_q[g_nq].type = type;
	g_q[g_nq].nsty = 0;
	g_q[g_nq].styles = 0;
}

void dom_query_add_obj(int qid, ObjID obj)
{
	set_set(g_q[qid].set, obj);
}

void dom_style_new()
{
	++g_nsty;
	g_sty = realloc(g_sty, sizeof(Style)*(g_nsty+1));
	g_sty[g_nsty].set = set_new();
	g_sty[g_nsty].sid = g_nsty;
	g_sty[g_nsty].nq = 0;
	g_sty[g_nsty].q = 0;
}

void dom_style_add_obj(int styid, ObjID obj)
{
	set_set(g_sty[styid].set, obj);
}

int dom_num_query(void)
{
	return g_nq;
}

Query dom_get_query(int qid)
{
	return g_q[qid];
}

static int parent_in_set(ObjID o, Set s)
{
	while (o = obj_parent(o))
		if (set_test(s, o))
			return 1;
	return 0;
}

static void query(Query *q)
{
	if (q->type == Q_AND) {
		set_and(q->set, g_q[q->a].set, g_q[q->b].set);
	} else {
		set_copy(q->set, g_q[q->b].set);
		for (ObjID o = 1; o <= obj_num; ++o)
			if (set_test(q->set, o) && !parent_in_set(o, g_q[q->a].set))
				set_clear(q->set, o);
	}
}

static const char *qtype(int qid)
{	
	static int i = 0;
	static char buf[64][16];
	int ti = (++i) %16;
	switch (g_q[qid].type) {
		case Q_TAG: snprintf(buf[ti], 64, "<%d>", qid); break;
		case Q_CLS: snprintf(buf[ti], 64, ".%d", qid); break;
		case Q_AND: snprintf(buf[ti], 64, "%s%s", qtype(g_q[qid].a), qtype(g_q[qid].b)); break;
		case Q_HIER: snprintf(buf[ti], 64, "%s %s", qtype(g_q[qid].a), qtype(g_q[qid].b)); break;
	}
	return buf[ti];
}

const char* query_str(int qid)
{
	static int i=0;
	static char buffer[256][16];
	int ti = (++i)%16;
	snprintf(buffer[ti], 256, "%s(%d)", qtype(qid), set_len(g_q[qid].set));
	return buffer[ti];
}

void query_dump(int qid)
{
	printf("%s\n", query_str(qid));
}

static int stycmp(const Style* s1, const Style* s2)
{
	int ls1= set_len(s1->set);
	int ls2 = set_len(s2->set);
	if (ls1 == ls2) 
		return 0;
	return (ls1 > ls2)? 1: -1;
}

const char *style_coverage(Style *s)
{
	static char buffer[256];
	Set q  = set_new();
	for(int i=0; i < s->nq; ++i)
		set_or(q, q, g_q[s->q[i]].set);
	snprintf(buffer, 256, "%d/%d", set_len(q), set_len(s->set));
	return buffer;
}

void try_add_query(int type, int a, int b)
{
	set_tmp(tmp);
	Query q;
	q.a = a;
	q.b = b;
	q.set = tmp;
	q.type = type;
	query(&q);
	if (set_is_empty(q.set) || set_is_equal(q.set, g_q[b].set))
		return;
	dom_query_new_type(type);
	g_q[g_nq].a = a;
	g_q[g_nq].b = b;
	set_copy(g_q[g_nq].set, q.set);
}

int dom_query_num_styles(int qid)
{
	return g_q[qid].nsty;
}

int dom_query_get_styles(int qid, int sid)
{
	return g_q[qid].styles[sid];
}

int style_num_covers(int sid)
{
	return g_sty[sid].nq;
}

int style_get_cover(int sid, int qid)
{
	return g_sty[sid].q[qid];
}

int dom_query_new_class(Set set)
{
	int clsid = ++g_nq;
	g_q = realloc(g_q, sizeof(Query)*(g_nq+1));
	g_q[g_nq].set = set_new();
	set_copy(g_q[g_nq].set, set);
	g_q[g_nq].a = g_q[g_nq].b = 0;
	g_q[g_nq].type = Q_CLS;
	int max = g_nq;
	for (int i = 1; i <= max; ++i) {
		if (g_q[i].type == Q_TAG || g_q[i].type==Q_CLS)
			try_add_query(Q_AND, i, max);
	}
	max = g_nq;
	for (int i = 1; i <= max; ++i) {
		if (g_q[i].type != Q_HIER) {
			try_add_query(Q_HIER, i, max);
			try_add_query(Q_HIER, max, i);
		}
	}
	return clsid;
}

static void style_qadd(Style *s, int qid)
{
	for (int q=0; q < s->nq; ++q) {
		if (set_is_subset(g_q[qid].set, g_q[s->q[q]].set))
			return;
	}
	s->nq ++;
	s->q = realloc(s->q, sizeof(Qid) * s->nq);
	s->q[s->nq-1] = qid;
	++g_q[qid].nsty;
	g_q[qid].styles = realloc(g_q[qid].styles, sizeof(int)*g_q[qid].nsty);
	g_q[qid].styles[g_q[qid].nsty - 1] = s->sid;
}

static void style_resolve(Style *s)
{
	int ncov = 0;
	set_tmp(cover);
	for (int q = 1; q <= g_nq; ++q) {
		if (set_is_subset(g_q[q].set, s->set)) {
			style_qadd(s, q);
			set_or(cover,cover, g_q[q].set);
			ncov ++;
		}
	}
	set_sub(cover, s->set, cover);
	//~ printf("%d: %d / %d  ", s->sid, ncov, set_len(cover));
	
	if (set_is_empty(cover)) {
		//~ printf("Done\n");
		return; // all done
	}
	int nid = dom_query_new_class(cover);
	//~ printf(" new class %s\n",query_str(nid));
	style_qadd(s, nid);
}

void dom_style_resolve()
{
	int ntags = g_nq;
	for (int a = 1; a <= ntags; ++a) {
		for (int b = 1; b <= ntags; ++b) {
			try_add_query(Q_HIER, a, b);
		}
	}
	//~ qsort(&g_sty[1], g_nsty, sizeof(Style), stycmp);
	for (int i=1; i <= g_nsty; ++i)
		style_resolve(&g_sty[i]);
	//~ dom_query_dump();
}

void dom_query_dump()
{
	for (int qid=1; qid <= g_nq; ++qid) {
		printf("%s : %d objs ", qtype(qid), set_len(g_q[qid].set));
		for (int s =0; s < g_q[qid].nsty; ++s)
			printf(" %d", g_q[qid].styles[s]);
		printf("\n");
	}
	printf("%d queries\n", g_nq);
	
	//~ dom_style_dump();
}

void dom_style_dump()
{
	int nused = 0;
	int *used = alloca(sizeof(int)*g_nq);
	
	int is_used(int qid) {
		for (int u=0; u < nused; ++u) {
			if (used[u] == qid)
				return 1;
		}
		return 0;
	}
	
	for (int i = 1; i <= g_nsty; ++i) {
		for(int q=0; q < g_sty[i].nq; ++q) {
			if (!is_used(g_sty[i].q[q])) {
				used[nused++] = g_sty[i].q[q];
			}
		}
	}
	for (int i=0; i < nused; ++i) {
		printf("%s : %d\n", qtype(used[i]), set_len(g_q[used[i]].set));
	}
	printf("%d used queries\n", nused);
	//~ for (int styid = 1; styid <= g_nstyles; ++styid) {
		//~ for (int tid = 1; tid <= g_ntags; ++tid) {
			//~ if (set_is_subset(g_tags[tid], g_styles[styid])) {
				//~ printf("%d:%d is subset of %d:%d\n", tid, set_len(g_tags[tid]), styid, set_len(g_styles[styid]));
			//~ }
		//~ }
	//~ }		
	//~ for (int styid=1; styid <= g_nstyles; ++styid) {
		//~ printf("%3d: %d\n", styid, set_len(g_styles[styid]));
		
	//~ }
	
}

#endif
#endif
