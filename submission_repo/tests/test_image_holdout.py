import unittest

from build.ingest_reviewed_images import OUTPUT, ROOT, read
from eval.check_images import validate


class HoldoutIntegrityTests(unittest.TestCase):
    def test_gold_quotes_exist_and_questions_are_new(self):
        cases = read(ROOT / "eval/image_holdout_v1.json")
        old = read(ROOT / "eval/image_smoke.json")
        validate(cases, read(OUTPUT / "records.json"))
        self.assertEqual(len(cases), 24)
        self.assertEqual(len({c["question"] for c in cases}), len(cases))
        self.assertFalse({c["question"] for c in cases} & {c["question"] for c in old})
        self.assertFalse({c["id"] for c in cases} & {c["id"] for c in old})


if __name__ == "__main__":
    unittest.main()
