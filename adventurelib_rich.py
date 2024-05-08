"""A module that extends adventurelib library while maintaining compatibility.

Features:
- support for loading data from TOML files
- colorful and styled console output using rich library
- improved prompt with history and word completion

To use just import this module instead of adventurelib:
```
import adventurelib_rich as adventurelib
```

This comes with a cost: While the original adventurelib aims to be a single
file library without any dependencies besides Python 3, this module depends
on rich and prompt_toolkit libraries and needs a minimum version of 3.11 for
Python.
"""

import datetime
import functools
import re
import string
from typing import Self, Type, TypeVar

try:
    import tomllib
except ImportError:
    raise ImportError(
        "The adventurelib_rich module requires the tomllib library to load "
        "data from TOML files. tomllib is part of the Python standard library "
        "from version 3.11. Please upgrade to Python 3.11 or newer."
    )

try:
    import prompt_toolkit
    import prompt_toolkit.completion
    import prompt_toolkit.styles
except ImportError:
    raise ImportError(
        "The adventurelib_rich module requires the prompt_toolkit library for "
        "a better prompt. Either install it manually with "
        "`pip install prompt_toolkit` or (re)install adventurelib using the "
        "'rich' extra with `pip install adventurelib[rich]`."
    )

try:
    import rich.console
    import rich.style
    import rich.text
except ImportError:
    raise ImportError(
        "The adventurelib_rich module requires the rich library for colorful "
        "console output. Either install it manually with `pip install rich` "
        "or (re)install adventurelib using the 'rich' extra with "
        "`pip install adventurelib[rich]`."
    )


import adventurelib as al
from adventurelib import Bag, get_context, set_context, start, when

# Define the public API of this module to match the original adventurelib
# module. This way, users can import this module as `adventurelib` and use
# it as a drop-in replacement for the original adventurelib module.
# __all__ is used when doing `from adventurelib_rich import *`.
__all__ = (
    "when",
    "start",
    "protected",
    "Room",
    "Item",
    "Bag",
    "say",
    "set_context",
    "get_context",
    "load",
    "console",
)

# region Console


class Console(rich.console.Console):
    """Rich console with support for string substitution."""

    substitutes: dict[str, str] = {}

    def print_ruler(self, label: str) -> None:
        """Prints a ruler with a label."""
        text = rich.text.Text(label, style=rich.style.Style(color="magenta", bold=True))
        self.rule(text, style=rich.style.Style(color="cyan"))

    def print_with_substitutions(self, msg: str) -> None:
        """Prints a message with string substitutions."""
        self.print(string.Template(msg).substitute(self.substitutes))

    def prompt_password(self, message: str = "") -> str:
        return prompt_toolkit.prompt(
            prompt_toolkit.HTML(f"{message}"), is_password=True
        ).strip()


# Create a global console object that can be used for printing messages.
console = Console()


def say(msg: str | object) -> None:
    """Replaces the original `say` function with a version that supports
    styled output using rich libraries markup and string substitutions.
    Keeps the original behavior of the `say` function of de-denting the
    given text. Wrapping of text to fit within the width of the terminal is
    left to the rich libraries console.
    """
    if not isinstance(msg, str):
        msg = str(msg)
    msg = re.sub(r"^[ \t]*(.*?)[ \t]*$", r"\1", msg, flags=re.M)
    console.print_with_substitutions(msg)


# endregion

# region Prompt


def prompt_words() -> list[str]:
    """Returns a list of words that can be used for word completion in the
    prompt. The words are extracted from the available commands of the
    adventurelib module.
    """
    commands = al._available_commands()
    patterns = [pattern for pattern, _, _ in commands]
    words = {pattern.prefix[0] for pattern in patterns}
    return list(words)


prompt_style = prompt_toolkit.styles.Style.from_dict(
    {
        "completion-menu.completion": "bg:ansicyan fg:ansiblack",
        "completion-menu.completion.current": "bg:ansiwhite ansimagenta",
    }
)

prompt_session = prompt_toolkit.PromptSession(style=prompt_style)
# Define a completer that uses the words from the prompt_words function.
# This is a very simple completer that only completes the first word of the
# input with the available commands.
prompt_completer = prompt_toolkit.completion.WordCompleter(
    words=prompt_words, ignore_case=True
)


def prompt() -> str | prompt_toolkit.HTML:
    """A replacement for the original `prompt` function that uses the
    prompt_toolkit library for a more advanced prompt with history and
    word completion. The prompt is styled using the rich library.
    """
    return prompt_toolkit.HTML("<ansicyan>⏵ </ansicyan>")


# Replace the original prompt function with the new prompt function.
al.prompt = prompt

# Patch the adventurelib module to use the new prompt function together with
# the word completer. This is done replacing the `input` function in the
# adventurelib module.
setattr(
    al,
    "input",
    functools.partial(
        prompt_session.prompt, completer=prompt_completer, reserve_space_for_menu=4
    ),
)


# endregion

# region Adventure Data

adventure_data = None


class AdventureDataError(Exception):
    """Base class for exceptions raised by the TOML data loader."""


class AdventureDataLoadError(AdventureDataError):
    """Raised when there is an error loading the TOML data from a file."""


def load(filename: str) -> None:
    """Loads the adventure data from a TOML file. The data is stored in a
    global variable and can be accessed using the `get_from_data` function.

    Raises:
        AdventureDataLoadError: If the file is not found or the data is invalid.
    """
    global adventure_data
    try:
        with open(filename, "rb") as f:
            adventure_data = tomllib.load(f)
    except FileNotFoundError as fnfe:
        raise AdventureDataLoadError(f"Data file '{filename}' not found") from fnfe
    except tomllib.TOMLDecodeError as tde:
        raise AdventureDataLoadError(
            f"Data file '{filename}' with invalid data"
        ) from tde


E = TypeVar("E")


def _get_from_data(name: str, cls: Type[E]) -> E:
    """Loads an entity from the adventure data using the given name and class.
    Possible classes are `Room` and `Item`. The data must be loaded with the
    `load` function before calling this function.

    The TOML data file must have a section for the entity class with the type
    and the name of the entity, for example `[Room."Dark Room"]`. Values from
    this section will be added as attributes to the entity using their keys as
    attribute names.

    Raises:
        AdventureDataError: If the data is not loaded, the entity is not found,
            or there is a conflict with existing attributes of the entity.
    """
    if not adventure_data:
        raise AdventureDataError(
            'No adventure data loaded: use load("<filename>") first to read '
            "data from a TOML file."
        )

    cls_name = cls.__name__
    cls_name_lower = cls_name.lower()
    try:
        obj_data = adventure_data[cls_name][name]
    except KeyError as key_error:
        if key_error.args[0] == cls_name:
            msg = f"Section for {cls_name_lower}s in data missing"
        else:
            msg = f'Invalid {cls_name_lower} name "{name}"'
        raise AdventureDataError(
            f"{msg}: To load a {cls_name_lower} from the data file, add a "
            f'section to the TOML file with "{cls_name}" and the name of '
            f'the {cls_name_lower}, for example `[{cls_name}."Dark Room"]`. '
            f"Values from this section will be added as attributes to the "
            f"{cls_name_lower} using their keys as attribute names."
        )

    # Some keys are mandatory for certain entities and must be given in the
    # initial arguments when creating the entity, for example the description
    # for a room. These keys are handled separately and are added to this list:
    consumed_keys = []
    # Keys are checked for conflicts with existing attributes of the entity
    # class. That is to prevent overwriting existing attributes such as
    # `forward`. Keys which should not be checked (and therefore are allowed
    # to be overwritten) are added to this list:
    checked_keys = []

    if issubclass(cls, Room):
        try:
            args = [obj_data["description"]]
            consumed_keys.append("description")
        except KeyError:
            raise AdventureDataError(
                f'Missing "description" in section `[{cls_name}."{name}"]` in '
                f"TOML file: Description is a mandatory value for a "
                f"{cls_name_lower} in data."
            )
        checked_keys.append("label")
    elif issubclass(cls, Item):
        args = [name]
        if aliases := obj_data.get("aliases"):
            args = args + [label.lower() for label in [name] + aliases]
            consumed_keys.append("aliases")
    else:
        args = []

    # Create the entity object with the given arguments.
    obj = cls(*args)

    # Add the remaining values from the data to the entity as attributes.
    for key, value in obj_data.items():
        if key in consumed_keys:
            continue
        if key not in checked_keys and hasattr(obj, key):
            raise AdventureDataError(
                f'Key "{key}" in section `[{cls_name}."{name}"]` in TOML '
                f"file conflicts with an existing attribute of the {cls_name_lower}."
            )
        setattr(obj, key, value)

    return obj


# endregion

# region Adventure Entities


class Room(al.Room):
    @classmethod
    def load(cls, name: str) -> Self:
        """Extends the original `Room` entity with a `load` class method that
        loads the room data from the adventure data file. The data file must
        be loaded with the `load` function before calling this method.
        """
        return _get_from_data(name, cls=cls)


class Item(al.Item):
    @classmethod
    def load(cls, name: str) -> Self:
        """Extends the original `Item` entity with a `load` class method that
        loads the room data from the adventure data file. The data file must
        be loaded with the `load` function before calling this method.
        """
        return _get_from_data(name, cls=cls)


# endregion

# region Protected


class protected:
    """Decorator to protect a function with a password prompt.

    How to use:
    ```
    @protected
    def secret_function():
        print("You found the secret function!")
    ```

    How to customize:
    ```
    protected.password = "secret"
    protected.message = "Enter password:"
    protected.message_success = "Password is correct!"
    protected.message_fail = "Password is not correct."
    protected.timeout = 600
    ```
    """

    password = "password"
    message = "password?"
    message_success: str | None = None
    message_fail: str | None = "wrong password!"
    timeout: int = 0

    _authorized_at = None

    def __init__(self, function):
        self.function = function
        functools.update_wrapper(self, function)

    def _authorized(self) -> bool:
        if self._authorized_at:
            timedelta = datetime.datetime.now() - self._authorized_at
            return timedelta < datetime.timedelta(seconds=self.timeout)
        else:
            return False

    def _authorize(self):
        self._authorized_at = datetime.datetime.now()

    def __call__(self, *args, **kwargs):
        if not self._authorized():
            password = console.prompt_password(self.message)
            if password != self.password:
                if self.message_fail:
                    console.print(self.message_fail)
                return None

            self._authorize()

            if self.message_success:
                console.print(self.message_success)

        return self.function(*args, **kwargs)


# endregion
