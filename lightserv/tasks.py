from . import cel

@cel.task()
def reverse(name):
    return name[::-1]