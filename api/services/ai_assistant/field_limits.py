"""
Sizes of the receptionist's text fields, shared by the API contracts (``schemas``) and the services that cut what
they store: a value accepted at the door always fits its column.
"""

# One line: a name, a contact, an email address, a business name, a tone (VARCHAR(255) columns).
SHORT_TEXT_MAX_CHARS = 255
# Free text: a visitor's need or message, the owner's note on a request.
LONG_TEXT_MAX_CHARS = 2000
# The random id the widget keeps with a visitor's conversation.
SESSION_ID_MAX_CHARS = 64
# A short label: the receptionist's first name, an appointment type (VARCHAR(64) columns).
LABEL_MAX_CHARS = 64
