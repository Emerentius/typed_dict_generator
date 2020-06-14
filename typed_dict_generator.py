from typing import Dict, Any, Union, List, Optional
from mypy_extensions import TypedDict
import re
from dataclasses import dataclass


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
        all_types = {get_type(key, val) for val in value}
        all_types = all_types or {Any}

        # if there is only 1 type, the Union will collapse
        # into that one type
        return List[Union[tuple(all_types)]]
    if type_ == dict:
        assert key is not None
        types_of_keys = {key: get_type(key, val) for key, val in value.items()}
        return TypedDictPrinter(key, types_of_keys)

    raise ValueError("type not supported")


def generate_typed_dict_code(name: str, dictionary: Dict) -> str:
    return str(get_type(name, dictionary))


some_dict = {
    "name": "foo",
    "cond": True,
    "floaty": 1.0,
    "dict": {"some_key": "blub"},
    "some_list": ["foo", "bar"],
}
code = generate_typed_dict_code("Foo", some_dict)
print(code)
