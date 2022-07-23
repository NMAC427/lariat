from __future__ import annotations

from typing import Iterator
from urllib.parse import urlparse

import requests

from lariat.core.parser import FMParser, FMRecord
from lariat.core.query import FMQuery


class FMServer:
    default: FMServer = None

    request_kwargs = {
        "stream": True,
        "verify": True,
        "timeout": 25,
    }

    def __init__(
        self,
        url: str = None,
        username: str = None,
        password: str = None,
    ):
        # Parse URL
        url = urlparse(url)
        self._url = {
            "scheme": url.scheme or "http",
            "hostname": url.hostname,
            "port": url.port or (433 if (url.scheme or "http") == "https" else 80),
            "path": url.path or "/fmi/xml/fmresultset.xml",
        }

        self._base_request_url = "{scheme}://{hostname}:{port}{path}".format(
            **self._url
        )

        # Config
        self.username = username
        self.password = password

        # Init parser
        self.parser = FMParser()

    # DEFAULT

    def set_as_default_server(self):
        FMServer.default = self

    # USER COMMANDS

    def get_db_names(self) -> list[str]:
        query = FMQuery("-dbnames")
        result = self._run_query(query)
        return [record.get_field("database_name") for record in result]

    def get_layout_names(self) -> list[str]:
        query = FMQuery("-layoutnames")
        result = self._run_query(query)
        return [record.get_field("layout_name") for record in result]

    # HELPERS

    def _run_query(self, query) -> Iterator[FMRecord]:
        query_str = query.build_query()
        request_url = self._base_request_url + "?" + query_str

        response = requests.get(
            url=request_url, auth=(self.username, self.password), **self.request_kwargs
        )

        response.raise_for_status()
        return self.parser.parse(response.raw)

    def _run_query_model(self, query, model: type) -> Iterator:
        for record in self._run_query(query):
            yield model._from_fm_record(record)


def _number_caster(value) -> int | float | None:
    # First try to cast to integer
    try:
        return int(value)
    except (ValueError, TypeError):
        pass

    # Then try to cast to a float
    try:
        return float(value)
    except (ValueError, TypeError):
        pass

    # Everything failed -> return NONE
    return None
