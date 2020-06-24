import typed_dict_generator
import json


def gen_code() -> str:
    with open("test_files/response.json") as f:
        data = json.load(f)
        return typed_dict_generator.generate_typed_dict_code("Response", data)


def test_generated_code():
    from typing_extensions import TypedDict
    from typing import Union, List

    eval(gen_code())

