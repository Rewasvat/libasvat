import click
from enum import Enum
from imgui_bundle import imgui
from libasvat.imgui.colors import Colors


class LogType(str, Enum):
    """Possible types of a Logger message."""
    INFO = "INFO"
    GOOD = "GOOD"
    WARNING = "WARNING"
    ERROR = "ERROR"

    @property
    def color_rgba(self):
        """Gets the RGBA color associated with this log type (for use with IMGUI)."""
        mapping = {
            self.INFO: Colors.white,
            self.GOOD: Colors.green,
            self.WARNING: Colors.yellow,
            self.ERROR: Colors.red,
        }
        return mapping[self]

    @property
    def color_name(self):
        """Gets the color name (a string) associated with this log type (for use with Click)."""
        mapping = {
            self.INFO: "white",
            self.GOOD: "green",
            self.WARNING: "yellow",
            self.ERROR: "red",
        }
        return mapping[self]


class LogMessage:
    """Represents a message saved by a Logger object."""

    def __init__(self, tag: str, message: str, logtype: LogType):
        self.tag = tag
        self.message = message
        self.logtype = logtype

    def styled(self):
        """Returns a click-styled version of this logs's string representation."""
        return click.style(str(self), fg=self.logtype.color_name)

    def draw(self):
        """Draws this log message using IMGUI."""
        imgui.text_colored(self.logtype.color_rgba, str(self))

    def __str__(self):
        if self.tag is not None and self.tag != "":
            return f"[{self.tag}] {self.message}"
        return self.message

    def to_json(self):
        """Converts this object to a JSON representation of itself for persistence."""
        return vars(self).copy()

    @classmethod
    def from_json(cls, json_data: dict):
        """Loads a instance of this class based on the given JSON_DATA dict."""
        data = json_data.copy()
        data["logtype"] = LogType(data["logtype"])
        obj = cls(None, None, None)
        obj.__dict__.update(data)
        return obj


class Logger:
    """Utility to store messages with metadata, which can then be printed to the console
    or draw onscreen with IMGUI."""

    def __init__(self, tag: str = None):
        self._tag = tag
        self.messages: list[LogMessage] = []

    def log(self, message: str, logtype: LogType, output=False):
        """Logs a message with the given LogType."""
        msg = LogMessage(self._tag, message, logtype)
        self.messages.append(msg)
        if output:
            click.echo(msg.styled())

    def get_logs(self):
        """Generator of messages from this Logger."""
        return (msg for msg in self.messages)

    def clear(self):
        """Clear all logs stored in this logger instance."""
        self.messages.clear()

    def info(self, message: str, output=False):
        """Logs a INFO-type message."""
        self.log(message, LogType.INFO, output=output)

    def good(self, message: str, output=False):
        """Logs a GOOD-type message."""
        self.log(message, LogType.GOOD, output=output)

    def warning(self, message: str, output=False):
        """Logs a WARNING-type message."""
        self.log(message, LogType.WARNING, output=output)

    def error(self, message: str, output=False):
        """Logs a ERROR-type message."""
        self.log(message, LogType.ERROR, output=output)

    def to_json(self):
        """Converts this object to a JSON representation of itself for persistence."""
        data = vars(self).copy()
        data["messages"] = []
        for msg in self.messages:
            data["messages"].append(msg.to_json())
        return data

    @classmethod
    def from_json(cls, json_data: dict):
        """Loads a instance of this class based on the given JSON_DATA dict."""
        data = json_data.copy()
        obj = cls()
        messages: list[dict] = data.pop("messages")
        obj.__dict__.update(data)
        for msg_data in messages:
            obj.messages.append(LogMessage.from_json(msg_data))
        return obj
