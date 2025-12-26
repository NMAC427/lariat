from __future__ import annotations

import datetime
import decimal
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic

from lariat._typing import T
from lariat.errors import ConversionError, FieldError
from lariat.models import symbolic as sym

if TYPE_CHECKING:
    from lariat.models import Model


class Field(Generic[T], ABC):
    def __init__(self, name: str, not_empty=False, lenient=True, calc=False):
        """
        :param name: The name of the field in the FileMaker layout.
        :param not_empty: If the value can be None or not.
        :param lenient: Bool specifying if type conversion should be lenient or strict.
        :param calc: Bool specifying if the field is the result of a calculation
            or not. Only fields with calc=False can be set.
        """
        self.name = name
        self.not_empty = not_empty
        self.lenient = lenient
        self.calc = calc

        self.attname = None

    def contribute_to_class(self, cls, name):
        self.attname = name
        setattr(cls, name, self)
        cls._meta.add_field(self)

    def __get__(self, instance: Model, owner=None):
        if instance is None:
            # If __get__ gets called on the class instead of an instance.
            return self.symbolic()

        instance_state = instance.__dict__
        if self.attname not in instance_state:
            if self.not_empty:
                raise ValueError(
                    f"Value for field '{self.attname}' not set (can't be empty)."
                )
            return None

        return instance_state[self.attname]

    def __set__(self, instance: Model, value: T):
        if self.calc:
            raise AttributeError("Can't set field the value of a calculated field.")
        self.force_set(instance, value)

    def force_set(self, instance: Model, value: T):
        instance_state = instance.__dict__
        if value is None:
            if self.not_empty:
                raise FieldError(
                    f"Field '{self.attname}' is non empty. It's value can't be set to"
                    " None."
                )
            instance_state[self.attname] = None
        else:
            instance_state[self.attname] = self.to_python(value)

    def __repr__(self):
        return f"<{type(self).__name__} '{self.name}'>"

    @abstractmethod
    def to_python(self, value) -> T:
        """
        Convert the input value to the correct Python data type for this
        field. If this conversion fails, a lariat.exception.ConversionError
        should get raised.
        """

    @abstractmethod
    def symbolic(self) -> sym.SField[T]: ...


class IntField(Field[int]):
    regex = re.compile("[^0-9.]")

    def to_python(self, value):
        try:
            return int(value)
        except (TypeError, ValueError) as e:
            # Try to convert lenient
            if self.lenient:
                value = self.regex.sub("", value)
                value = value.split(".")[0]

                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass

            if self.not_empty:
                raise ConversionError(e)
            return None

    def symbolic(self):
        return sym.IntSField(self)

    def __get__(self, instance, owner=None) -> int | sym.IntSField:
        return super().__get__(instance, owner)


class FloatField(Field[float]):
    regex = re.compile("[^0-9.]")

    def to_python(self, value: str):
        try:
            return float(value)
        except (TypeError, ValueError) as e:
            # Try to convert lenient
            if self.lenient:
                try:
                    value = self.regex.sub("", value)
                    return float(value)
                except (TypeError, ValueError):
                    pass

            if self.not_empty:
                raise ConversionError(e)
            return None

    def symbolic(self):
        return sym.FloatSField(self)

    def __get__(self, instance, owner=None) -> float | sym.FloatSField:
        return super().__get__(instance, owner)


class DecimalField(Field[decimal.Decimal]):
    regex = re.compile("[^0-9.]")
    context = decimal.Context(prec=16)

    def to_python(self, value):
        try:
            return self.context.create_decimal(value)
        except (TypeError, ValueError, decimal.InvalidOperation) as e:
            # Try to convert lenient
            if self.lenient:
                try:
                    value = self.regex.sub("", str(value))
                    return self.context.create_decimal(value)
                except (TypeError, ValueError, decimal.InvalidOperation):
                    pass

            if self.not_empty:
                raise ConversionError(e)
            return None

    def symbolic(self):
        return sym.DecimalSField(self)

    def __get__(self, instance, owner=None) -> decimal.Decimal | sym.DecimalSField:
        return super().__get__(instance, owner)


class StringField(Field[str]):
    def to_python(self, value):
        if isinstance(value, str):
            return value
        return str(value)

    def symbolic(self):
        return sym.StringSField(self)

    def __get__(self, instance, owner=None) -> str | sym.StringSField:
        return super().__get__(instance, owner)


class BoolField(Field[bool]):
    def to_python(self, value):
        if value in (True, False):
            # 1/0 are equal to True/False. bool() converts former to latter.
            return bool(value)
        if value in ("t", "true", "True", "1", "yes"):
            return True
        if value in ("f", "false", "False", "0", "no"):
            return False
        if self.not_empty:
            raise ConversionError(f"Couldn't convert value {value!r} to a boolean.")

    def symbolic(self):
        return sym.BoolSField(self)

    def __get__(self, instance, owner=None) -> bool | sym.BoolSField:
        return super().__get__(instance, owner)


class DateTimeField(Field[datetime.datetime]):
    PATTERN = "%m/%d/%Y %H:%M:%S"

    def to_python(self, value):
        date = datetime.datetime.strptime(value, self.PATTERN)
        if date is None and self.not_empty:
            raise ConversionError(f"Couldn't convert {value} to a datetime.")
        return date

    def symbolic(self):
        return sym.DateTimeSField(self)

    def __get__(self, instance, owner=None) -> datetime.datetime | sym.DateTimeSField:
        return super().__get__(instance, owner)


class DateField(Field[datetime.date]):
    PATTERN = "%m/%d/%Y"

    def to_python(self, value):
        date = datetime.datetime.strptime(value, self.PATTERN)
        if date is None and self.not_empty:
            raise ConversionError(f"Couldn't convert {value} to a date.")
        return date.date()

    def symbolic(self):
        return sym.DateSField(self)

    def __get__(self, instance, owner=None) -> datetime.date | sym.DateSField:
        return super().__get__(instance, owner)


class TimeField(Field[datetime.time]):
    PATTERN = "%H:%M:%S"

    def to_python(self, value):
        time = datetime.datetime.strptime(value, self.PATTERN)
        if time is None and self.not_empty:
            raise ConversionError(f"Couldn't convert {value} to a time.")
        return time

    def symbolic(self):
        return sym.TimeSField(self)

    def __get__(self, instance, owner=None) -> datetime.time | sym.TimeSField:
        return super().__get__(instance, owner)


class ListField(Generic[T]):
    def __init__(
        self, field_name: str, values, field_type: type[Field[T]], field_kwargs=None
    ):
        if field_kwargs is None:
            field_kwargs = {}

        self.fields = []
        for value in values:
            field = field_type(field_name % value, **field_kwargs)
            self.fields.append(field)

        self.attname = None

    def contribute_to_class(self, cls, name):
        self.attname = name

        setattr(cls, name, self)
        cls._meta.add_list_field(self)

    def __get__(self, instance: Model, owner=None):
        return ListFieldGetSet(self, instance)

    def __set__(self, instance: Model, value):
        raise AttributeError("Can't set list field.")

    def force_set(self, instance: Model, value):
        raise AttributeError("Can't set list field.")


class ListFieldGetSet(Generic[T]):
    def __init__(self, field: ListField[T], instance: Model):
        self._field = field
        self._instance = instance

    def __repr__(self):
        return repr(list(self))

    def __iter__(self):
        for field in self._field.fields:
            yield field.__get__(self._instance)

    def __getitem__(self, item) -> sym.SField[T]:
        field = self._field.fields[item]
        return field.__get__(self._instance)

    def __setitem__(self, key, value):
        field = self._field.fields[key]
        return field.__set__(self._instance, value)
