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


def test_shared_negation():
    # (A & ~B) | (C & ~B) -> Valid
    qs = Person.records().filter(
        ((Person.name == "A") & ~(Person.city == "B"))
        | ((Person.name == "C") & ~(Person.city == "B"))
    )
    query = qs._q.build_query("-find", filter_=True)
    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: (q1);!(q2);(q3);!(q4)
  -q1: ('Name', '==A')
  -q2: ('City', '==B')
  -q3: ('Name', '==C')
  -q4: ('City', '==B')\
""")


def test_omit_only_chain():
    # ~A | ~B
    qs = Person.records().filter(Person.name != "A").filter(Person.name != "B")
    query = qs._q.build_query("-find", filter_=True)

    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: !(q1);!(q2)
  -q1: ('Name', '==A')
  -q2: ('Name', '==B')\
""")


def test_subset_negation():
    # (A & ~B & ~C) | (D & ~B) -> Valid (G1 >= G2)
    qs = Person.records().filter(
        ((Person.name == "A") & ~(Person.city == "B") & ~(Person.age == 10))
        | ((Person.name == "D") & ~(Person.city == "B"))
    )
    query = qs._q.build_query("-find", filter_=True)
    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: (q1);!(q2);!(q3);(q4);!(q5)
  -q1: ('Name', '==A')
  -q2: ('Age', '=10')
  -q3: ('City', '==B')
  -q4: ('Name', '==D')
  -q5: ('City', '==B')\
""")


def test_reordering_negation():
    # A | (B & ~C) -> Valid (reordered to (B & ~C) | A)
    qs = Person.records().filter(
        (Person.name == "A") | ((Person.name == "B") & ~(Person.city == "C"))
    )
    query = qs._q.build_query("-find", filter_=True)
    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: (q1);!(q2);(q3)
  -q1: ('Name', '==B')
  -q2: ('City', '==C')
  -q3: ('Name', '==A')\
""")


def test_disjoint_negation_fail():
    # (A & ~B) | (C & ~D) -> Invalid
    qs = Person.records().filter(
        ((Person.name == "A") & ~(Person.city == "B"))
        | ((Person.name == "C") & ~(Person.city == "D"))
    )
    with pytest.raises(ValueError, match="Cannot represent query"):
        qs._q.build_query("-find", filter_=True)


def test_mixed_negation_fail():
    # (A & ~B) | C | (D & ~E) -> Invalid
    # N sets: {B}, {}, {E}.
    # Sorted: {B}, {E}, {}.
    # {B} not superset of {E}. Fail.
    qs = Person.records().filter(
        ((Person.name == "A") & ~(Person.city == "B"))
        | (Person.name == "C")
        | ((Person.name == "D") & ~(Person.city == "E"))
    )
    with pytest.raises(ValueError, match="Cannot represent query"):
        qs._q.build_query("-find", filter_=True)


def test_string():
    # (Name has word "Manager") OR (Name contains "Director")
    qs = Person.records().filter(
        (Person.name.has_word("Manager")) | (Person.name.contains("Director"))
    )
    query = qs._q.build_query("-find", filter_=True)

    assert format_query(query) == snapshot("""\
Command: -findquery
  -query: (q1);(q2)
  -q1: ('Name', '=Manager')
  -q2: ('Name', '*Director*')\
""")
