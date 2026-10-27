import unittest
from pathlib import Path

from cskh.knowledge import KnowledgeBase, chunk_faq, chunk_menu, fold

DATA = Path(__file__).resolve().parents[1] / "data"
MENU = (DATA / "menu.txt").read_text(encoding="utf-8")
FAQ = (DATA / "faq.md").read_text(encoding="utf-8")


class FoldTests(unittest.TestCase):
    def test_strips_accents_including_d_bar(self):
        self.assertEqual(fold("Trà Đào Cam Sả"), "tra dao cam sa")


class ChunkingTests(unittest.TestCase):
    def test_menu_has_one_chunk_per_item_with_category(self):
        chunks = chunk_menu("## Cà phê\n- Latte (M 50.000đ): ngon\n## Topping\n- Kem: +5.000đ\n")
        self.assertEqual([c.text for c in chunks], ["Cà phê: Latte (M 50.000đ): ngon", "Topping: Kem: +5.000đ"])

    def test_faq_items_keep_their_section_heading(self):
        chunks = chunk_faq("Giới thiệu quán.\n\nThanh toán\n- Tại quầy.\n- Không chuyển khoản.\n")
        self.assertEqual(
            [c.text for c in chunks],
            ["Giới thiệu quán.", "Thanh toán: Tại quầy.", "Thanh toán: Không chuyển khoản."],
        )

    def test_shipped_files_produce_a_chunk_for_every_menu_item(self):
        items = [line for line in MENU.splitlines() if line.startswith("- ")]
        self.assertEqual(len(chunk_menu(MENU)), len(items))
        self.assertTrue(chunk_faq(FAQ))


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase.from_texts(FAQ, MENU)

    def top(self, query, n=1):
        return [c.text for c in self.kb.search(query, limit=n)]

    def test_matches_without_accents_and_ranks_the_named_item_first(self):
        self.assertIn("Trà Đào Cam Sả", self.top("tra dao")[0])
        self.assertIn("Cappuccino", self.top("Cappuccino size L bao nhiêu")[0])

    def test_finds_policy_chunks(self):
        self.assertTrue(any("Giao hàng" in t for t in self.top("giao hàng tận nơi không", 2)))
        self.assertTrue(any("chuyển khoản" in t for t in self.top("thanh toán chuyển khoản", 2)))

    def test_spelling_variant_cafe_maps_to_ca_phe(self):
        self.assertTrue(self.top("cafe", 3))

    def test_empty_stopword_only_or_unknown_queries_return_nothing(self):
        for query in ("", "   ", "có không", "zzzqqq"):
            with self.subTest(query=query):
                self.assertEqual(self.kb.search(query), [])


if __name__ == "__main__":
    unittest.main()
