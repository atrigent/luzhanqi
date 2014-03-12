from collections import namedtuple

def namedtuple_with_defaults(typename, *args, **kwargs):
    extra_args = {}
    for arg in 'verbose', 'rename':
        if arg in kwargs:
            extra_args[arg] = kwargs[arg]
            del kwargs[arg]

    kwargs = tuple(kwargs.items())
    field_names = list(args) + [key for key, val in kwargs]
    defaults = tuple(val for key, val in kwargs)

    T = namedtuple(typename, field_names, **extra_args)
    T.__new__.__defaults__ = defaults
    return T

def match(val, matchval):
    if matchval == '*':
        return True
    elif callable(matchval):
        return matchval(val)
    elif isinstance(matchval, list):
        return val in matchval
    else:
        raise ValueError()

class SequenceMixin:
    def __getitem__(self, key):
        if isinstance(key, int):
            if -len(self) <= key <= -1:
                key = len(self) + key
            elif key < 0:
                raise IndexError()

            return super().__getitem__(key)
        elif isinstance(key, slice):
            return [self[i] for i in range(*key.indices(len(self)))]
        else:
            raise TypeError()
