from datetime import date

from lariat.core.server import FMServer
from lariat.models import DateField, FloatField, IntField, ListField, Model, StringField

# Define some Model


class Person(Model):
    class Meta:
        db = "people"
        layout = "Person"

    name = StringField("Name", non_empty=True)
    date_of_birth = DateField("DateOfBirth", non_empty=True)
    age = IntField("Age", calc=True)
    height = FloatField("Height")


# Connect to Filemaker Server
# fmt: off

server = FMServer(
    url="http://fms.example.com/fmi/xml/fmresultset.xml",
    username="username",
    password="password"
)
server.set_as_default_server()


# Run some queries
johnny_appleseed = Person( #
    name = "Johnny Appleseed",
    date_of_birth = date.today(),
    height = 1.65,
)

johnny_appleseed.save(script_after=("some_script", None))


john_doe = (
    Person.records()
        .filter(Person.name == "John Doe")
        .first_or_none())

print(john_doe)

john_doe.height = 1.82
john_doe.save()


adults = (
    Person.records()
        .filter(Person.age >= 18)
        .sort(Person.name.ascend)
        .max(10)
        .all())

print(adults)

adults[0].delete()


# Fetch a record by its id
john_doe2 = (
    Person.records()
        .record_id(john_doe.record_id)
        .first_or_none())
