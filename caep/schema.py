#!/usr/bin/env python


import argparse
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, cast

from pydantic import BaseModel, ValidationError

import caep

DEFAULT_SPLIT = ","

DEFAULT_KV_SPLIT = ":"

# Map of pydantic schema types to python types
TYPE_MAPPING: Dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}

# Type of BaseModel Subclasses
BaseModelType = TypeVar("BaseModelType", bound=BaseModel)


class SchemaError(Exception):
    pass


class FieldError(Exception):
    pass


class ArrayInfo(BaseModel):
    array_type: type
    split: str = DEFAULT_SPLIT


class DictInfo(BaseModel):
    dict_type: type
    split: str = DEFAULT_SPLIT
    kv_split: str = DEFAULT_KV_SPLIT


Arrays = Dict[str, ArrayInfo]
Dicts = Dict[str, DictInfo]


def escape_split(
    value: str, split: str = DEFAULT_SPLIT, maxsplit: int = 0
) -> List[str]:
    """
    Helper method to split on specified field
    (unless field is escaped with backslash)
    """

    return [
        re.sub(r"(?<!\\)\\", "", v)
        for v in re.split(rf"(?<!\\){split}", value, maxsplit=maxsplit)
    ]


def split_dict(value: Optional[str], dict_info: DictInfo) -> Dict[str, str]:
    """
    Split string into dictionary

    Arguments:
        value: str      - Value to split
        array: DictInfo - Config object that specifies the type
                          and the value to split items and
                          key/values on
    """
    if value is None or not value.strip():
        return {}

    d: Dict[str, str] = {}

    # Split on specified field, unless they are escaped
    for items in escape_split(value, dict_info.split):

        try:
            # Split key val on first occurence of specified split value
            key, val = escape_split(items, dict_info.kv_split, maxsplit=2)
        except ValueError:
            raise FieldError(f"Unable to split {items} by `{dict_info.kv_split}`")

        d[key.strip()] = dict_info.dict_type(val.strip())

    return d


def split_list(value: str, array: ArrayInfo) -> List[Any]:
    """
    Split string into list

    Arguments:
        value: str       - Value to split
        array: ArrayInfo - Config object that specifies the type
                           and the value to split on
    """
    if value is None or not value.strip():
        return []

    # Split by configured split value, unless it is escaped
    return [array.array_type(v).strip() for v in escape_split(value, array.split)]


def split_arguments(
    args: argparse.Namespace, arrays: Arrays, dicts: Dicts
) -> Dict[str, Any]:
    """
    Loop over argument/values and split by configured split value for dicts and arrays

    Supports escaped values which not be part of the split operation

    Arguments:

        args: argparse.Namespace - Argparse namespace
        arrays: dict[str, ArrayInfo] - Dictionary with field name as key
                                       and ArrayInfo (type + split) as value
        dicts: dict[str, ArrayInfo] -  Dictionary with field name as key
                                       and DictInfo (type + split/kv_split) as value
    """
    args_with_list_split = {}

    for field, value in vars(args).items():

        if field in arrays:
            value = split_list(value, arrays[field])

        elif field in dicts:
            value = split_dict(value, dicts[field])

        args_with_list_split[field] = value

    return args_with_list_split


def build_parser(
    fields: Dict[str, Dict[str, Any]],
    description: str,
    epilog: Optional[str],
) -> Tuple[argparse.ArgumentParser, Arrays]:
    """

    Build argument parser based on pydantic fields

    Return ArgumentParser and fields that are defined as arrays

    """

    # Map of all fields that are defined as arrays
    arrays: Arrays = {}

    # Map of all fields that are defined as objects (dicts)
    dicts: Dicts = {}

    # Add epilog to --help output
    if epilog:
        parser = argparse.ArgumentParser(
            description,
            epilog=epilog,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
    else:
        parser = argparse.ArgumentParser(description)

    # Example data structure for pydantic fields
    # {
    #   "enabled": {
    # 	    "default": false,
    # 	    "description": "Boolean with default value",
    # 	    "title": "Enabled",
    # 	    "type": "boolean"
    #   },
    #   "flag1": {
    # 	    "default": true,
    # 	    "description": "Boolean with default value",
    # 	    "title": "Flag1",
    # 	    "type": "boolean"
    #   },
    #   "str_arg": {
    # 	    "description": "Required String Argument",
    # 	    "title": "Str Arg",
    # 	    "type": "string"
    #   },
    #   "strlist": {
    # 	    "description": "Comma separated list of strings",
    # 	    "items": {
    # 	          "type": "string"
    # 	    },
    # 	    "split": ",",
    # 	    "title": "Strlist",
    # 	    "type": "array"
    #   },
    #     "dict_arg": {
    #     "title": "Dict Arg",
    #     "description": "Dict ",
    #     "default": {},
    #     "kv_split": ":",
    #     "split": ",",
    #     "type": "object",
    #     "additionalProperties": {
    #         "type": "string"
    #     }
    # }

    # Loop over all pydantic schema fields
    for field, schema in fields.items():
        # for lists, dicts and sets we will use the default (str), but
        # for other types we will raise an error if field_type is not specified
        field_type: type = str

        if schema["type"] == "array":
            array_type = TYPE_MAPPING.get(schema["items"]["type"])

            if not array_type:
                raise FieldError(
                    f"Unsupported pydantic type for array field {field}: {schema}"
                )

            arrays[field] = ArrayInfo(
                array_type=array_type, split=schema.get("split", DEFAULT_SPLIT)
            )

            # For arrays (lists, sets etc), we parse as str in caep and split values by
            # configured split value later
            field_type = str

        elif schema["type"] == "object":
            dict_type = TYPE_MAPPING.get(schema["additionalProperties"]["type"])

            if not dict_type:
                raise FieldError(
                    f"Unsupported pydantic type for dict field {field}: {schema}"
                )

            dicts[field] = DictInfo(
                dict_type=dict_type,
                split=schema.get("split", DEFAULT_SPLIT),
                kv_split=schema.get("kv_split", DEFAULT_KV_SPLIT),
            )

        else:

            if schema["type"] not in TYPE_MAPPING:
                raise FieldError(
                    f"Unsupported pydantic type for field {field}: {schema}"
                )

            field_type = TYPE_MAPPING[schema["type"]]

        parser_args: Dict[str, Any] = {}

        if field_type == bool:
            if schema.get("default") is False:
                parser_args["action"] = "store_true"
            elif schema.get("default") is True:
                parser_args["action"] = "store_false"
            else:
                raise FieldError(
                    f"bools without defaults are not supported {field}: {schema}"
                )
        else:
            parser_args = {"type": field_type}

        parser.add_argument(
            f"--{field.replace('_', '-')}",
            help=schema.get("description", "No help provided"),
            default=schema.get("default"),
            **parser_args,
        )

    return parser, arrays, dicts


def load(
    model: Type[BaseModelType],
    description: str,
    config_id: str,
    config_file_name: str,
    section_name: str,
    alias: bool = False,
    opts: Optional[List[str]] = None,
    raise_on_validation_error: bool = False,
    exit_on_validation_error: bool = True,
    epilog: Optional[str] = None,
) -> BaseModelType:

    """

    Load ceap config as derived from pydantic model

    Arguments:

        model: BaseModelType            - Pydantic Model
        description: str                - Argparse description to show on --help
        config_id                       - CAEP config id
        config_file_name                - CAEP config file name
        section_name: str               - CAEP section name from config
        alias: bool                     - Use alias for pydantic schema
        opts: Optional[List[str]]       - Send option to caep (usefull for
                                          testing command line options)
        raise_on_validation_error: bool - Reraise validation errors from pydantic
        exit_on_validation_error: bool  - Exit and print help on validation error
        epilog: str                     - Add epilog text to --help output

    Returns parsed model

    """

    # Get all pydantic fields
    fields = model.schema(alias).get("properties")

    if not fields:
        raise SchemaError(f"Unable to get properties from schema {model}")

    # Build argument parser based on pydantic fields
<<<<<<< HEAD
    parser, arrays = build_parser(fields, description, epilog)
=======
    parser, arrays, dicts = build_parser(fields, description)
>>>>>>> bf7a5e8 (support dicts)

    args = split_arguments(
        args=caep.config.handle_args(
            parser, config_id, config_file_name, section_name, opts=opts
        ),
        arrays=arrays,
        dicts=dicts,
    )

    try:
        return model(**args)
    except ValidationError as e:
        if raise_on_validation_error:
            raise
        else:
            # ValidationError(model='Arguments',
            #                  errors=[{'loc': ('str_arg',),
            #                          'msg': 'none is not an allowed value',
            #                          'type': 'type_error.none.not_allowed'}])

            for error in e.errors():
                argument = cast(str, error.get("loc", [])[0]).replace("_", "-")
                msg = error.get("msg")

                print(f"{msg} for --{argument}\n")

            parser.print_help()
            sys.exit(1)
