from typing import (
    Dict,
    Any,
    Union,
    List,
    Set,
    Iterator,
    Iterable,
    Tuple,
    NewType,
)
import re
import itertools
from dataclasses import dataclass

# The KeyPath is the sequence of key accesses required to get to a certain
# value, represented by `key1.key2.key3` etc.
# All TypedDicts under the same path are likely to be of the same type, so we need
# to be able to clearly identify them so that the generated dicts for multiple
# examples can be unified.
KeyPath = NewType("KeyPath", str)


class Code:
    pass


@dataclass(eq=True, frozen=True)
class TypedDictCode(Code):
    """When printed, returns the Python code to generate a TypedDict."""

    name: str
    # Represent the dictionary as tuples so that it can be hashed.
    # It would be nice if the constructor could convert the dictionary
    # but I haven't figured out how to do that with dataclass(frozen=True)
    dict_: Tuple[Tuple[str, Any], ...]

    def __str__(self) -> str:
        pairs = (f'"{key}": {value}' for key, value in self.dict_)
        dict_str = "{ " + ", ".join(pairs) + " }"

        dict_str = dict_str.replace("typing.", "")

        return f'TypedDict("{self.name.title()}", {dict_str})'


NoneType = type(None)


@dataclass(eq=True, frozen=True)
class BuiltInCode(Code):
    type_: Union[int, float, str, bool, NoneType]

    def __str__(self) -> str:
        # types of built-ins convert to str like this: <class 'classname'>
        # this substitution extracts 'classname' from that
        return re.sub(r"<class '(\w+)'>", lambda match: match.group(1), str(self.type_))


@dataclass(eq=True, frozen=True)
class ListCode(Code):
    inner_type: Code

    def __str__(self) -> str:
        return f"List[{self.inner_type}]"


@dataclass(eq=True, frozen=True)
class UnionCode(Code):
    inner_types: List[Code]

    def __str__(self) -> str:
        n_types = len(self.inner_types)
        if n_types == 0:
            return "Any"
        elif n_types == 1:
            return str(self.inner_types[0])
        else:
            type_list = ", ".join(str(t) for t in self.inner_types)
            return f"Union[{type_list}]"


def get_type(
    key: str, value: Union[None, List[Any], Dict[str, Any], str, int, float, bool]
) -> Code:
    if isinstance(value, (type(None), str, int, float, bool)):
        return BuiltInCode(type(value))  # type: ignore
    if isinstance(value, list):
        all_types = {get_type(key, element) for element in value}

        # if there is only 1 type, the Union will collapse
        # into that one type
        return ListCode(UnionCode(list(all_types)))
    if isinstance(value, dict):
        assert key is not None
        types_of_keys = {key: get_type(key, val) for key, val in value.items()}
        return TypedDictCode(key, tuple(types_of_keys.items()))

    raise ValueError("type not supported")


def generate_typed_dict_code(name: str, dictionary: Dict[str, Any]) -> str:
    return str(get_type(name, dictionary))


def find_all_typed_dicts(
    name: str, dict_: Dict[str, Any]
) -> Iterator[Tuple[KeyPath, TypedDictCode]]:
    toplevel_dict = get_type(name, dict_)
    assert isinstance(toplevel_dict, TypedDictCode)
    yield from _find_all_typed_dicts(KeyPath(name), toplevel_dict)


def _find_all_typed_dicts(
    path: KeyPath, code: Code
) -> Iterator[Tuple[KeyPath, TypedDictCode]]:
    """Recursive helper fn for a depth-first search through the typed dictionary"""
    if isinstance(code, BuiltInCode):
        return

    if isinstance(code, TypedDictCode):
        yield path, code
        for key, val in code.dict_:
            yield from _find_all_typed_dicts(KeyPath(f"{path}.{key}"), val)
        return

    if isinstance(code, ListCode):
        yield from _find_all_typed_dicts(path, code.inner_type)
    elif isinstance(code, UnionCode):
        for type_ in code.inner_types:
            yield from _find_all_typed_dicts(path, type_)
    else:
        raise Exception(f"Unsupported type: {code}")


def accumulate_typed_dicts(
    name: str, dict_: Dict
) -> Dict[KeyPath, List[TypedDictCode]]:
    accumulated_dicts: Dict = {}
    for path, typed_dict in find_all_typed_dicts(KeyPath(name), dict_):
        accumulated_dicts.setdefault(path, []).append(typed_dict)
    return accumulated_dicts


# ============================================================================
import click
import json
import os


@click.command()
@click.argument(
    "file", type=click.Path(exists=True, dir_okay=False, readable=True, allow_dash=True)
)
def cli(file: str):
    try:
        with click.open_file(file) as f:
            data = json.load(f)
    except Exception as e:
        click.echo(f"Input must be a valid json file. Error: {e}")
        return
    filename = os.path.basename(file)
    filename, _ = os.path.splitext(filename)

    if isinstance(data, dict):
        code = generate_typed_dict_code(filename.title(), data)
        click.echo(code)
    else:
        click.echo("Json does not represent a dictionary")


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
