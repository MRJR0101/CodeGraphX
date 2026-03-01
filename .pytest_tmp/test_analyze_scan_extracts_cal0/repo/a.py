import os

def bar(y):
    return y + 1

def foo(x):
    if x > 0:
        return bar(x)
    return 0

def dup(v):
    if v:
        return v
    return 0
