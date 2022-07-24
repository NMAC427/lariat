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
    Raw error raised by FileMaker
    """
