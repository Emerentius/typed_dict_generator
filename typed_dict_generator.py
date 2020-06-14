from typing import Dict, Any, Union, List, Optional
from mypy_extensions import TypedDict


def generate_typed_dict(name: str, dict: Dict[str, Any]) -> TypedDict:
    types_of_keys = {key: get_type(key, val) for key, val in dict.items()}
    return TypedDict(name, types_of_keys)


def get_type(key: str, value: Any) -> Union[None, type, List[type], TypedDict]:
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
        return generate_typed_dict(key, value)

    raise ValueError("type not supported")


some_dict = {
    "name": "foo",
    "cond": True,
    "floaty": 1.0,
    "dict": {"some_key": "blub"},
    "some_list": ["foo", "bar"],
}
Foo = generate_typed_dict("Foo", some_dict)

foo = Foo(some_dict)
print(repr(Foo))
print(foo["name"])
