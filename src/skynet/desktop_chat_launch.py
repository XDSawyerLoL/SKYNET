from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .desktop_chat import ChatWindow


class ComposerSubmitFilter(QObject):
    """Chat-style composer behavior: Enter sends, Shift+Enter inserts a line break."""

    def __init__(self, window: ChatWindow) -> None:
        super().__init__(window)
        self.window = window

    def eventFilter(self, obj, event) -> bool:
        if obj is self.window.entry and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                modifiers = event.modifiers()
                if modifiers & Qt.ShiftModifier:
                    return False
                if not self.window.busy:
                    self.window.send_message()
                return True
        return super().eventFilter(obj, event)


def main() -> None:
    app = QApplication([])
    app.setApplicationName("SKYNET")
    app.setOrganizationName("SKYNET Project")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI Variable", 10))
    window = ChatWindow()
    submit_filter = ComposerSubmitFilter(window)
    window.entry.installEventFilter(submit_filter)
    window._composer_submit_filter = submit_filter  # keep QObject alive for the window lifetime
    window.showMaximized()
    app.exec()


if __name__ == "__main__":
    main()
