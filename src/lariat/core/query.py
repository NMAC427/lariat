# https://help.claris.com/en/server-custom-web-publishing-guide.pdf
from __future__ import annotations

import dataclasses
from urllib.parse import urlencode

from lariat.errors import MissingParamError


class FMQuery:
    # Description of all valid query commands
    @dataclasses.dataclass
    class CommandDescription:
        required: set[str] = dataclasses.field(default_factory=set)
        optional: set[str] = dataclasses.field(default_factory=set)
        field_names: bool = dataclasses.field(default=False)

    _c_db_lay = {"-db", "-lay"}
    _c_layr = {"-lay.response"}
    _c_script = {
        "-script",
        "-script.param",
        "-script.prefind",
        "-script.prefind.param",
        "-script.presort",
        "-script.presort.param",
    }
    _c_find = {"-recid", "-lop", "-op", "-max", "-skip", "-sortorder", "-sortfield"}

    _commands = {
        "-dbnames": CommandDescription(),
        "-delete": CommandDescription(
            required=_c_db_lay | {"-recid"},
            optional=_c_script,
        ),
        "-edit": CommandDescription(
            required=_c_db_lay | {"-recid"},
            optional=_c_script | {"-modid"},
            field_names=True,
        ),
        "-find": CommandDescription(
            required=_c_db_lay,
            optional=_c_layr | _c_script | _c_find,
            field_names=True,
        ),
        "-findany": CommandDescription(
            required=_c_db_lay,
            optional=_c_layr | _c_script,
        ),
        "-findall": CommandDescription(
            required=_c_db_lay,
            optional=_c_layr | _c_script | _c_find,
        ),
        "-layoutnames": CommandDescription(
            required={"-db"},
        ),
        "-new": CommandDescription(
            required=_c_db_lay,
            optional=_c_script,
            field_names=True,
        ),
        "-view": CommandDescription(
            required={"-db", "-lay"},
        ),
    }

    def __init__(self, command: str):
        # The query command. Every query must contain exactly one such command.
        self.command = command

        self.params = dict()
        self.field_params = dict()

    def add_param(self, name: str, value):
        self.params[name.lower()] = str(value)

    def add_field_param(self, name: str, value):
        self.field_params[name.lower()] = value

    def build_query(self):
        command = self.command
        command_desc = self._commands[command]

        # Build params
        params = self.params

        # Validate params
        params_set = set(params.keys())
        if missing_params := command_desc.required - params_set:
            raise MissingParamError(missing_params)
        if unused_params := params_set - command_desc.required - command_desc.optional:
            print(f"WARNING: Unused parameters {unused_params}.")
        if self.field_params and not command_desc.field_names:
            print(f"WARNING: Command {command} doesn't take field names as argument.")

        # Build query string
        params = params | self.field_params
        return command + "&" + urlencode([*params.items()], doseq=False)
