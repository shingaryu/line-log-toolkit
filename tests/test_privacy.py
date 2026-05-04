import json
import tempfile
import unittest
from pathlib import Path

from line_log_toolkit.privacy import (
    EntityCandidate,
    PseudonymMap,
    parse_extraction_response,
)


class PrivacyTests(unittest.TestCase):
    def test_parse_extraction_response_accepts_fenced_object(self):
        response = """```json
{"entities":[{"surfaces":["Alice","Alice-san"],"type":"PERSON"},{"surfaces":["Tokyo"],"type":"LOCATION"}]}
```"""

        entities = parse_extraction_response(response)

        self.assertEqual(
            entities,
            [
                EntityCandidate(("Alice", "Alice-san"), "PERSON"),
                EntityCandidate(("Tokyo",), "LOCATION"),
            ],
        )

    def test_map_keeps_existing_pseudonyms_after_reload(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "map.json"
            entity_map = PseudonymMap()
            added = entity_map.add_entities(
                [
                    EntityCandidate(("Alice",), "PERSON"),
                    EntityCandidate(("Tokyo",), "LOCATION"),
                ]
            )
            entity_map.save(path)

            loaded = PseudonymMap.load(path)
            loaded.add_entities(
                [
                    EntityCandidate(("Alice",), "PERSON"),
                    EntityCandidate(("Bob",), "PERSON"),
                ]
            )
            loaded.save(path)

            payload = json.loads(path.read_text(encoding="utf-8"))
            by_surface = {item["surfaces"][0]: item["pseudonym"] for item in payload["entries"]}

        self.assertEqual(added, 2)
        self.assertEqual(by_surface["Alice"], "Person_A")
        self.assertEqual(by_surface["Bob"], "Person_B")
        self.assertEqual(by_surface["Tokyo"], "Location_A")

    def test_pseudonymize_and_restore_prefers_longest_match(self):
        entity_map = PseudonymMap()
        entity_map.add_entities(
            [
                EntityCandidate(("Alice",), "PERSON"),
                EntityCandidate(("Alice Smith",), "PERSON"),
            ]
        )

        pseudonymized = entity_map.pseudonymize("Alice Smith emailed Alice.")
        restored = entity_map.restore(pseudonymized)

        self.assertEqual(pseudonymized, "Person_A emailed Person_B.")
        self.assertEqual(restored, "Alice Smith emailed Alice.")

    def test_surfaces_share_pseudonym_and_restore_as_is_editable(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "map.json"
            entity_map = PseudonymMap()
            entity_map.add_entities(
                [
                    EntityCandidate(("Alice", "Alice-san", "ALICE"), "PERSON"),
                ]
            )
            entity_map.save(path)

            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["entries"][0]["restore_as"] = "Alice Smith"
            path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = PseudonymMap.load(path)
            pseudonymized = loaded.pseudonymize("ALICE called Alice-san.")
            restored = loaded.restore(pseudonymized)

        self.assertEqual(pseudonymized, "Person_A called Person_A.")
        self.assertEqual(restored, "Alice Smith called Alice Smith.")

    def test_saved_map_uses_surfaces(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "map.json"
            entity_map = PseudonymMap()
            entity_map.add_entities(
                [EntityCandidate(("Alice", "Alice-san"), "PERSON")]
            )
            entity_map.save(path)

            payload = json.loads(path.read_text(encoding="utf-8"))
            entry = payload["entries"][0]

        self.assertEqual(entry["surfaces"], ["Alice", "Alice-san"])

    def test_honorific_variants_are_merged(self):
        entity_map = PseudonymMap()
        added = entity_map.add_entities(
            [
                EntityCandidate(("松澤",), "PERSON"),
                EntityCandidate(("松澤さん",), "PERSON"),
            ]
        )

        self.assertEqual(added, 1)
        self.assertEqual(entity_map.pseudonymize("松澤さんから松澤へ"), "Person_AからPerson_Aへ")


    def test_merge_from_reuses_existing_pseudonyms_before_new_entities(self):
        source = PseudonymMap()
        source.add_entities(
            [
                EntityCandidate(("Alice", "Alice-san"), "PERSON"),
                EntityCandidate(("Tokyo",), "LOCATION"),
            ]
        )

        target = PseudonymMap()
        merge_result = target.merge_from(source)
        added = target.add_entities(
            [
                EntityCandidate(("Alice-san",), "PERSON"),
                EntityCandidate(("Bob",), "PERSON"),
            ]
        )

        self.assertEqual(merge_result.imported_count, 2)
        self.assertEqual(merge_result.merged_count, 0)
        self.assertEqual(merge_result.conflict_count, 0)
        self.assertEqual(added, 1)
        self.assertEqual(
            target.pseudonymize("Alice-san and Bob in Tokyo"),
            "Person_A and Person_B in Location_A",
        )

    def test_merge_from_merges_matching_entry_without_changing_target_pseudonym(self):
        source = PseudonymMap()
        source.add_entities([EntityCandidate(("Alice", "Alice-san"), "PERSON")])

        target = PseudonymMap()
        target.add_entities([EntityCandidate(("Alice",), "PERSON")])
        result = target.merge_from(source)

        self.assertEqual(result.imported_count, 0)
        self.assertEqual(result.merged_count, 1)
        self.assertEqual(target.pseudonymize("Alice-san"), "Person_A")


if __name__ == "__main__":
    unittest.main()
