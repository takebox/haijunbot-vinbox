# -*- coding: utf-8 -*-
def ot(tag_name: str) -> str:
    """Generate the HTML tag opening marker

    Parameters:
    tag_name -- HTML tag name

    Returns:
    The formatted opening tag string
    """
    return f"<{tag_name}>"


def ct(tag_name: str) -> str:
    """Generate the HTML tag closing marker

    Parameters:
    tag_name -- HTML tag name

    Returns:
    The formatted closing tag string
    """
    return f"</{tag_name}>"
