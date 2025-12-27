from __future__ import annotations

from lariat.fm_error_codes import FM_ERROR_CODES


class ConversionError(Exception):
    pass


class FieldError(Exception):
    pass


class MissingParamError(Exception):
    pass


class XMLParserError(Exception):
    pass


class FileMakerError(Exception):
    """
    Error raised by FileMaker
    """

    def __init__(self, code: str | int = None):
        if isinstance(code, str):
            try:
                code = int(code)
            except (ValueError, TypeError):
                pass

        self.code = code
        self.description = FM_ERROR_CODES.get(code, None)

    def __str__(self):
        if self.description is not None:
            return f"{self.description} ({self.code})"
        else:
            return FileMakerError(
                f"Error Code = {self.code}; For a list of error codes, visit:\n"
                "https://support.claris.com/s/article/"
                "Error-codes-for-Custom-Web-Publishing-1503692934814"
            )
