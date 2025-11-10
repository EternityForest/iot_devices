import warnings

TRUE_STRINGS = ("true", "yes", "on", "enable", "active", "enabled", "1")
FALSE_STRINGS = ("false", "no", "off", "disable", "inactive", "disabled", "0")


def str_to_bool(s: str) -> bool:
    "Return a bool value if the str is one of the valid bool strings"
    warnings.warn(
        "str_to_bool is deprecated, do not use old style string based config",
        DeprecationWarning,
    )
    if s.lower() in TRUE_STRINGS:
        return True
    elif s.lower() in FALSE_STRINGS:
        return False
    else:
        raise ValueError("Not a valid boolean string")
