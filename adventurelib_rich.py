import functools
import re
import tomllib

import prompt_toolkit
import prompt_toolkit.completion
import rich.console

import adventurelib as al
from adventurelib import Bag, Item, Room, get_context, set_context, start, when

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
)

console = rich.console.Console()

# region Data

data = None


def load(filename):
    global data
    with open(filename, "rb") as f:
        data = tomllib.load(f)


def load_from_data(name, cls):
    if not data:
        raise ValueError(
            'No data loaded: use load("<filename>") first to read data from '
            "a TOML file."
        )

    cls_name = cls.__name__
    cls_name_lower = cls_name.lower()
    try:
        obj_data = data[cls_name][name]
    except KeyError as key_error:
        if key_error.args[0] == cls_name:
            msg = f"Section for {cls_name_lower}s in data missing"
        else:
            msg = f'Invalid {cls_name_lower} name "{name}"'
        raise ValueError(
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
            raise ValueError(
                f'Missing "description" in section `[{cls_name}."{name}"]` in '
                f"TOML file: Description is a mandatory value for a "
                f"{cls_name_lower} in data."
            )
        checked_keys.append("label")
    elif cls is Item:
        if aliases := obj_data.get("aliases"):
            args = [name] + [label.lower() for label in [name] + aliases]
            consumed_keys.append("aliases")

    obj = cls(*args)

    for key, value in obj_data.items():
        if key in consumed_keys:
            continue
        if key not in checked_keys and hasattr(obj, key):
            raise ValueError(
                f'Key "{key}" in section `[{cls_name}."{name}"]` in TOML '
                f"file conflicts with an existing attribute of the {cls_name_lower}."
            )
        setattr(obj, key, value)

    return obj


setattr(al.Room, "load", functools.partial(load_from_data, cls=Room))
setattr(al.Item, "load", functools.partial(load_from_data, cls=Item))

# endregion

# region Prompt


def prompt_words():
    commands = al._available_commands()
    patterns = [pattern for pattern, _, _ in commands]
    words = [pattern.prefix[0] for pattern in patterns]
    return words


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

# region Say


def say(msg):
    msg = str(msg)
    msg = re.sub(r"^[ \t]*(.*?)[ \t]*$", r"\1", msg, flags=re.M)
    console.print(msg)


# endregion
