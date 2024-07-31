import unittest

import semantic_version

from rosetta.core.catalog.version import lib_version_parse, lib_version_compare


class TestSemanticVersion(unittest.TestCase):

    def test_semantic_version(self):
        self.assertIsNotNone(semantic_version.Version("0.2.0"))

        with self.assertRaises(ValueError):
            self.assertIsNotNone(semantic_version.Version("v0.2.0"))


class TestLibVersionParse(unittest.TestCase):

    def test_lib_version_parse(self):
        branch, num_commits, hash = lib_version_parse("v0.2.0-0-g6f9305e")
        self.assertEqual(branch, "v0.2.0")
        self.assertEqual(num_commits, 0)
        self.assertEqual(hash, "g6f9305e")

        branch, num_commits, hash = lib_version_parse("v0.1.0-55-g8397417")
        self.assertEqual(branch, "v0.1.0")
        self.assertEqual(num_commits, 55)
        self.assertEqual(hash, "g8397417")

    def test_lib_version_parse_with_hyphenated_branch_name(self):
        branch, num_commits, hash = lib_version_parse("v0.1.0-alpha-4-g6f9305e")
        self.assertEqual(branch, "v0.1.0-alpha")
        self.assertEqual(num_commits, 4)
        self.assertEqual(hash, "g6f9305e")

        branch, num_commits, hash = lib_version_parse("v0.1.0-beta2-17-gf63950e")
        self.assertEqual(branch, "v0.1.0-beta2")
        self.assertEqual(num_commits, 17)
        self.assertEqual(hash, "gf63950e")

        branch, num_commits, hash = lib_version_parse("v0.1.0-MB-1234-5-g269f05e")
        self.assertEqual(branch, "v0.1.0-MB-1234")
        self.assertEqual(num_commits, 5)
        self.assertEqual(hash, "g269f05e")

    def test_invalid_lib_version_format(self):
        with self.assertRaises(ValueError):
            lib_version_parse("invalid-version-string")

        with self.assertRaises(ValueError):
            lib_version_parse("")

    def test_missing_v_prefix(self):
        branch, num_commits, hash = lib_version_parse("0.2.0-0-g6f9305e")
        self.assertEqual(branch, "0.2.0")
        self.assertEqual(num_commits, 0)
        self.assertEqual(hash, "g6f9305e")


class TestLibVersionCompare(unittest.TestCase):

    def test_equal_versions(self):
        self.assertEqual(lib_version_compare("1.0.0-0-g123", "1.0.0-0-g123"), 0)

    def test_greater_version(self):
        self.assertTrue(lib_version_compare("1.0.1-0-g123", "1.0.0-0-g123") > 0)
        self.assertTrue(lib_version_compare("1.1.1-0-g123", "1.1.0-0-g123") > 0)
        self.assertTrue(lib_version_compare("2.1.1-0-g123", "2.1.0-0-g123") > 0)
        self.assertTrue(lib_version_compare("20.1.0-0-g123", "9.1.0-0-g123") > 0)

    def test_lesser_version(self):
        self.assertTrue(lib_version_compare("1.0.0-0-g123", "1.0.1-0-g123") < 0)
        self.assertTrue(lib_version_compare("1.1.0-0-g123", "1.1.1-0-g123") < 0)
        self.assertTrue(lib_version_compare("2.0.0-0-g123", "2.0.1-0-g123") < 0)
        self.assertTrue(lib_version_compare("9.0.0-0-g123", "20.0.0-0-g123") < 0)

    def test_with_hyphenated_branch(self):
        self.assertTrue(lib_version_compare("1.0.0-aaa-0-g123", "1.0.0-0-g123") < 0)
        self.assertTrue(lib_version_compare("1.0.0-alpha-0-g123", "1.0.0-0-g123") < 0)
        self.assertTrue(lib_version_compare("1.0.0-beta-0-g123", "1.0.0-alpha-0-g123") > 0)
        self.assertTrue(lib_version_compare("1.0.0-alpha-0-g123", "1.0.0-beta-0-g123") < 0)
        self.assertTrue(lib_version_compare("1.0.0-alpha1-0-g123", "1.0.0-alpha2-0-g123") < 0)


if __name__ == '__main__':
    unittest.main()