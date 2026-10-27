import json
import tempfile
import unittest
from pathlib import Path

from cskh.stores import load_stores

ROOT = Path(__file__).resolve().parents[1]


class StoreDataTests(unittest.TestCase):
    def test_shipped_store_data_loads(self):
        stores = load_stores(ROOT / "data" / "stores.json")
        self.assertGreaterEqual(len(stores), 1)

    def test_rejects_missing_fields_and_bad_phone(self):
        cases = {
            "missing": {"a": {"name": "x", "address": "y", "phone": "+84900000000"}},
            "bad_phone": {"a": {"name": "x", "address": "y", "phone": "0900000000", "hours": "8-9"}},
        }
        for label, data in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "stores.json"
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_stores(path)


if __name__ == "__main__":
    unittest.main()
