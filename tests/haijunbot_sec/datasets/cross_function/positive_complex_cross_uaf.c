#include <stdlib.h>
#include <string.h>

typedef struct Node {
  char *value;
  struct Node *next;
} Node;

Node *create_node(const char *val) {
  Node *n = (Node *)malloc(sizeof(Node));
  n->value = (char *)malloc(strlen(val) + 1);
  strcpy(n->value, val);
  n->next = NULL;
  return n;
}

void free_node_value(Node *n) {
  if (n != NULL) {
    free(n->value); // freevaluebut not setNULL
  }
}

void print_node(Node *n) {
  if (n != NULL && n->value != NULL) {
    // usealreadyfreeofvalue
    printf("%s\n", n->value); // UAF
  }
}

int main(void) {
  Node *node = create_node("test");
  free_node_value(node); // freevalue
  print_node(node);      // usealreadyfreeofvalue -> UAF
  free(node->value);     // Double Free
  free(node);
  return 0;
}
