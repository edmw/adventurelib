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

import functools
import re
import string

try:
    import tomllib
except ImportError:
    raise ImportError(
        "The adventurelib_rich module requires the tomllib library to load "
        "data from TOML files. Either install it manually with "
        "`pip install tomllib` or (re)install adventurelib using the 'rich' "
        "extra `pip install adventurelib[rich]`."
    )

try:
    import prompt_toolkit
    import prompt_toolkit.completion
except ImportError:
    raise ImportError(
        "The adventurelib_rich module requires the prompt_toolkit library for "
        "a better prompt. Either install it manually with "
        "`pip install prompt_toolkit` or (re)install adventurelib using the "
        "'rich' extra `pip install adventurelib[rich]`."
    )

try:
    import rich.console
    import rich.style
    import rich.text
except ImportError:
    raise ImportError(
        "The adventurelib_rich module requires the rich library for colorful "
        "console output. Either install it manually with `pip install rich` "
        "or (re)install adventurelib using the 'rich' extra "
        "`pip install adventurelib[rich]`."
    )

import adventurelib as al
from adventurelib import Bag, get_context, set_context, start, when

__all__ = (
    "when",
    "start",
    "Room",
    "Item",
    "Bag",
    "say",
    "set_context",
    "get_context",
    "load",
    "console",
    "print_ruler",
)

# region Console


class Console(rich.console.Console):
    substitutes = {}


console = Console()


def print_ruler(label: str) -> None:
    text = rich.text.Text(label, style=rich.style.Style(color="magenta", bold=True))
    console.rule(text, style=rich.style.Style(color="cyan"))


def say(msg: str):
    msg = str(msg)
    msg = re.sub(r"^[ \t]*(.*?)[ \t]*$", r"\1", msg, flags=re.M)
    if console.substitutes:
        msg = string.Template(msg).substitute(console.substitutes)
    console.print(msg)


# endregion

# region Prompt


def prompt_words():
    commands = al._available_commands()
    patterns = [pattern for pattern, _, _ in commands]
    words = {pattern.prefix[0] for pattern in patterns}
    return list(words)


prompt_session = prompt_toolkit.PromptSession()
prompt_completer = prompt_toolkit.completion.WordCompleter(
    words=prompt_words, ignore_case=True, sentence=True
)


def prompt():
    return prompt_toolkit.HTML("<ansicyan>⏵ </ansicyan>")


al.prompt = prompt
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
    pass


class AdventureDataLoadError(AdventureDataError):
    pass


def load(filename: str) -> None:
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


def load_from_data(name, cls):
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

    checked_keys = []
    consumed_keys = []

    if cls is Room:
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
    elif cls is Item:
        args = [name]
        if aliases := obj_data.get("aliases"):
            args = args + [label.lower() for label in [name] + aliases]
            consumed_keys.append("aliases")
    else:
        args = []

    obj = cls(*args)

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
    def load(cls, name):
        return load_from_data(name, cls=cls)


class Item(al.Item):
    @classmethod
    def load(cls, name):
        return load_from_data(name, cls=cls)


# endregion
