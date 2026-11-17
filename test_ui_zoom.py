"""Display scaling checks; no telescope or network operations."""
from types import SimpleNamespace
import tkinter as tk
from tkinter import font
import unittest

from skyqlink_setup import SetupApp
from ui_zoom import scale_argument


class ZoomTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = SetupApp(self.root, zoom_controls=True)
        self.root.update_idletasks()

    def tearDown(self):
        self.app.close()

    def test_zoom_resizes_entries_and_preserves_values_and_reset(self):
        self.app.host.set('192.168.1.123')
        baseline = self.app.port_entry.winfo_reqwidth()
        font_size = font.nametofont('TkDefaultFont', root=self.root).cget('size')
        self.app.zoom.apply(1.5)
        self.assertGreater(self.app.port_entry.winfo_reqwidth(), baseline)
        self.app.zoom.apply(0.7)
        self.assertLess(self.app.port_entry.winfo_reqwidth(), baseline)
        self.app.zoom.apply(1.0)
        self.assertEqual(self.app.port_entry.winfo_reqwidth(), baseline)
        self.assertEqual(font.nametofont('TkDefaultFont', root=self.root).cget('size'), font_size)
        self.assertEqual(self.app.host.get(), '192.168.1.123')
        self.assertIsNone(self.app.motor)
        self.assertFalse(self.app.bridge_enabled.get())

    def test_narrow_window_keeps_full_form_scrollable(self):
        self.root.geometry('640x480')
        self.root.update_idletasks()
        self.app.zoom.apply(2.0)
        canvas = self.app.scroll_canvas
        self.assertGreater(canvas.bbox('all')[2], canvas.winfo_width())
        canvas.xview_moveto(1)
        self.assertGreater(canvas.xview()[0], 0)
        self.app.zoom.fit_width()
        self.assertLess(self.app.zoom.scale, 2.0)

    def test_scaled_rocker_hit_boundary(self):
        rocker = self.app.bridge_switch
        calls = []
        rocker.command = lambda: calls.append(self.app.bridge_enabled.get())
        rocker.configure(state='normal')
        self.app.zoom.apply(0.5)
        rocker.click(SimpleNamespace(x=60))
        self.assertEqual(calls, [True])
        rocker.click(SimpleNamespace(x=20))
        self.assertEqual(calls, [True, False])

    def test_tab_and_section_heading_scale_and_reset(self):
        from tkinter import ttk
        style = ttk.Style(self.root)
        tab_size = self.app.mode_tab_font.cget('size')
        heading_size = self.app.section_heading_font.cget('size')
        self.assertEqual(self.app.mode_tab_font.cget('weight'), 'bold')
        self.assertEqual(self.app.section_heading_font.cget('weight'), 'bold')
        self.app.zoom.apply(1.5)
        self.assertEqual(self.app.mode_tab_font.cget('size'), round(tab_size * 1.5))
        self.assertEqual(self.app.section_heading_font.cget('size'), round(heading_size * 1.5))
        self.assertEqual(tuple(int(str(value)) for value in self.root.tk.splitlist(style.lookup('Mode.TNotebook.Tab', 'padding'))), (24, 15))
        self.app.zoom.apply(1)
        self.assertEqual(self.app.mode_tab_font.cget('size'), tab_size)
        self.assertEqual(self.app.section_heading_font.cget('size'), heading_size)

    def test_invalid_scale_rejected(self):
        for value in ('nan', 'inf', '0', '2.1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                scale_argument(value)


if __name__ == '__main__':
    unittest.main()
