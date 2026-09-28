"""
The page hooks the receptionist video films, as agreed with the demo host.

Each hook is the ``data-capture`` attribute the demo host sets for the capture, or else the element's class.
"""

LAUNCHER_SELECTOR = '[data-capture="launcher"], .ai-launcher'
PANEL_SELECTOR = '[data-capture="panel"], .ai-panel'
# Every quick-reply chip carries the attribute: the first one stands in for the example on a page without it.
FIRST_CHIP_SELECTOR = "[data-capture-chip], .ai-chips button"
EXAMPLE_CHIP_SELECTOR = '[data-capture="example-chip"], .ai-chip--example'
APPOINTMENT_CHIP_SELECTOR = '[data-capture="appointment-chip"], .ai-chip--appointment'

MESSAGE_SELECTOR = "[data-capture-message], .ai-m"
VISITOR_MESSAGE_SELECTOR = '[data-capture-message="user"], .ai-m--user'
RECEPTIONIST_MESSAGE_SELECTOR = '[data-capture-message="assistant"], .ai-m--assistant'

CLIENT_HOME_SELECTOR = '[data-capture="client-home"], .cs-home'
REQUEST_ROW_SELECTOR = '[data-capture="client-home"] [data-capture="request-row"], .cs-home .cs-row'
EXAMPLE_BANNER_SELECTOR = '[data-capture="example-banner"], .cs-example'
