from __future__ import annotations
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Iterator,
    Set,
    Tuple,
    NewType,
    Protocol,
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

TypeAssignments = Dict[int, Optional[str]]
JsonValue = Optional["list[Any] | dict[str, Any] | str | int | float | bool"]


class Code(Protocol):
    def to_str(self, assignments: TypeAssignments) -> str:
        pass


def camel_case(name: str) -> str:
    return name.title().replace("_", "")


@dataclass(eq=True, frozen=True)
class TypedDictCode(Code):
    """When printed, returns the Python code to generate a TypedDict."""

    name: str
    # Represent the dictionary as tuples so that it can be hashed.
    # It would be nice if the constructor could convert the dictionary
    # but I haven't figured out how to do that with dataclass(frozen=True)
    dict_: Tuple[Tuple[str, Code], ...]

    def to_str(self, assignments: TypeAssignments) -> str:
        assignment = assignments.get(id(self))
        if assignment is not None:
            return assignment

        pairs = (f'"{key}": {value.to_str(assignments)}' for key, value in self.dict_)
        dict_str = "{ " + ", ".join(pairs) + " }"

        dict_str = dict_str.replace("typing.", "")

        return f'TypedDict("{self.name}", {dict_str})'


NoneType = type(None)


@dataclass(eq=True, frozen=True)
class BuiltInCode(Code):
    type_: int | float | str | bool | NoneType

    def to_str(self, assignments: TypeAssignments) -> str:
        # types of built-ins convert to str like this: <class 'classname'>
        # this substitution extracts 'classname' from that
        class_ = re.sub(
            r"<class '(\w+)'>", lambda match: match.group(1), str(self.type_)
        )
        return class_ if class_ != "NoneType" else "None"


@dataclass(eq=True, frozen=True)
class ListCode(Code):
    inner_type: Code

    def to_str(self, assignments: TypeAssignments) -> str:
        return f"List[{self.inner_type.to_str(assignments)}]"


@dataclass(eq=True, frozen=True)
class UnionCode(Code):
    inner_types: Tuple[Code, ...]

    def to_str(self, assignments: TypeAssignments) -> str:
        n_types = len(self.inner_types)
        if n_types == 0:
            return "Any"
        elif n_types == 1:
            return self.inner_types[0].to_str(assignments)
        else:
            type_list = ", ".join(t.to_str(assignments) for t in self.inner_types)
            return f"Union[{type_list}]"


def type_order_key(type_) -> int:
    if isinstance(type_, BuiltInCode):
        order = [int, float, str, bool, NoneType]
        return order.index(type_.type_)
    elif isinstance(type_, UnionCode):
        return 100
    elif isinstance(type_, ListCode):
        return 200
    elif isinstance(type_, TypedDictCode):
        return 300
    else:
        raise Exception(f"Unsupported type: {type_}")


def get_types(key: str, value: JsonValue) -> List[Code]:
    """
    Generate a list of types, sorted such that earlier types do not have dependencies
    on later types. The last element will be the type of the input
    """
    types: List[Code] = []
    _get_type(key, value, types)
    return types


def _get_type(
    key: str,
    value: JsonValue,
    type_assignments: List[Code],
) -> Code:
    code: Code
    if isinstance(value, (type(None), str, int, float, bool)):
        code = BuiltInCode(type(value))  # type: ignore
    elif isinstance(value, list):
        all_types = {_get_type(key, element, type_assignments) for element in value}
        ordered_types = sorted(all_types, key=type_order_key)

        # if there is only 1 type, the Union will collapse
        # into that one type
        code = ListCode(UnionCode(tuple(ordered_types)))
    elif isinstance(value, dict):
        assert key is not None
        types_of_keys = {
            key: _get_type(key, val, type_assignments) for key, val in value.items()
        }
        code = TypedDictCode(key, tuple(types_of_keys.items()))
    else:
        raise ValueError("type not supported")

    # insert new code
    type_assignments.append(code)
    return code


def find_unused_name(name: str, taken_names: Set[str]) -> str:
    # Inefficient as hell, but it's a rare case in most circumstances.
    candidates = itertools.chain([name], (f"{name}{i}" for i in range(2, 10001)))
    unused_name = next((c for c in candidates if c not in taken_names), None)
    if unused_name is None:
        raise Exception(
            "Failed to find unused name. Too many assignments of types with same desired name."
        )
    return unused_name


def generate_typed_dict_code(name: str, dictionary: dict[str, Any]) -> str:
    types = get_types(name, dictionary)
    type_assignments: TypeAssignments = {id(ty): None for ty in types}

    # typed dicts can't be nested, so we generate assignments for them
    # and then refer to TypedDicts nested inside other types by their variable name.

    # Avoid naming conflicts both with built-in types. keywords, types from typing module
    # and other generated types
    # TODO: Add more pre-existing names
    taken_names: Set[str] = {
        "int",
        "str",
        "float",
        "list",
        "List",
        "set",
        "Set",
        "dict",
        "Dict",
        "Iterable",
        "Mapping",
        "Optional",
        "Union",
        "Tuple",
        "type",
        "id",
        "def",
        "for",
        "pass",
        "Any",
        "None",
        "True",
        "False",
    }

    output = ""
    for ty in types:
        if isinstance(ty, TypedDictCode):
            name = find_unused_name(camel_case(ty.name), taken_names)
            taken_names.add(name)
            renamed_type = TypedDictCode(name, ty.dict_)
            output += f"{name} = {renamed_type.to_str(type_assignments)}\n"

            type_assignments[id(ty)] = name

    return output


def find_all_typed_dicts(
    name: str, dict_: dict[str, Any]
) -> Iterator[Tuple[KeyPath, TypedDictCode]]:
    toplevel_dict, type_assignments = get_types(name, dict_)
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
    name: str, dict_: dict
) -> dict[KeyPath, list[TypedDictCode]]:
    accumulated_dicts: dict = {}
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
        click.echo(code, nl=False)
    else:
        click.echo("Json does not represent a dictionary")


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
