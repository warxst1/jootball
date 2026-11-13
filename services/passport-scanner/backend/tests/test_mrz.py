import unittest
from datetime import date

from app.mrz import check_digit, parse_td3

FIRST = "P<UTOTESTER<<MIRA<NOVA".ljust(44, "<")
SECOND = "ZX12345672UTO0410151F3110315<<<<<<<<<<<<<<<8"


class Td3Tests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 6)

    def test_icao_checksum_examples(self):
        self.assertEqual(check_digit("520727"), "3")
        self.assertEqual(check_digit("AB2134<<<"), "5")

    def test_synthetic_td3(self):
        result = parse_td3(FIRST, SECOND, today=self.today)
        self.assertEqual(result["status"], "review_required")
        self.assertTrue(all(check["status"] == "PASS" for check in result["checks"].values()))
        self.assertEqual(result["data"]["passport_number"], "ZX1234567")
        self.assertEqual(result["data"]["first_name"], "MIRA NOVA")
        self.assertEqual(result["data"]["last_name"], "TESTER")
        self.assertEqual(result["data"]["issuing_country"], "UTO")
        self.assertEqual(result["data"]["nationality"], "UTO")
        self.assertEqual(result["data"]["sex"], "F")
        self.assertEqual(result["data"]["date_of_expiry"], "2031-10-31")

    def test_ambiguous_birth_date(self):
        result = parse_td3(FIRST, SECOND, today=self.today)
        self.assertIsNone(result["data"]["date_of_birth"])
        self.assertEqual(result["dates"]["date_of_birth"]["status"], "ambiguous")
        self.assertEqual(result["dates"]["date_of_birth"]["candidates"], ["1904-10-15", "2004-10-15"])

    def test_single_character_error(self):
        result = parse_td3(FIRST, SECOND[:9] + "0" + SECOND[10:], today=self.today)
        self.assertEqual(result["status"], "checksum_failed")
        self.assertEqual(result["checks"]["passport_number"]["status"], "FAIL")
        self.assertEqual(result["checks"]["composite"]["status"], "FAIL")
        self.assertEqual(result["checks"]["date_of_birth"]["status"], "PASS")

    def test_invalid_structure(self):
        self.assertIsNone(parse_td3(FIRST[:-1], SECOND))
        self.assertIsNone(parse_td3(FIRST, SECOND + "<"))
        self.assertIsNone(parse_td3(FIRST, SECOND[:20] + "2" + SECOND[21:]))


if __name__ == "__main__":
    unittest.main()
