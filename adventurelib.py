import re
import sys
import inspect
import readline
from copy import deepcopy
from functools import partial
from itertools import zip_longest

commands = [
    (('quit',), sys.exit, {}),  # quit command is built-in
]

__all__ = (
    'when',
    'start',
    'Room',
    'Item',
    'Bag',
)


class InvalidCommand(Exception):
    """A command is not defined correctly."""


class Placeholder:
    """Match a word in a command string."""
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name.upper()


class Room:
    """A generic room object that can be used by game code."""

    _directions = {}

    @staticmethod
    def add_direction(forward, reverse):
        """Add a direction."""
        for dir in (forward, reverse):
            if not dir.islower():
                raise InvalidCommand(
                    'Invalid direction %r: directions must be all lowercase.'
                )
            if dir in Room._directions:
                raise KeyError('%r is already a direction!' % dir)
        Room._directions[forward] = reverse
        Room._directions[reverse] = forward

        # Set class attributes to None to act as defaults
        setattr(Room, forward, None)
        setattr(Room, reverse, None)

    def __init__(self, description):
        self.description = description.strip()

        # Copy class Bags to instance variables
        for k, v in vars(type(self)).items():
            if isinstance(v, Bag):
                setattr(self, k, deepcopy(v))

    def __str__(self):
        return self.description

    def exit(self, direction):
        """Get the exit of a room in a given direction.

        Return None if the room has no exit in a direction.

        """
        if direction not in self._directions:
            raise KeyError('%r is not a direction' % direction)
        return getattr(self, direction, None)

    def exits(self):
        """Get a list of directions to exit the room."""
        return sorted(d for d in self._directions if getattr(self, d))

    def __setattr__(self, name, value):
        if isinstance(value, Room):
            if name not in self._directions:
                raise InvalidDirection(
                    '%r is not a direction you have declared.\n\n' +
                    'Try calling Room.add_direction(%r, <opposite>) ' % name +
                    ' where <opposite> is the return direction.'
                )
            reverse = self._directions[name]
            object.__setattr__(self, name, value)
            object.__setattr__(value, reverse, self)
        else:
            object.__setattr__(self, name, value)

Room.add_direction('north', 'south')
Room.add_direction('east', 'west')


class Item:
    """A generic item object that can be referred to by a number of names."""

    def __init__(self, name, *aliases):
        self.name = name
        self.aliases = (name,) + aliases

    def __repr__(self):
        return '%s(%s)' % (
            type(self).__name__,
            ', '.join(repr(n) for n in self.aliases)
        )

    def __str__(self):
        return self.name


class Bag(set):
    """A collection of Items, such as in an inventory.

    Behaves very much like a set, but the 'in' operation is overloaded to
    accept a str item name, and there is a ``take()`` method to remove an item
    by name.

    """
    def _find(self, name):
        for item in self:
            if name in item.aliases:
                return item
        return None

    def __contains__(self, v):
        """Return True if an Item is present in the bag.

        If v is a str, then find the item by name, otherwise find the item by
        identity.

        """
        if isinstance(v, str):
            return bool(self._find(v))
        else:
            return set.__contains__(v)

    def take(self, name):
        """Remove an Item from the bag if it is present.

        If multiple names match, then return one of them.

        Return None if no item matches the name.

        """
        obj = self._find(name)
        if obj is not None:
            self.remove(obj)
        return obj


def _register(command, func, kwargs={}):
    """Register func as a handler for the given command."""
    words = command.split()
    match = []
    argnames = []
    for w in words:
        if not w.isalpha():
            raise InvalidCommand(
                'Invalid command %r' % command +
                'Commands may consist of letters only.'
            )
        if w.isupper():
            arg = w.lower()
            argnames.append(arg)
            match.append(Placeholder(arg))
        elif w.islower():
            match.append(w)
        else:
            raise InvalidCommand(
                'Invalid command %r' % command +
                '\n\nWords in commands must either be in lowercase or ' +
                'capitals, not a mix.'
            )

    sig = inspect.signature(func)
    func_argnames = set(sig.parameters)
    when_argnames = set(argnames) | set(kwargs.keys())
    if func_argnames != when_argnames:
        raise InvalidCommand(
            'The function %s%s has the wrong signature for @when(%r)' % (
                func.__name__, sig, command
            ) + '\n\nThe function arguments should be (%s)' % (
                ', '.join(argnames + list(kwargs.keys()))
            )
        )

    commands.append((tuple(match), func, kwargs))


def prompt():
    """Called to get the prompt text."""
    return '> '


def no_command_matches(command):
    """Called when a command is not understood."""
    print("I don't understand '%s'." % command)


def when(command, **kwargs):
    """Decorator for command functions."""
    def dec(func):
        _register(command, func, kwargs)
        return func
    return dec


def help():
    """Print a list of the commands you can give."""
    print('Here is a list of the commands you can give:')
    for match, func, kwargs in sorted(commands):
        print(' '.join(str(t) for t in match))


def start(help=True):
    """Run the game."""
    if help:
        # Ugly, but we want to keep the arguments consistent
        help = globals()['help']
        commands.insert(0, (('help',), help, {}))
        commands.insert(0, (('?',), help, {}))
    while True:
        try:
            cmd = input(prompt()).strip()
        except EOFError:
            print()
            break

        if not cmd:
            continue

        ws = tuple(cmd.lower().split())
        for match, func, kwargs in commands:
            args = kwargs.copy()
            for cword, word in zip_longest(match, ws):
                if word is None:
                    break
                if isinstance(cword, Placeholder):
                    args[cword.name] = word
                elif cword != word:
                    break
            else:
                func(**args)
                break
        else:
            no_command_matches(cmd)
        print()


