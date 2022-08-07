from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Literal

from lariat._typing import T
from lariat.models import fields

if TYPE_CHECKING:
    from lariat.models.fields import Field


class FieldExpression(Generic[T]):
    OP_T = Literal["eq", "cn", "bw", "ew", "gt", "gte", "lt", "lte", "neq"]

    def __init__(self, lhs: Field[T], op: OP_T, rhs: T):
        if not isinstance(lhs, fields.Field):
            raise TypeError(f"`lhs` must be a Field, not '{type(lhs).__name__}'")
        if not isinstance(op, str):
            raise TypeError(f"`op` must be a string, not '{type(op).__name__}'")
        if isinstance(rhs, FieldExpression):
            raise TypeError(f"Can't chain field expressions")
        if isinstance(rhs, SField):
            raise TypeError(f"Field expression can't contain two fields")

        self.lhs = lhs
        self.op = op
        self.rhs = rhs

    def __repr__(self):
        return f"<FieldExpression {self.lhs} {self.op} {self.rhs!r}>"


class SortExpression:
    def __init__(self, field: Field, method: str):
        assert isinstance(field, fields.Field)
        assert isinstance(method, str)

        self.field = field
        self.sort_method = method

    def __repr__(self):
        return f"<SortExpression {self.field} '{self.sort_method}'>"


####


class SField(Generic[T]):
    """Symbolic Field

    Interface to reference and manipulate a column symbolically
    """

    def __init__(self, field: Field[T]):
        self._field = field

    # Sorting

    @property
    def ascend(self):
        return SortExpression(self._field, "ascend")

    @property
    def descend(self):
        return SortExpression(self._field, "descend")

    def sort_by(self, value_list: str):
        assert isinstance(value_list, str)
        return SortExpression(self._field, value_list)

    # Filtering

    def __eq__(self, other: T):
        return FieldExpression(self._field, "eq", other)

    def __ne__(self, other: T):
        return FieldExpression(self._field, "neq", other)

    def __gt__(self, other: T):
        return FieldExpression(self._field, "gt", other)

    def __ge__(self, other: T):
        return FieldExpression(self._field, "gte", other)

    def __lt__(self, other: T):
        return FieldExpression(self._field, "lt", other)

    def __le__(self, other: T):
        return FieldExpression(self._field, "lte", other)


class IntSField(SField[int]):
    ...


class FloatSField(SField[float]):
    ...


class BoolSField(SField[bool]):
    ...


class StringSField(SField[str]):
    def contains(self, value: T):
        return FieldExpression(self._field, "cn", value)

    def startswith(self, value: T):
        return FieldExpression(self._field, "bw", value)

    def endswith(self, value: T):
        return FieldExpression(self._field, "ew", value)
