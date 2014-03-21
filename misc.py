from collections import namedtuple

def namedtuple_with_defaults(typename, *args, **kwargs):
    """Like namedtuple, but allows specifying defaults.

    The members without default values are specified as
    string arguments and then the ones with defaults
    are specified as keyword arguments.
    """

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
    """Do a generic value match between a value and a "matchval".

    The matchval can be:
    - The string '*', in which case always return True.
    - A callable, in which case it acts as a predicate.
    - Something that can be used with the "in" operator,
        in which case "value in matchval" is used.
    - Anything else, in which the two values are tested for
        equality.
    """

    if matchval == '*':
        return True
    elif callable(matchval):
        return matchval(val)

    try:
        return val in matchval
    except Exception:
        pass

    return val == matchval

def match_sequence(seq, matchvals):
    """Apply a sequence of matchvals to a sequence of values.

    See match.
    """

    return (len(seq) == len(matchvals) and
            all(match(val, matchval)
                for val, matchval in zip(seq, matchvals)))

def sequence_getitem(getitem):
    """Decorates sequence __getitem__ methods and adds slicing and negatives.

    Slicing allows getting a range of values with an optional step. Negative
    indeces allows getting values from the end of the sequence. These things
    are both annoying to implement and can be implemented with common code,
    which is what this decorator does.
    """

    def new_getitem(self, key):
        if isinstance(key, int):
            if -len(self) <= key <= -1:
                key = len(self) + key
            elif key < 0:
                raise IndexError()

            return getitem(self, key)
        elif isinstance(key, slice):
            return [self[i] for i in range(*key.indices(len(self)))]
        else:
            raise TypeError()

    return new_getitem

def find_connected_component(vertex, f):
    connections = set()

    def iterate_connections(origin):
        connections.add(origin)
        for coord in f(origin):
            if coord not in connections:
                iterate_connections(coord)

    iterate_connections(vertex)
    return connections
