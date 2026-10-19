"""Parser tests do not import or run a model."""
import unittest

from shared_task import COMMON_INSTRUCTION, parse_task


class ParseTaskTests(unittest.TestCase):
    def test_math_candidates_are_user_supplied(self):
        task = parse_task("2+3?\nA. 4\nB. 5\nC. 6")
        self.assertEqual(task["question"], "2+3?")
        self.assertEqual(task["choices"], {"A": "4", "B": "5", "C": "6"})
        self.assertEqual(task["instruction"], COMMON_INSTRUCTION)
        self.assertEqual(set(task), {"question", "choices", "instruction", "task_sha256"})

    def test_robot_is_the_same_contract(self):
        task = parse_task("A cube is held above the table. Put it down.\nA) Lower it onto the table\nB) Lift it higher")
        self.assertEqual(task["choices"]["A"], "Lower it onto the table")
        self.assertEqual(task["instruction"], COMMON_INSTRUCTION)
        self.assertNotIn("expected", task)

    def test_korean_arbitrary_content_and_punctuation(self):
        task = parse_task(" 대한민국의 수도는? \nA． 부산\nB: 서울\nC） 제주")
        self.assertEqual(task["question"], "대한민국의 수도는?")
        self.assertEqual(task["choices"], {"A": "부산", "B": "서울", "C": "제주"})

    def test_multiline_content_preserved_and_crlf_normalized(self):
        task = parse_task("  First line\r\n\r\n  second line  \r\n A.  keep  two  spaces \r\n\r\n B. second \r\n")
        self.assertEqual(task["question"], "First line\n\n  second line")
        self.assertEqual(task["choices"], {"A": "keep  two  spaces", "B": "second"})

    def test_ten_choices(self):
        task = parse_task("Select a letter.\n" + "\n".join(f"{letter}. value {letter}" for letter in "ABCDEFGHIJ"))
        self.assertEqual(list(task["choices"]), list("ABCDEFGHIJ"))

    def test_stable_hash_and_meaningful_changes(self):
        first = parse_task("2+3?\nA. 4\nB. 5")
        normalized_equivalent = parse_task(" 2+3? \r\nA) 4 \r\nB: 5\r\n")
        self.assertEqual(first["task_sha256"], normalized_equivalent["task_sha256"])
        self.assertNotEqual(first["task_sha256"], parse_task("2+4?\nA. 4\nB. 5")["task_sha256"])
        self.assertNotEqual(first["task_sha256"], parse_task("2+3?\nA. 5\nB. 4")["task_sha256"])
        self.assertEqual(len(first["task_sha256"]), 64)

    def test_missing_candidates(self):
        for value in ("", "2+3?", "Question\nA. only one"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "보기 2개 이상"):
                parse_task(value)

    def test_invalid_or_missing_question_and_answers(self):
        for value, error in (("A. one\nB. two", "질문"),
                             ("Question\nA. \nB. two", "보기 A의 내용"),
                             ("Question\nA. one\nB:\t", "보기 B의 내용")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, error):
                parse_task(value)

    def test_duplicate_and_order_rejected(self):
        cases = (("Question\nA. one\nA. two", "중복"),
                 ("Question\nB. one\nC. two", "순서"),
                 ("Question\nA. one\nC. two", "순서"),
                 ("Question\na. one\nb. two", "대문자"),
                 ("Question\nA. one\nB. two\nK. eleven", "A부터 J"))
        for value, error in cases:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, error):
                parse_task(value)

    def test_no_unlabelled_continuation_or_expected_answer_line(self):
        for extra in ("a continuation", "정답: B", "Answer: B", "1. third", "AB. third"):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "각 줄"):
                parse_task(f"Question\nA. one\nB. two\n{extra}")

    def test_length_limits(self):
        for value, error in (("x" * 2001, "2,000"),
                             ("x" * 1601 + "\nA. one\nB. two", "1,600"),
                             ("Question\nA. " + "x" * 301 + "\nB. two", "300")):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                parse_task(value)
        task = parse_task("x" * 1600 + "\nA. one\nB. two")
        self.assertEqual(len(task["question"]), 1600)
        task = parse_task("Question\nA. " + "x" * 300 + "\nB. two")
        self.assertEqual(len(task["choices"]["A"]), 300)

    def test_non_text_input(self):
        for value in (None, {}, 5):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "텍스트"):
                parse_task(value)


if __name__ == "__main__":
    unittest.main()
