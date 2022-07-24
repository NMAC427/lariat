from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from lariat.models.model import Model


T = TypeVar("T")
ModelT = TypeVar("ModelT", bound="Model")
