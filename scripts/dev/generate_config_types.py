"""This script auto-generates the `qutebrowser/config/configcontainer.py` file."""

from __future__ import annotations

import pathlib
import textwrap
from typing import Union, cast
from collections.abc import Mapping
from typing_extensions import TypeAlias, assert_never

# pylint: disable=unused-import
import qutebrowser.config.config  # noqa: F401, needed to avoid cyclical import errors
# pylint: enable=unused-import

from qutebrowser.config import configdata, configtypes
from qutebrowser.config.configdata import Option


NestedConfig: TypeAlias = dict[str, Union[Option, "NestedConfig"]]


def make_nested_config(config: Mapping[str, Option]) -> NestedConfig:
    """The original configdata.yml defines nested keys using `.`s in a flat tree.

    This function returns a new dict where options are grouped and nested, e.g.
    `'auto_save.session': Option(...)` -> `{'auto_save': {'session': Option(...)}}`
    """
    result = {}
    for key, value in config.items():
        parts = key.split(".")
        current = result
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return result


def _get_type_hint(typ: configtypes.ConfigType) -> str:  # noqa: C901
    if isinstance(typ, configtypes.List):
        return f"list[{get_type_hint(typ.valtype)}]"

    if isinstance(typ, configtypes.Dict):
        return f"Mapping[{get_type_hint(typ.keytype)}, {get_type_hint(typ.valtype)}]"

    if isinstance(typ, configtypes.Bool):
        return "bool"

    valid_values = typ.get_valid_values()
    if valid_values:
        return f'Literal[{", ".join(repr(k) for k in valid_values.values)}]'
    if isinstance(typ, configtypes.MappingType):
        # note: should be redundant, but means we can get exhaustive type matching
        return f'Literal[{", ".join(repr(k) for k in typ.MAPPING.keys())}]'

    if isinstance(
        typ,
        (
            configtypes.String,
            configtypes.FontBase,
            configtypes.QtColor,
            configtypes.QssColor,
            configtypes.Command,
            configtypes.Key,
            configtypes.SessionName,
            configtypes.Url,
            configtypes.File,
            configtypes.UrlPattern,
            configtypes.FormatString,
            configtypes.Directory,
            configtypes.Encoding,
            configtypes.FuzzyUrl,
            configtypes.SearchEngineUrl,
            configtypes.Proxy,
        ),
    ):
        return "str"

    if isinstance(typ, configtypes.Int):
        return "int"

    if isinstance(typ, configtypes.Float):
        return "float"

    if isinstance(typ, configtypes.ListOrValue):
        return f"Union[{get_type_hint(typ.valtype)}, {get_type_hint(typ.listtype)}]"

    if isinstance(typ, configtypes.Perc):
        return "Union[float, int, str]"

    if isinstance(typ, configtypes.PercOrInt):
        return "Union[int, str]"

    if isinstance(typ, configtypes.Regex):
        return "Union[str, re.Pattern[str]]"

    assert_never(typ)


def get_type_hint(typ: configtypes.BaseType) -> str:
    """Turn a config type into a Python type annotation, e.g. `String` -> `'str'`."""
    typ = cast(configtypes.ConfigType, typ)

    inner = _get_type_hint(typ)

    if typ.none_ok:
        return f"Optional[{inner}]"

    return inner


def generate_config_types(config_data: Mapping[str, Option]) -> str:
    """Generate the `ConfigContainer` dataclass and all nested types."""
    output = [
        triple_quote(
            textwrap.dedent("""
                This file defines static types for the `c` variable in `config.py`.

                This is auto-generated from the `scripts/dev/generate_config_types.py` file.

                It is not intended to be used at runtime.

                Example usage:
                ```py
                from typing import TYPE_CHECKING, cast

                if TYPE_CHECKING:
                    from qutebrowser.config.configfiles import ConfigAPI
                    from qutebrowser.config.configcontainer import ConfigContainer

                    # note: these expressions aren't executed at runtime
                    c = cast(ConfigContainer, ...)
                    config = cast(ConfigAPI, ...)
                ```
            """).lstrip()
        ),
        "",
        "# pylint: disable=line-too-long, invalid-name",
        "",
        "from __future__ import annotations",
        "import re",
        "from dataclasses import dataclass",
        "from collections.abc import Mapping",
        "from typing import Optional, Union, Literal",
        "",
        "",
    ]

    def generate_class(
        class_name: str,
        config: NestedConfig,
        *,
        indent: str = "",
        description: str | None = None,
    ) -> list[str]:
        class_def = [
            f"{indent}@dataclass",
            f"{indent}class {class_name}:",
        ]
        if description is not None:
            class_def.append(f"{indent}    {triple_quote(description)}")

        for key, value in config.items():
            if isinstance(value, Option):
                type_hint = get_type_hint(value.typ)
                if value.default is None:
                    class_def.append(f"{indent}    {key}: Optional[{type_hint}]")
                else:
                    class_def.append(f"{indent}    {key}: {type_hint}")

                if value.description:
                    lines = value.description.split("\n")
                    description = "\n\n".join(
                        [
                            line if i == 0 else f"{indent}    {line}"
                            for i, line in enumerate(lines)
                        ]
                    )
                    if not description.endswith("\n") and len(lines) > 1:
                        description += f"\n{indent}    "

                    class_def.append(f"{indent}    {triple_quote(description)}\n")
            elif isinstance(value, dict):
                nested_class_name = "_" + snake_to_camel(key)
                class_def.append(f"{indent}    {key}: {nested_class_name}")
                class_def.extend(
                    generate_class(nested_class_name, value, indent=indent + "    ")
                )
            else:
                assert_never(value)

        return class_def

    nested_config = make_nested_config(config_data)
    output.extend(
        generate_class(
            "ConfigContainer",
            nested_config,
            description="Type for the `c` variable in `config.py`.",
        )
    )

    return "\n".join(output)


def snake_to_camel(name: str) -> str:
    return "".join(word.capitalize() for word in name.split("_"))


def literal(v: str) -> str:
    return '"' + v + '"'


def triple_quote(v: str) -> str:
    """surround the given string with trible double quotes."""
    # some option descriptions use `\+` which isn't a valid escape sequence
    # in python docstrings, so just escape it.
    return '"""' + v.replace(r"\+", r"\\+") + '"""'


def main():
    configdata.init()

    generated_code = generate_config_types(configdata.DATA)

    output_file = (
        pathlib.Path(__file__).parent.parent.parent
        / "qutebrowser"
        / "config"
        / "configcontainer.py"
    )
    output_file.write_text(generated_code)

    print(f"Config types have been written to {output_file}")


if __name__ == "__main__":
    main()
