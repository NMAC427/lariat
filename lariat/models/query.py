from __future__ import annotations

from lariat.core.query import FMQuery
from lariat.core.server import FMServer
from lariat.models.fields import SymbolicField, SymbolicFieldExpression, Field


class QuerySet:
    """Represent a lazy database lookup for a set of objects"""

    def __init__(self, model):
        self.model = model

        self._filter = dict()
        self._sort = []
        self._max = None

    def _clone(self) -> QuerySet:
        c = self.__class__(model=self.model)
        c._filter = self._filter.copy()
        c._sort = self._sort.copy()
        c._max = self._max
        return c

    # Perform queries on database

    def get(self):
        pass

    def all(self):
        # Construct Query
        command = "-find" if self._filter else "-findall"
        query = FMQuery(command)

        # Default params
        query.add_param("-db", self.model._meta.db)
        query.add_param("-lay", self.model._meta.layout)

        # Filter
        for field, value in self._filter.items():
            query.add_field_param(field, value)

        # Sort
        for precedence, (field, order) in enumerate(self._sort, start=1):
            query.add_param(f"-sortfield.{precedence}", field)
            if order:
                query.add_param(f"-sortorder.{precedence}", order)

        # Max
        if max := self._max:
            query.add_param("-max", max)

        server = FMServer.default
        return list(server._run_query_model(query, self.model))

    # Chainable Operations

    def filter(self, *args, **kwargs):
        """
        fieldname_op = value

        # Valid operator keywords:

        eq      =value
        cn      *value*
        bw       value*
        ew      *value
        gt      >value
        gte    >=value
        lt      <value
        lte    <=value
        neq    omit, value
        """

        filter = {}

        # Symbolic Expressions
        for expr in args:
            if not isinstance(expr, SymbolicFieldExpression):
                raise ValueError()
            if not isinstance(expr.lhs, Field):
                raise ValueError()
            if isinstance(expr.rhs, (Field, SymbolicFieldExpression)):
                raise ValueError()

            field_name = expr.lhs.name

            filter[field_name] = expr.rhs
            filter[field_name + ".op"] = expr.op

        # Kwarg expressions
        for name, value in kwargs.items():
            components = name.split("__")
            operator = None
            if len(components) >= 2:
                operator = components[-1]
                name = "__".join(components[:-1])

            field_name = self.model._attr_mapping.get(name)
            filter[field_name] = value
            if operator is not None:
                filter[field_name + ".op"] = operator

        # New
        c = self._clone()
        c._filter.update(filter)
        return c

    def sort(self, *args):
        """
        sort('fieldname', '-fieldname', ('fieldname', 'value list'))
              Ascending    Descending                  Value List
        """
        sort = []
        for field in args:
            if isinstance(field, SymbolicField):
                name = field.field.name
                order = field._sort_by or ("descend" if field._neg else "ascend")
                sort.append((name, order))
            elif isinstance(field, str):
                name, order = (
                    (field[1:], "descend")
                    if field.startswith("-")
                    else (field, "ascend")
                )
                sort.append((self._map_to_field(name), order))
            elif isinstance(field, tuple):
                name, order = field
                sort.append((self._map_to_field(name), order))
            else:
                raise ValueError(field)  # TODO: Better error message

        # New
        c = self._clone()
        c._sort.extend(sort)
        assert len(c._sort) <= 9  # TODO: Better error message
        return c

    def max(self, max: int = None):
        c = self._clone()
        c._max = max
        return c

    # Helpers

    def _map_to_field(self, attr: str) -> str:
        return self.model._attr_mapping[attr]
