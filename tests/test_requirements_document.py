import copy
import json
import unittest
from pathlib import Path

from requirements.document import DocumentError, check_draft, digest, render, validate_draft, validate_review

FIXTURE = Path(__file__).parent / 'fixtures/requirements/complete.json'


class DocumentTest(unittest.TestCase):
    def setUp(self):
        self.draft = json.loads(FIXTURE.read_text())

    def test_complete_draft_and_deterministic_readable_output(self):
        validate_draft(self.draft, {'message:1'})
        self.assertEqual(check_draft(self.draft), [])
        self.assertEqual(digest(self.draft), digest(copy.deepcopy(self.draft)))
        self.assertIn('居民填写昵称报名', render(self.draft))

    def test_empty_placeholder_and_open_checklist_prevent_completion(self):
        self.draft['sections']['goal'] = 'TODO'
        self.draft['checklist'][1]['status'] = 'open'
        missing = check_draft(self.draft)
        self.assertIn('sections.goal', missing)
        self.assertIn('checklist.audience', missing)

    def test_invalid_shape_reference_and_duplicate_ids_are_rejected(self):
        for mutate in [lambda d: d.update(schema_version=True),
                       lambda d: d['functions'][0].update(sources=['message:99']),
                       lambda d: d['checklist'].append(copy.deepcopy(d['checklist'][0])),
                       lambda d: d.update(confirm=True)]:
            d = copy.deepcopy(self.draft)
            mutate(d)
            with self.assertRaises(DocumentError):
                validate_draft(d, {'message:1'})

    def test_not_applicable_needs_permission_and_explanation(self):
        self.draft['checklist'][0].update(status='not-applicable', answer='不需要')
        self.assertIn('checklist.goal', check_draft(self.draft))
        self.draft['checklist'][4].update(status='not-applicable', answer='')
        self.assertIn('checklist.constraints', check_draft(self.draft))

    def test_checklist_changes_invalidate_hash(self):
        old = digest(self.draft)
        self.draft['checklist'][0]['answer'] += '补充'
        self.assertNotEqual(old, digest(self.draft))

    def test_review_cannot_pass_blocking_findings_or_wrong_version(self):
        review = {'reply': '通过', 'version': 1, 'hash': digest(self.draft), 'verdict': 'PASS', 'findings': []}
        validate_review(review, 1, digest(self.draft))
        review['findings'] = [{'id': 'F1', 'location': 'functions', 'evidence': '原文',
                               'expected': '补充', 'problem': '遗漏', 'blocking': True}]
        with self.assertRaises(DocumentError):
            validate_review(review, 1, digest(self.draft))
        review['findings'] = []
        with self.assertRaises(DocumentError):
            validate_review(review, 2, digest(self.draft))
