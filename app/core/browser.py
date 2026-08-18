from seleniumbase import Driver
import asyncio

driver = None
driver_lock = asyncio.Lock()


def get_driver() -> Driver:
    if driver is None:
        raise RuntimeError("Browser has not been initialized")

    return driver


def uc_open_with_reconnect(url: str, reconnect_time: int = 6) -> None:
    get_driver().uc_open_with_reconnect(
        url,
        reconnect_time=reconnect_time,
    )


def get_page_source() -> str:
    return get_driver().page_source


def get_title() -> str:
    return get_driver().get_title()


def get_current_url() -> str:
    return get_driver().get_current_url()


def is_element_visible(selector: str) -> bool:
    return get_driver().is_element_visible(selector)


def click(selector: str) -> None:
    get_driver().click(selector)


def type(selector: str, text: str) -> None:
    get_driver().type(selector, text)


def clear(selector: str) -> None:
    get_driver().clear(selector)


def get_text(selector: str) -> str:
    return get_driver().get_text(selector)


def sleep(seconds: float) -> None:
    get_driver().sleep(seconds)


def find_element(by: str, value: str):
    return get_driver().find_element(by, value)


def find_elements(by: str, value: str):
    return get_driver().find_elements(by, value)


def execute_script(script: str, *args):
    """Executes JavaScript in the current browser window/frame."""
    return get_driver().execute_script(script, *args)


def get(*args, **kwargs):
    """Executes JavaScript in the current browser window/frame."""
    return get_driver().get(*args, **kwargs)


def wait_for_element(*args, **kwargs):
    return get_driver().wait_for_element(*args, **kwargs)


def press_keys(*args, **kwargs):
    return get_driver().press_keys(*args, **kwargs)


def wait_for_element_present(*args, **kwargs):
    return get_driver().wait_for_element_present(*args, **kwargs)


def wait_for_page_load(*args, **kwargs):
    return get_driver().wait_for_page_load(*args, **kwargs)


def wait_for_ready_state_complete(*args, **kwargs):
    return get_driver().wait_for_ready_state_complete(*args, **kwargs)


def is_element_present(*args, **kwargs):
    return get_driver().is_element_present(*args, **kwargs)

