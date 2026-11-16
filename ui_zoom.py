"""Opt-in Tk zoom, retaining baseline measurements to avoid cumulative rounding."""
import math
from tkinter import font, ttk
import tkinter as tk


def scale_argument(value):
    """Validate a startup scale before creating a window."""
    value = float(value)
    if not math.isfinite(value) or not 0.5 <= value <= 2.0:
        raise ValueError('UI scale must be between 0.5 and 2.0')
    return value


class UiZoom:
    """Scale typography and pixel spacing without rebuilding live controls."""
    def __init__(self, app, controls=False):
        self.app, self.root = app, app.root
        self.scale = 1.0
        self.fonts = []
        self.options = []
        self.layouts = []
        self.columns = []
        self.style = ttk.Style(self.root)
        self.rowheight = int(self.style.lookup('Treeview', 'rowheight') or 20)
        self.named = [font.nametofont(name, root=self.root) for name in font.names(self.root)]
        named_names = {str(item) for item in self.named}
        for widget in self.walk(app):
            keys = widget.keys()
            if 'font' in keys:
                original = str(widget.cget('font'))
                if original and original not in named_names:
                    local = font.Font(root=self.root, font=original)
                    widget.configure(font=local)
                    self.fonts.append((local, local.cget('size')))
            for key in ('padding', 'padx', 'pady', 'wraplength'):
                if key in keys:
                    raw = widget.cget(key)
                    values = self.parts(raw)
                    if values:
                        self.options.append((widget, key, tuple(widget.winfo_pixels(v) for v in values)))
            manager = widget.winfo_manager()
            if manager in ('grid', 'pack'):
                raw_info = self.root.tk.splitlist(self.root.tk.call(manager, 'info', widget._w))
                info = dict(zip(raw_info[::2], raw_info[1::2], strict=True))
                for key in ('padx', 'pady', 'ipadx', 'ipady'):
                    values = self.parts(info.get('-' + key, 0))
                    self.layouts.append((widget, manager, key,
                                         tuple(widget.winfo_pixels(v) for v in values)))
            if isinstance(widget, ttk.Treeview):
                for column in widget['columns']:
                    self.columns.append((widget, column, widget.column(column, 'width'),
                                         widget.column(column, 'minwidth')))
        self.fonts.extend((item, item.cget('size')) for item in self.named)
        if controls:
            menu = tk.Menu(self.root)
            view = tk.Menu(menu, tearoff=False)
            view.add_command(label='Zoom in', command=lambda: self.apply(self.scale + 0.1))
            view.add_command(label='Zoom out', command=lambda: self.apply(self.scale - 0.1))
            view.add_command(label='Actual size (100%)', command=lambda: self.apply(1.0))
            view.add_command(label='Fit width', command=self.fit_width)
            menu.add_cascade(label='View', menu=view)
            self.root.configure(menu=menu)

    @staticmethod
    def walk(widget):
        """Include nested text widgets and their surrounding frames."""
        yield widget
        for child in widget.winfo_children():
            yield from UiZoom.walk(child)

    def parts(self, value):
        """Normalize Tk's scalar and list option representations."""
        if isinstance(value, (int, float)):
            return (value,)
        return self.root.tk.splitlist(value)

    def apply(self, value):
        """Change size only; preserve connection, entry and motor-control state."""
        self.scale = min(2.0, max(0.5, value))
        for item, size in self.fonts:
            item.configure(size=(1 if size >= 0 else -1) * max(1, round(abs(size) * self.scale)))
        for widget, key, values in self.options:
            widget.configure(**{key: tuple(round(v * self.scale) for v in values)})
        for widget, manager, key, values in self.layouts:
            self.root.tk.call(manager, 'configure', widget._w, '-' + key,
                              tuple(round(v * self.scale) for v in values))
        for widget, column, width, minimum in self.columns:
            widget.column(column, width=round(width * self.scale), minwidth=round(minimum * self.scale))
        self.style.configure('Treeview', rowheight=round(self.rowheight * self.scale))
        self.app.bridge_switch.set_scale(self.scale)
        self.root.update_idletasks()
        self.app.resize_content()

    def fit_width(self):
        """Fit the current form width, with scrolling below the readable minimum."""
        self.root.update_idletasks()
        self.apply(self.scale * self.app.scroll_canvas.winfo_width() / max(1, self.app.winfo_reqwidth()))
