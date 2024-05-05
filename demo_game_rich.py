from adventurelib_rich import *

load("demo_game_rich.toml")

console.substitutes = {
    "STYLE_ROOM": "green",
    "STYLE_ITEM": "yellow",
}

Room.label = None
Room.items = Bag()

current_room = starting_room = Room.load("Dark Room")
valley = starting_room.north = Room.load("Valley")
magic_forest = valley.north = Room.load("Magic Forest")
mallet = Item.load("rusty mallet")

valley.items = Bag(
    {
        mallet,
    }
)

inventory = Bag()


@when("north", direction="north")
@when("south", direction="south")
@when("east", direction="east")
@when("west", direction="west")
def go(direction):
    global current_room
    room = current_room.exit(direction)
    if room:
        current_room = room
        say("You go %s." % direction)
        look()
        if room == magic_forest:
            set_context("magic_aura")
        else:
            set_context("default")


@when("take ITEM")
def take(item):
    obj = current_room.items.take(item)
    if obj:
        say("You pick up the [$STYLE_ITEM]%s[/]." % obj)
        inventory.add(obj)
    else:
        say("There is no [$STYLE_ITEM]%s[/] here." % item)


@when("drop THING")
def drop(thing):
    obj = inventory.take(thing)
    if not obj:
        say("You do not have a [$STYLE_ITEM]%s[/]." % thing)
    else:
        say("You drop the [$STYLE_ITEM]%s[/]." % obj)
        current_room.items.add(obj)


@when("look")
def look():
    if current_room.label:
        console.print_ruler(current_room.label)
    say(current_room)
    if current_room.items:
        for i in current_room.items:
            say("A [$STYLE_ITEM]%s[/] is here." % i)


@when("inventory")
def show_inventory():
    say("You have:")
    for thing in inventory:
        say(thing)


@when("cast", context="magic_aura", magic=None)
@when("cast MAGIC", context="magic_aura")
def cast(magic):
    if magic == None:
        say("Which magic you would like to spell?")
    elif magic == "fireball":
        say("A flaming Fireball shoots form your hands!")


look()
start()
