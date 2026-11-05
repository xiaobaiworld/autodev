import unittest
from cockpit.claim import claim_panes, ClaimError

ROLES = ["claude-opus", "codex", "agy"]
W = "pro1 / 1"


def term(addr, where=W, state="live"):
    return {"address": addr, "where": where, "state": state}


LS = [term("t14"), term("t1b"), term("t18"), term("t19"), term("t99", where="other / 1")]
LABELS = {"t1b": {"role": "claude-opus"}, "t18": {"role": "codex"}, "t19": {"role": "agy"}}


def run(ls=LS, labels=LABELS, fallback=None, self_addr="t14"):
    return claim_panes(ls, lambda a: labels.get(a, {}), self_addr, ROLES, fallback)


class ClaimTest(unittest.TestCase):
    def test_complete(self):
        self.assertEqual(run(), {"claude-opus": "t1b", "codex": "t18", "agy": "t19"})

    def test_missing_one_names_the_role(self):
        labels = {k: v for k, v in LABELS.items() if k != "t19"}
        with self.assertRaisesRegex(ClaimError, "agy"):
            run(labels=labels)

    def test_duplicate_label_rejected(self):
        labels = dict(LABELS, t19={"role": "codex"})
        with self.assertRaisesRegex(ClaimError, "codex"):
            run(labels=labels)

    def test_wrong_label_ignored_then_missing(self):
        labels = dict(LABELS, t19={"role": "typo"})
        with self.assertRaisesRegex(ClaimError, "agy"):
            run(labels=labels)

    def test_self_not_in_list(self):
        with self.assertRaisesRegex(ClaimError, "t14"):
            run(ls=[t for t in LS if t["address"] != "t14"])

    def test_other_space_label_not_claimed(self):
        labels = dict(LABELS, t99={"role": "agy"})
        labels.pop("t19")
        with self.assertRaisesRegex(ClaimError, "agy"):
            run(labels=labels)

    def test_fallback_used_when_labels_missing(self):
        fb = {"claude-opus": "t1b", "codex": "t18", "agy": "t19"}
        self.assertEqual(run(labels={}, fallback=fb), fb)

    def test_fallback_address_outside_space_rejected(self):
        fb = {"claude-opus": "t1b", "codex": "t18", "agy": "t99"}
        with self.assertRaisesRegex(ClaimError, "t99"):
            run(labels={}, fallback=fb)

    def test_fallback_duplicate_address_rejected(self):
        fb = {"claude-opus": "t1b", "codex": "t1b", "agy": "t19"}
        with self.assertRaisesRegex(ClaimError, "t1b"):
            run(labels={}, fallback=fb)

    def test_label_and_fallback_disagree(self):
        fb = {"claude-opus": "t18", "codex": "t1b", "agy": "t19"}
        with self.assertRaisesRegex(ClaimError, "不一致"):
            run(fallback=fb)

    def test_fallback_never_claims_self(self):
        fb = {"claude-opus": "t14", "codex": "t18", "agy": "t19"}
        with self.assertRaisesRegex(ClaimError, "t14"):
            run(labels={}, fallback=fb)


if __name__ == "__main__":
    unittest.main()
