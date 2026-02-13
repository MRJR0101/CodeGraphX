def add(a, b):
    return a + b


def add2(x, y):
    return x + y


class BasePlugin:
    def run(self):
        raise NotImplementedError
