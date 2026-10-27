import unittest
from pathlib import Path

from cskh.menu import TELEGRAM_LIMIT, menu_messages

MENU_FILE = Path(__file__).resolve().parents[1] / "data" / "menu.txt"


class MenuMessagesTests(unittest.TestCase):
    def test_headings_bold_and_text_escaped(self):
        [chunk] = menu_messages("## Cà phê\n- A & B <i>x</i> (M 10.000đ)\n")
        self.assertEqual(chunk, "<b>Cà phê</b>\n- A &amp; B &lt;i&gt;x&lt;/i&gt; (M 10.000đ)")

    def test_splits_between_lines_without_losing_any(self):
        lines = [f"- Món {i} (M 10.000đ)" for i in range(50)]
        chunks = menu_messages("\n".join(lines), limit=200)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 200 for c in chunks))
        self.assertEqual("\n".join(chunks).splitlines(), lines)

    def test_shipped_menu_fits_telegram_limit(self):
        chunks = menu_messages(MENU_FILE.read_text(encoding="utf-8"))
        self.assertTrue(chunks)
        self.assertTrue(all(len(c) <= TELEGRAM_LIMIT for c in chunks))


if __name__ == "__main__":
    unittest.main()
