import unittest

from app.textutil import (
    build_chunks,
    detect_contour,
    mask_contacts,
    money_amounts,
    price_is_grounded,
    reciprocal_rank_fusion,
)


class TextUtilTests(unittest.TestCase):
    def test_mask_keeps_price_digits(self):
        masked = mask_contacts("Вилка 5 000–15 000 ₽, телефон +7 (903) 775-50-48, почта a.b@example.com")
        self.assertIn("5 000", masked)
        self.assertNotIn("903", masked)
        self.assertNotIn("example.com", masked)
        self.assertIn("[телефон]", masked)
        self.assertIn("[email]", masked)

    def test_contour(self):
        self.assertEqual(detect_contour("Сколько стоит часовая консультация?"), "personal")
        self.assertEqual(detect_contour("Какой SLA в часах по КПТР?"), "premium")
        self.assertEqual(detect_contour("Консультация за 15 тысяч — это премиальная поддержка?"), "both")
        self.assertEqual(detect_contour("Вы сейчас работаете в ООО «1С-Премиум»?"), "both")
        self.assertEqual(detect_contour("Сколько стоит лицензия 1С:ERP?"), "both")

    def test_price_guard(self):
        personal = ["Стоимость: 5 000–15 000 ₽."]
        self.assertEqual(money_amounts("Вилка 5 000–15 000 ₽."), {"5000", "15000"})
        self.assertTrue(price_is_grounded("Экспертная консультация стоит 5 000–15 000 ₽.", personal))
        self.assertFalse(price_is_grounded("Сопровождение стоит 50 000 ₽ в месяц.", personal))
        self.assertTrue(price_is_grounded("Цены на сайте компании нет.", []))

    def test_rrf_order(self):
        fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
        self.assertEqual(fused[0], "b")

    def test_price_card_is_not_split(self):
        body = "# Форматы\n\n## Экспертная консультация\n\nСтоимость: 5 000–15 000 ₽.\n\nСессия 60–90 минут.\n"
        chunks = build_chunks("KN-02", "personal", "https://komfortnavigator.ru/", "2026-10-31", body)
        joined = "\n".join(chunk["content"] for chunk in chunks)
        self.assertIn("5 000–15 000", joined)
        price_chunks = [chunk for chunk in chunks if "Стоимость:" in chunk["content"]]
        self.assertEqual(len(price_chunks), 1)
        self.assertIn("60–90", price_chunks[0]["content"])

    def test_resume_heading_has_no_old_end_date(self):
        from pathlib import Path

        text = Path("knowledge/KN-06-rezyume.md").read_text(encoding="utf-8")
        self.assertNotIn("июнь 2026", text)
        self.assertIn("по настоящее время", text)


if __name__ == "__main__":
    unittest.main()
