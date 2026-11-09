"""The real integration's model response cannot write unapproved files."""
import json
import unittest

from f_legal_workbench_design import parse_files, aggregate_reviews


class IntegrationOutputTests(unittest.TestCase):
    def test_text_and_json_preserve_content(self):
        data = {'a.md': 'business input', 'data.json': {'entities': []}}
        self.assertEqual(parse_files(json.dumps({'files': data}), set(data)), data)

    def test_extra_path_is_rejected_before_writing(self):
        for path in ('../outside.txt', '/tmp/outside.txt', 'unexpected.md'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                parse_files(json.dumps({'files': {'a.md': 'ok', path: 'bad'}}), {'a.md'})

    def test_missing_or_wrong_envelope_is_rejected(self):
        for value in ({'files': {}}, {'other': {}}, {'files': [], 'ok': True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_files(json.dumps(value), {'a.md'})

    def test_pass_cannot_hide_high_finding(self):
        finding = dict(id='x', severity='high', location='api', problem='mismatch', expected='align')
        review = dict(verdict='PASS', scope='contracts', findings=[finding], requirement_coverage=['FR-02'])
        self.assertIn('verdict: REWORK', aggregate_reviews([review]))
        review['verdict'] = 'BLOCK'
        self.assertIn('verdict: BLOCK', aggregate_reviews([review]))

    def test_review_requires_evidence_and_preserves_findings(self):
        with self.assertRaises(ValueError):
            aggregate_reviews([])
        finding = dict(id='x', severity='medium', location='api', problem='mismatch', expected='align')
        review = dict(verdict='PASS', scope='contracts', findings=[finding], requirement_coverage=['FR-02'])
        text = aggregate_reviews([review])
        self.assertIn('verdict: PASS', text)
        self.assertIn('mismatch', text)
        self.assertIn('FR-02', text)


if __name__ == '__main__':
    unittest.main()
