import typed_dict_generator
import json


def gen_code() -> str:
    with open("test_files/response.json") as f:
        data = json.load(f)
        return typed_dict_generator.generate_typed_dict_code("Response", data)


# This test is too strict in its output. We should really be testing
# that mypy accepts the input as being of the generated type.
# def test_generate_typed_dict_code():
#     assert (
#         gen_code()
#         == """Dict2 = TypedDict("Dict2", { "some_key": str })
# HeterogenousList = TypedDict("HeterogenousList", { "quux": str })
# Response = TypedDict("Response", { "name": str, "cond": bool, "floaty": float, "dict": Dict2, "some_list": List[str], "null": None, "heterogenous_list": List[Union[float, str, HeterogenousList]] })"""
#     )


def test_generated_code():
    from typing_extensions import TypedDict
    from typing import Union, List

    exec(gen_code())
