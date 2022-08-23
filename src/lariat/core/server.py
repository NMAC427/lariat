from __future__ import annotations

from typing import Type
from urllib.parse import urlparse

import httpx

from lariat._typing import ModelT
from lariat.core.parser import FMParser, FMRecord
from lariat.core.query import FMQuery


class FMServer:
    default: FMServer = None

    def __init__(
        self,
        url: str = None,
        username: str = None,
        password: str = None,
    ):
        # Networking
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

        self.username = username
        self.password = password

        self.httpx_client = httpx.Client(
            auth=(self.username, self.password),
            verify=True,
            timeout=10,
        )

        # Init parser
        self.parser = FMParser()

    # DEFAULT

    def set_as_default_server(self):
        FMServer.default = self

    # USER COMMANDS

    def get_db_names(self) -> list[str]:
        query = FMQuery("-dbnames")
        result = self.run_query(query)
        return [record.get_field("database_name") for record in result]

    def get_layout_names(self) -> list[str]:
        query = FMQuery("-layoutnames")
        result = self.run_query(query)
        return [record.get_field("layout_name") for record in result]

    # HELPERS

    def run_query(self, query: FMQuery) -> list[FMRecord]:
        url = self._base_request_url + "?" + query.build_query()
        with self.httpx_client.stream("GET", url) as response:
            response.raise_for_status()
            result, metadata = self.parser.parse(response.iter_raw())
            return result

    def run_query_model(self, query: FMQuery, model: type[ModelT]) -> list[ModelT]:
        return [model._from_fm_record(record) for record in self.run_query(query)]
