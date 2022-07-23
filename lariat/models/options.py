from __future__ import annotations


class ModelOptions:
    # Options that the user can specify
    OPTIONS = {
        "db",
        "layout",
    }

    def __init__(self, meta):
        self.db = None
        self.layout = None
        self.fields = []

        self.meta = meta

    def contribute_to_class(self, cls, name):
        cls._meta = self
        self.model = cls

        # Override values from 'class Meta'.
        if self.meta:
            meta_attrs = self.meta.__dict__.copy()
            for name, value in meta_attrs.items():
                if name.startswith("_"):
                    continue
                if name not in ModelOptions.OPTIONS:
                    raise TypeError(f"'class Meta' got an invalid attribute {name}")
                setattr(self, name, value)

    def add_field(self, field):
        self.fields.append(field)
