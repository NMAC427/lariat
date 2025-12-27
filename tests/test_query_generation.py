import pytest
from inline_snapshot import snapshot

from lariat.models import IntField, Model, StringField

from .query_util import format_query


class Person(Model):
    class Meta:
        db = "people"
        layout = "Person"

    name = StringField("Name")
    age = IntField("Age")
    city = StringField("City")


def test_simple_find():
    qs = Person.records().filter(Person.name == "John", Person.age == 30)
    query = qs._q.build_query("-find", filter_=True)

    assert format_query(query) == snapshot("""\
Command: -find
  age: 30
  age.op: eq
  name: ==John\
""")


def test_simple_or_query():
    # (Name == John) OR (Name == Jane)
    qs = Person.records().filter((Person.name == "John") | (Person.name == "Jane"))
    query = qs._q.build_query("-find", filter_=True)

    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: (q1);(q2)
  -q1: ('Name', '==John')
  -q2: ('Name', '==Jane')\
""")


def test_complex_and_or_query():
    # (City == NY AND Age > 20) OR (City == LA)
    qs = Person.records().filter(
        ((Person.city == "NY") & (Person.age > 20)) | (Person.city == "LA")
    )
    query = qs._q.build_query("-find", filter_=True)

    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: (q1,q2);(q3)
  -q1: ('City', '==NY')
  -q2: ('Age', '>20')
  -q3: ('City', '==LA')\
""")


def test_negation_query():
    # NOT (Age > 30)  => Age <= 30
    qs = Person.records().filter(~(Person.age > 30))
    query = qs._q.build_query("-find", filter_=True)

    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: (q1)
  -q1: ('Age', '<=30')\
""")


def test_de_morgan_negation():
    # NOT (Name == John OR Name == Jane) => Name != John AND Name != Jane
    qs = Person.records().filter(~((Person.name == "John") | (Person.name == "Jane")))
    query = qs._q.build_query("-find", filter_=True)

    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: !(q1);!(q2)
  -q1: ('Name', '==Jane')
  -q2: ('Name', '==John')\
""")


def test_distribution():
    # (A | B) & C -> (A & C) | (B & C)
    qs = Person.records().filter(
        ((Person.name == "John") | (Person.name == "Jane")) & (Person.city == "NY")
    )
    query = qs._q.build_query("-find", filter_=True)

    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: (q1,q2);(q3,q4)
  -q1: ('Name', '==John')
  -q2: ('City', '==NY')
  -q3: ('Name', '==Jane')
  -q4: ('City', '==NY')\
""")
