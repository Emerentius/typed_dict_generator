# Typed Dict Generator

This script generates Python code for [TypedDicts](https://docs.python.org/3/library/typing.html#typing.TypedDict) from Json. `TypedDict`s are available in the `typing` module from 3.8+ and in `typing_extensions` before that.

## Usage
```bash
$ poetry run python typed_dict_generator.py test_files/response.json 
TypedDict("Response", { "name": str, "cond": bool, "floaty": float, "dict": TypedDict("Dict", { "some_key": str }), "some_list": List[str], "null": None, "heterogenous_list": List[Union[float, str, TypedDict("Heterogenous_List", { "quux": str })]] })
```

The output can be copied into a python file with a few typing imports prepended. Let your autoformatter make the output pretty.

```python
# If you're using a Python version older than 3.8, you will need
# to import TypedDict from typing_extensions or mypy_extensions
from typing import List, Union, TypedDict

Response = TypedDict(
    "Response",
    {
        "name": str,
        "cond": bool,
        "floaty": float,
        "dict": TypedDict("Dict", {"some_key": str}),
        "some_list": List[str],
        "null": None,
        "heterogenous_list": List[
            Union[float, str, TypedDict("Heterogenous_List", {"quux": str})]
        ],
    },
)
```
