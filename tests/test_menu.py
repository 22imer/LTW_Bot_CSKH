import re
import unittest
from pathlib import Path

from cskh.menu import TELEGRAM_LIMIT, menu_messages

MENU_FILE = Path(__file__).resolve().parents[1] / "data" / "menu.txt"

SAMPLE = (
    "THỰC ĐƠN TEST (ghi chú nội bộ)\n"
    "Ghi chú giá.\n\n"
    "## Cà phê\n"
    "- Latte & Co (M 38.000đ / L 48.000đ): Sữa <nóng>. [có caffeine, có sữa, đề xuất] Topping thêm: Kem, Thạch.\n"
    "## Topping (giá thêm)\n"
    "- Kem: +15.000đ\n"
)


class MenuRenderTests(unittest.TestCase):
    def setUp(self):
        [self.text] = menu_messages(SAMPLE)

    def test_category_gets_icon_and_bold_uppercase_heading(self):
        self.assertIn("☕ <b>CÀ PHÊ</b>", self.text)
        self.assertIn("🧋 <b>TOPPING (GIÁ THÊM)</b>", self.text)

    def test_item_shows_short_prices_and_flag_icons(self):
        self.assertIn("• <b>Latte &amp; Co</b> — M 38k · L 48k ⚡ 🥛 ⭐", self.text)

    def test_description_and_toppings_on_their_own_lines_and_escaped(self):
        self.assertIn("   Sữa &lt;nóng&gt;.", self.text)
        self.assertIn("   🧋 thêm: Kem, Thạch", self.text)
        self.assertNotIn("<nóng>", self.text)

    def test_topping_price_stays_on_the_title_line(self):
        self.assertIn("• <b>Kem</b> +15k", self.text)

    def test_internal_title_note_is_hidden_and_legend_added(self):
        self.assertIn("☁️ <b>THỰC ĐƠN TEST</b>", self.text)
        self.assertNotIn("ghi chú nội bộ", self.text)
        self.assertIn("⚡ có caffeine", self.text)


class MenuSplitTests(unittest.TestCase):
    def test_split_never_cuts_an_item_in_half(self):
        text = "## Cà phê\n" + "\n".join(
            f"- Món {i} (M 10.000đ): mô tả dài cho món số {i}. [có caffeine, không sữa]" for i in range(40)
        )
        chunks = menu_messages(text, limit=500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 500 for c in chunks))
        joined = "\n".join(chunks)
        for i in range(40):
            self.assertEqual(joined.count(f"<b>Món {i}</b>"), 1)
            # the description line must sit directly under its own title
            self.assertRegex(joined, rf"<b>Món {i}</b>[^\n]*\n   mô tả dài cho món số {i}\.")

    def test_shipped_menu_renders_every_item_within_telegram_limit(self):
        source = MENU_FILE.read_text(encoding="utf-8")
        items = [line for line in source.splitlines() if line.startswith("- ")]
        chunks = menu_messages(source)
        self.assertTrue(all(len(c) <= TELEGRAM_LIMIT for c in chunks))
        self.assertEqual(len(re.findall(r"^• <b>", "\n".join(chunks), flags=re.M)), len(items))


if __name__ == "__main__":
    unittest.main()
