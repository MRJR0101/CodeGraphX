def add(x, y):
    return x + y


def multiply(a, b):
    return a * b


class BasePlugin:
    def run(self):
        raise NotImplementedError


class MyPlugin(BasePlugin):
    def run(self):
        return "hello"
