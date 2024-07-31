import unittest
from rosetta.cmd.cmds.version import version_parse

class TestVersionParse(unittest.TestCase):

    def test_version_parse(self):
        branch, num_commits, hash = version_parse("v0.2.0-0-g6f9305e")
        self.assertEqual(branch, "v0.2.0")
        self.assertEqual(num_commits, 0)
        self.assertEqual(hash, "g6f9305e")

    def test_version_parse_with_hyphenated_branch_name(self):
        branch, num_commits, hash = version_parse("v0.1.0-alpha-4-g6f9305e")
        self.assertEqual(branch, "v0.1.0-alpha")
        self.assertEqual(num_commits, 4)
        self.assertEqual(hash, "g6f9305e")

        branch, num_commits, hash = version_parse("v0.1.0-beta2-17-gf63950e")
        self.assertEqual(branch, "v0.1.0-beta2")
        self.assertEqual(num_commits, 17)
        self.assertEqual(hash, "gf63950e")

        branch, num_commits, hash = version_parse("v0.1.0-MB-1234-5-g269f05e")
        self.assertEqual(branch, "v0.1.0-MB-1234")
        self.assertEqual(num_commits, 5)
        self.assertEqual(hash, "g269f05e")

    def test_invalid_version_format(self):
        with self.assertRaises(ValueError):
            version_parse("invalid-version-string")

    def test_missing_v_prefix(self):
        branch, num_commits, hash = version_parse("0.2.0-0-g6f9305e")
        self.assertEqual(branch, "0.2.0")
        self.assertEqual(num_commits, 0)
        self.assertEqual(hash, "g6f9305e")

if __name__ == '__main__':
    unittest.main()