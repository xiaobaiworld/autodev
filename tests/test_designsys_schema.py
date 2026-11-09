import unittest

from designsys import schema as s


REQ = dict()
REQ["type"] = "object"
REQ["required"] = ["a"]
REQ["properties"] = dict(a=dict(type="string"))


class KeywordTests(unittest.TestCase):
    def check(self, schema, value):
        return s.validate(value, schema)

    def test_valid_value_has_no_errors(self):
        self.assertEqual(self.check(REQ, dict(a="x")), [])

    def test_missing_required_is_reported_with_its_path(self):
        errs = self.check(REQ, dict())
        self.assertEqual(len(errs), 1)
        self.assertIn("a", errs[0]["message"])

    def test_wrong_type_is_reported(self):
        errs = self.check(dict(type="string"), 5)
        self.assertEqual(errs[0]["path"], "$")

    def test_bool_is_not_an_integer(self):
        self.assertTrue(self.check(dict(type="integer"), True))
        self.assertEqual(self.check(dict(type="integer"), 3), [])

    def test_enum_and_const(self):
        self.assertEqual(self.check(dict(enum=["a", "b"]), "a"), [])
        self.assertTrue(self.check(dict(enum=["a", "b"]), "c"))
        self.assertEqual(self.check(dict(const=1), 1), [])
        self.assertTrue(self.check(dict(const=1), 2))

    def test_array_items_and_min_items(self):
        schema = dict(type="array", minItems=1, items=dict(type="string"))
        self.assertEqual(self.check(schema, ["a"]), [])
        self.assertTrue(self.check(schema, []))
        errs = self.check(schema, ["a", 2])
        self.assertEqual(errs[0]["path"], "$[1]")

    def test_additional_properties_false_rejects_unknown_keys(self):
        props = dict(a=dict())
        schema = dict(type="object", properties=props, additionalProperties=False)
        self.assertTrue(self.check(schema, dict(a=1, zzz=2)))

    def test_pattern_and_string_length(self):
        schema = dict(type="string", pattern="^A[0-9]{2}$", minLength=3)
        self.assertEqual(self.check(schema, "A01"), [])
        self.assertTrue(self.check(schema, "B01"))

    def test_ref_to_local_definition(self):
        defs = dict(id=dict(type="string", pattern="^T"))
        item = {"$ref": "#/$defs/id"}
        schema = {"$defs": defs, "type": "array", "items": item}
        self.assertEqual(self.check(schema, ["T1"]), [])
        self.assertTrue(self.check(schema, ["X1"]))

    def test_unresolvable_ref_is_an_error_not_a_pass(self):
        with self.assertRaisesRegex(s.SchemaError, "引用"):
            self.check({"$ref": "#/$defs/missing"}, 1)

    def test_unsupported_keyword_is_rejected_not_silently_ignored(self):
        names = ("oneOf", "anyOf", "allOf", "not", "if", "patternProperties", "dependentRequired")
        for kw in names:
            with self.assertRaisesRegex(s.SchemaError, kw):
                self.check({kw: []}, 1)

    def test_unsupported_keyword_in_an_unvisited_branch_is_still_rejected(self):
        inner = dict(oneOf=[])
        schema = dict(type="object", properties=dict(a=inner))
        with self.assertRaisesRegex(s.SchemaError, "oneOf"):
            self.check(schema, dict())

    def test_unsupported_keyword_inside_defs_is_rejected_even_if_unused(self):
        schema = {"$defs": {"x": {"anyOf": []}}, "type": "string"}
        with self.assertRaisesRegex(s.SchemaError, "anyOf"):
            self.check(schema, "ok")

    def test_unknown_type_in_an_unvisited_branch_is_still_rejected(self):
        inner = dict(type="datetime")
        schema = dict(type="object", properties=dict(a=inner))
        with self.assertRaises(s.SchemaError):
            self.check(schema, dict())

    def test_annotation_keywords_are_allowed(self):
        url = "https://json-schema.org/draft/2020-12/schema"
        schema = {"$schema": url, "title": "t", "description": "d", "type": "string"}
        self.assertEqual(self.check(schema, "x"), [])

    def test_unknown_type_name_is_an_error_not_a_pass(self):
        with self.assertRaises(s.SchemaError):
            self.check(dict(type="datetime"), "x")


if __name__ == "__main__":
    unittest.main()
