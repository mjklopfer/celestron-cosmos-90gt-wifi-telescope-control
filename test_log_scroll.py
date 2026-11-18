"""Live Tk scroll regressions; no telescope or network access."""
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import unittest
from skyqlink_setup import SetupApp

class LogScrollTests(unittest.TestCase):
    def test_follow_bottom_pause_and_trim(self):
        root = tk.Tk()
        try:
            root.geometry('600x220')
            widget = ScrolledText(root, height=8, wrap='none', state='disabled')
            widget.pack(fill='both', expand=True)
            root.update()
            rows = []
            for index in range(250):
                SetupApp.append_log_record(widget, rows, {}, f'Entry {index}\n')
            root.update()
            self.assertGreater(float(widget.yview()[1]), .999)
            widget.yview_moveto(.4)
            root.update()
            text = widget.get('@0,0', '@0,0 lineend')
            for index in range(250, 275):
                SetupApp.append_log_record(widget, rows, {}, f'Entry {index}\n')
            root.update()
            self.assertEqual(widget.get('@0,0', '@0,0 lineend'), text)
            widget.yview_moveto(1)
            root.update()
            for index in range(275, 1000):
                SetupApp.append_log_record(widget, rows, {}, f'Entry {index}\n')
            root.update()
            widget.yview_moveto(.5)
            root.update()
            text = widget.get('@0,0', '@0,0 lineend')
            SetupApp.append_log_record(widget, rows, {}, 'Trim oldest rows\n')
            root.update()
            self.assertEqual(len(rows), 901)
            self.assertEqual(widget.get('@0,0', '@0,0 lineend'), text)
            widget.yview_moveto(1)
            root.update()
            SetupApp.append_log_record(widget, rows, {}, 'Newest entry\n')
            root.update()
            self.assertGreater(float(widget.yview()[1]), .999)
        finally:
            root.destroy()
