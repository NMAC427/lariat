from __future__ import annotations

import datetime
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
        # TODO: Add timezone kwarg

        # Networking
        url = urlparse(url)
        self._url = {
            "scheme": url.scheme or "http",
            "hostname": url.hostname,
            "port": url.port or (443 if (url.scheme or "http") == "https" else 80),
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
        records, _ = self.run_query(query)
        return [record.get_field("database_name") for record in records]

    def get_layout_names(self, db: str) -> list[str]:
        query = FMQuery("-layoutnames")
        query.add_param("-db", db)
        records, _ = self.run_query(query)
        return [record.get_field("layout_name") for record in records]

    def get_metadata(self, db: str, layout: str):
        query = FMQuery("-view")
        query.add_param("-db", db)
        query.add_param("-lay", layout)
        _, metadata = self.run_query(query)
        return metadata

    # HELPERS

    def run_query(self, query: FMQuery) -> list[FMRecord]:
        url = self._base_request_url + "?" + query.build_query()
        with self.httpx_client.stream("GET", url) as response:
            response.raise_for_status()
            records, metadata = self.parser.parse(response.iter_raw())
            return records, metadata

    def run_query_model(self, query: FMQuery, model: type[ModelT]) -> list[ModelT]:
        records, _ = self.run_query(query)
        return [model._from_fm_record(record) for record in records]
