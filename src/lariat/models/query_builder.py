from __future__ import annotations

import copy
from functools import wraps
from typing import Generic, Literal, Type

from typing_extensions import Self

from lariat._typing import ModelT
from lariat.core.query import FMQuery
from lariat.core.server import FMServer
from lariat.errors import FileMakerError
from lariat.models.fields import Field
from lariat.models.symbolic import FieldExpression, SortExpression


class QueryBuilder(Generic[ModelT]):
    """Query Builder

    Helper class to construct queries.
    """

    def __init__(self, model: ModelT | type[ModelT]):
        self.model = model

        # Query Params
        self._filter: list[FieldExpression] = []
        self._sort: list[SortExpression] = []
        self._max: int | None = None
        self._skip: int | None = None
        self._scripts = dict()

        self._filtered_fields: set[Field] = set()
        self._sorted_fields: set[Field] = set()

    def _clone(self) -> Self:
        c = copy.copy(self)

        # Copy containers
        for k, v in self.__dict__.items():
            if isinstance(v, (list, dict, set)):
                c.__dict__[k] = copy.copy(v)

        return c

    # Building

    def build_query(
        self,
        command: str,
        *,
        filter_=False,
        sort=False,
        max_=False,
        skip=False,
        scripts=False,
    ) -> FMQuery:
        # Construct Query
        db = self.model._meta.db
        layout = self.model._meta.layout

        if db is None:
            raise TypeError(
                f"Missing 'db' in model '{self.model.__name__}' meta options"
            )
        if layout is None:
            raise TypeError(
                f"Missing 'layout' in model '{self.model.__name__}' meta options"
            )

        query = FMQuery(command)
        query.add_param("-db", db)
        query.add_param("-lay", layout)

        # Filter
        if filter_:
            for expr in self._filter:
                field_name = expr.lhs.name
                query.add_field_param(field_name, expr.rhs)
                query.add_field_param(field_name + ".op", expr.op)

        # Sort
        if sort:
            for precedence, expr in enumerate(self._sort, start=1):
                query.add_param(f"-sortfield.{precedence}", expr.field.name)
                query.add_param(f"-sortorder.{precedence}", expr.sort_method)

        # Max
        if max_:
            if m := self._max:
                query.add_param("-max", m)

        # Skip
        if skip:
            if skip := self._skip:
                query.add_param("-skip", skip)

        # Scripts
        if scripts:
            for script_type, (name, param) in self._scripts.items():
                if script_type == "after":
                    s_name = "-script"
                    s_param_name = "-script.param"
                else:
                    s_name = f"-script.{script_type}"
                    s_param_name = f"-script.{script_type}.param"

                query.add_param(s_name, name)
                if param is not None:
                    query.add_param(s_param_name, param)

        return query

    # Chainable Operations

    def filter(self, *args: FieldExpression) -> Self:
        """documentation"""
        c = self._clone()

        # Symbolic Expressions
        for expr in args:
            if not isinstance(expr, FieldExpression):
                raise TypeError(
                    "`filter` expected arguments of type FieldExpression, not"
                    f" '{type(expr).__name__}'"
                )

            # Each field can only appear once per query filter
            if expr.lhs in c._filtered_fields:
                raise ValueError(f"Already specified a filter for {expr.lhs}")
            c._filtered_fields.add(expr.lhs)

            c._filter.append(expr)

        return c

    def sort(self, *args: SortExpression) -> Self:
        c = self._clone()

        for expr in args:
            if not isinstance(expr, SortExpression):
                raise TypeError(
                    "`sort` expected arguments of type SortExpression, not"
                    f" '{type(expr).__name__}'"
                )
            if expr.field in c._sorted_fields:
                raise ValueError(f"Already specified a sort rule for {expr.field}")
            c._sorted_fields.add(expr.field)
            if len(c._sort) >= 9:
                raise ValueError(f"Can't sort by more than 9 fields")

            c._sort.append(expr)

        return c

    def max(self, limit: int) -> Self:
        c = self._clone()
        c._max = limit
        return c

    def skip(self, offset: int) -> Self:
        c = self._clone()
        c._skip = offset
        return c

    def script(
        self,
        script_type: Literal["after", "prefind", "presort"],
        name: str,
        param: str = None,
    ) -> Self:
        c = self._clone()
        if script_type in c._scripts:
            raise ValueError(f"Already defined a {script_type} script")
        if name is None:
            raise TypeError(f"Script name can't be None")
        c._scripts[script_type] = (name, param)
        return c

    # TODO: Related Set


class QuerySet(Generic[ModelT]):
    """Represent a lazy database lookup for a set of objects"""

    def __init__(self, model: type[ModelT]):
        self.model = model
        self._q = QueryBuilder(model)

    def _with(self, q: QueryBuilder):
        c = copy.copy(self)
        c._q = q
        return c

    # Perform queries on database

    def all(self) -> list[ModelT]:
        command = "-find" if self._q._filter else "-findall"
        query = self._q.build_query(
            command,
            filter_=True,
            sort=True,
            max_=True,
            skip=True,
            scripts=True,
        )

        server = FMServer.default
        try:
            return list(server.run_query_model(query, self.model))
        except FileMakerError as e:
            # 401: No records match the request
            if e.code == 401:
                return []
            raise e

    def first_or_none(self) -> ModelT | None:
        command = "-find" if self._q._filter else "-findall"
        query = self._q.max(1).build_query(
            command,
            filter_=True,
            sort=True,
            max_=True,
            skip=True,
            scripts=True,
        )

        server = FMServer.default

        try:
            result = server.run_query_model(query, self.model)
            return result[0]
        except FileMakerError as e:
            # 401: No records match the request
            if e.code == 401:
                return None
            raise e

    # Chainable Operations

    def filter(self, *args: FieldExpression) -> Self:
        return self._with(self._q.filter(*args))

    def sort(self, *args: SortExpression) -> Self:
        return self._with(self._q.sort(*args))

    def max(self, limit: int) -> Self:
        return self._with(self._q.max(limit))

    def skip(self, offset: int) -> Self:
        return self._with(self._q.skip(offset))

    def script_after(self, name: str, param: str = None) -> Self:
        return self._with(self._q.script("after", name, param))

    def script_prefind(self, name: str, param: str = None) -> Self:
        return self._with(self._q.script("prefind", name, param))

    def script_presort(self, name: str, param: str = None) -> Self:
        return self._with(self._q.script("presort", name, param))

    # TODO: Related Set


"""
API Design

QuerySet
    .filter(a, b)  # Condition: a & b
    .filter(x, y)  # Condition: a & b & c & d
    
QuerySet
    .include(a, b)  # Include:  a & b
    .include(x, y)  # Include:  a & b  +  x & y
    .exclude(u, v)  # Include:  a & b  +  x & y  -  u & v

"""
