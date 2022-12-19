# CAEP

Configuration library that supports loading configuration from ini, environment variables
and arguments into a [pydantic](https://docs.pydantic.dev/) schema.

With the pydantic schema you will have a fully typed configuration object that is parsed
at load time.

# Example

```python
#!/usr/bin/env python3
from typing import List

from pydantic import BaseModel, Field

import caep


class Config(BaseModel):

    text: str = Field(description="Required String Argument")
    number: int = Field(default=1, description="Integer with default value")
    switch: bool = Field(default=False, description="Boolean with default value")
    intlist: List[int] = Field(description="Space separated list of ints", split=" ")


# Config/section options below will only be used if loading configuration
# from ini file (under ~/.config)
config = caep.load(
    Config,
    "CAEP Example",
    "caep",  # Find .ini file under ~/.config/caep
    "caep.ini",  # Find .ini file name caep.ini
    "section",  # Load settings from [section] (default to [DEFATULT]
)

print(config)
```

Sample output with a `intlist` read from environment and `switch` from command line:

```bash
$ export INTLIST="1 2 3"
$ ./example.py --text "My value" --switch
text='My value' number=1 switch=True intlist=[1, 2, 3]
```

# Pydantic field types

Pydantic fields should be defined using `Field` and include the `description` parameter
to specify help text for the commandline.

Unless the `Field` has a `default` value, it is a required field that needs to be
specified in the environment, configuration file or on the command line.

Supported/tested types:

### `str`

Standard string argument.

### `int`

Values parsed as integer.

### `float`

Value parsed as float.

### `bool`

Value parsed as booleans. Booleans *must* have a default value, and you can use the configuration
to flip the value. Examples:


| Field                                                      | Input     | Configuration |
| -                                                          | -         | -             |
| `enable: bool = Field(value=False, description="Enable")`  | <NOT SET> | False         |
| `enable: bool = Field(value=False, description="Enable")`  | `yes`     | True          |
| `enable: bool = Field(value=False, description="Enable")`  | `true`    | True          |
| `disable: bool = Field(value=True, description="Disable")` | <NOT SET> | True          |
| `disable: bool = Field(value=True, description="Disable")` | `yes`     | False         |
| `disable: bool = Field(value=True, description="Disable")` | `true`    | False         |

### `List[str]` (`list[str]` for python >= 3.9)

List of strings, split by specified character (default = comma, argument=`split`).

Some examples:

| Field                                              | Input   | Configuration |
| -                                                  | -       | -             |
| `List[int] = Field(description="Ints", split=" ")` | `1 2`   | [1, 2]        |
| `List[str] = Field(description="Strs")`            | `ab,bc` | ["ab", "bc"]  |

### `Set[str]` (`set[str]` for python >= 3.9)

Set, split by specified character (default = comma, argument=`split`).

Some examples:

| Field                                             | Input      | Configuration |
| -                                                 | -          | -             |
| `Set[int] = Field(description="Ints", split=" ")` | `1 2 2`    | {1, 2}        |
| `Set[str] = Field(description="Strs")`            | `ab,ab,xy` | {"ab", "xy"}  |

### `Dict[str, <TYPE>]` (`dict[str, <TYPE>]` for python >= 3.9)

Dictioray of strings, split by specified character (default = comma, argument=`split` for
splitting items and colon for splitting key/value).

Some examples:

| Field                                                | Input                | Configuration            |
| -                                                    | -                    | -                        |
| `Dict[str, str] = Field(description="Dict")`         | `x:a,y:b`            | {"x": "a", "y": "b"}     |
| `Dict[str, int] = Field(description="Dict of ints")` | `a b c:1, d e f:2`   | {"a b c": 1, "d e f": 2} |


# Configuration

Arguments are parsed in two phases. First, it will look for the optional argument `--config`
which can be used to specify an alternative location for the ini file. If not `--config` argument
is given it will look for an optional ini file in the following locations
(`~/.config has presedence`):

- `~/.config/<CONFIG_ID>/<CONFIG_FILE_NAME>` (or directory specified by `$XDG_CONFIG_HOME`)
- `/etc/<CONFIG_FILE_NAME>`

The ini file can contain a `[DEFAULT]` section that will be used for all configurations.
In addition it can have a section that corresponds with `<SECTION_NAME>` that for
specific configuration, that will over override config from `[DEFAULT]`

# Environment variables

The configuration step will also look for environment variables in uppercase and
with `-` replaced with `_`. For the example below it will lookup the following environment
variables:

- $NUMBER
- $BOOL
- $STR_ARG

The configuration presedence are (from lowest to highest):
* argparse default
* ini file
* environment variable
* command line argument

## Validation

## XDG

Helper functions to use [XDG Base Directories](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) are included in `caep.xdg`:

It sill look up `XDG` environment variables like `$XDG_CONFIG_HOME` and use
defaults it now specified.

### `get_xdg_dir`

Generic function to get a `XDG` directory.

The following example with will return a path object to ~/.config/myprog
(if `$XDG_CONFIG_HOME` is not set) and create the directoy if it does not
exist.

```python
get_xdg_dir("myprog", "XDG_CONFIG_HOME", ".config", True)
```

### `get_config_dir`

Shortcut for `get_xdg_dir("CONFIG")`.

### `get_cache_dir`

Shortcut for `get_xdg_dir("CACHE")`.

## CAEP Legacy usage

Prior to version `0.1.0` the recommend usage was to add parser objects manually. This is
still supported, but with this approac you will not get the validation from pydantic:

```python
>>> import caep
>>> import argparse
>>> parser = argparse.ArgumentParser("test argparse")
>>> parser.add_argument('--number', type=int, default=1)
>>> parser.add_argument('--bool', action='store_true')
>>> parser.add_argument('--str-arg')
>>> args = caep.config.handle_args(parser, <CONFIG_ID>, <CONFIG_FILE_NAME>, <SECTION_NAME>)
```
