from typing import (
    Dict,
    Any,
    Union,
    List,
    Optional,
    Set,
    Iterator,
    Iterable,
    cast,
    Tuple,
    NewType,
)
from mypy_extensions import TypedDict
import re
import itertools
from dataclasses import dataclass

# The KeyPath is the sequence of key accesses required to get to a certain
# value, represented by `key1.key2.key3` etc.
# All TypedDicts under the same path are likely to be of the same type, so we need
# to be able to clearly identify them so that the generated dicts for multiple
# examples can be unified.
KeyPath = NewType("KeyPath", str)


@dataclass
class TypedDictPrinter:
    """When printed, returns the Python code to generate a TypedDict."""

    name: str
    dict_: Dict[str, Any]

    def __str__(self) -> str:
        pairs = (f'"{key}": {value}' for key, value in self.dict_.items())
        dict_str = "{ " + ", ".join(pairs) + " }"

        # types of built-ins convert to str like this: <class 'classname'>
        # this substitution extracts 'classname' from that
        dict_str = re.sub(r"<class '(\w+)'>", lambda match: match.group(1), dict_str)
        dict_str = dict_str.replace("typing.", "")

        return f'TypedDict("{self.name.title()}", {dict_str})'


def get_type(key: str, value: Any) -> Union[None, type, List[type], TypedDictPrinter]:
    type_ = value.__class__
    if value is None:
        # strictly speaking, None is of type NoneType
        # but the typing constructs accept None where NoneType should appear
        return None
    if type_ in [str, int, float, bool]:
        return type_
    if type_ == list:
        # typed_dicts = []
        other_types: Set = set()

        for element in value:
            element_type = get_type(key, element)

            if isinstance(element_type, TypedDictPrinter):
                # typed_dicts.append(element_type)
                raise NotImplementedError(
                    "Dictionaries nested in lists not yet supported"
                )
            else:
                other_types.add(element_type)

        all_types: Iterable
        if other_types:  # or typed_dicts:
            all_types = other_types  # itertools.chain(other_types, typed_dicts)
        else:
            all_types = [Any]

        # if there is only 1 type, the Union will collapse
        # into that one type
        return List[Union[tuple(all_types)]]
    if type_ == dict:
        assert key is not None
        types_of_keys = {key: get_type(key, val) for key, val in value.items()}
        return TypedDictPrinter(key, types_of_keys)

    raise ValueError("type not supported")


def generate_typed_dict_code(name: str, dictionary: Dict[str, Any]) -> str:
    return str(get_type(name, dictionary))


def find_all_typed_dicts(
    name: str, dict_: Dict[str, Any]
) -> Iterator[Tuple[KeyPath, TypedDictPrinter]]:
    toplevel_dict = get_type(name, dict_)
    assert isinstance(toplevel_dict, TypedDictPrinter)
    yield from _find_all_typed_dicts(KeyPath(name), toplevel_dict)


def _find_all_typed_dicts(
    path: KeyPath, value: Any
) -> Iterator[Tuple[KeyPath, TypedDictPrinter]]:
    """Recursive helper fn for a depth-first search through the typed dictionary"""
    if isinstance(value, str):
        return

    if isinstance(value, TypedDictPrinter):
        yield path, value
        for key, val in value.dict_.items():
            yield from _find_all_typed_dicts(KeyPath(f"{path}.{key}"), val)
        return

    try:
        origin = value.__origin__
    except AttributeError:
        return

    if origin == list:
        it = _find_all_typed_dicts(path, value.__args__)
    elif origin == Union:
        it = iter(value.__args__)
    else:
        raise Exception(f"Unsupported type: {value}")

    for val in it:
        yield from _find_all_typed_dicts(path, val)


def accumulate_typed_dicts(
    name: str, dict_: Dict
) -> Dict[KeyPath, List[TypedDictPrinter]]:
    accumulated_dicts: Dict = {}
    for path, typed_dict in find_all_typed_dicts(KeyPath(name), dict_):
        accumulated_dicts.setdefault(path, []).append(typed_dict)
    return accumulated_dicts


some_dict = {
    "name": "foo",
    "cond": True,
    "floaty": 1.0,
    "dict": {"some_key": "blub"},
    "some_list": ["foo", "bar"],
    "heterogenous_list": ["string", 1.0],
    # "heterogenous_list": ["string", 1.0, {"quux": "fox"}],
}

for val in find_all_typed_dicts("Foo", some_dict):
    print(val)

print("\naccumulated:")
print(accumulate_typed_dicts("Foo", some_dict))
