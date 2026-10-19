"""Domain-neutral multiple-choice contract shared by every live demo model.

The input contains a question followed by 2-10 candidates labelled A through J.
This module only parses the supplied task; it never invents candidates or answers.
"""
import hashlib
import json
import re


COMMON_INSTRUCTION = (
    "Choose the single best answer to the question from the supplied candidates. "
    "Use only information in the question and general knowledge. "
    "Reply with exactly one uppercase letter: the chosen candidate ID. Do not generate an explanation."
)

_CHOICE_LINE = re.compile(r"^\s*([A-Za-z])\s*[.):．：）]\s*(.*)$")
_NO_CHOICES = "질문 아래에 A. ... / B. ... 형식으로 보기 2개 이상을 입력해 주세요."


def parse_task(inputtext):
    """Return the exact question, ordered candidates, common instruction and hash.

    Candidate values and the question retain their internal whitespace. Only line
    endings and outer whitespace are normalized. Blank separator lines are allowed;
    other lines after the first candidate must be another labelled candidate.
    """
    if not isinstance(inputtext, str):
        raise ValueError("질문과 보기를 텍스트로 입력해 주세요.")
    normalized = inputtext.replace("\r\n", "\n").replace("\r", "\n")
    if len(normalized) > 2000:
        raise ValueError("전체 입력은 2,000자 이하로 입력해 주세요.")

    question_lines = []
    choices = {}
    in_choices = False
    for line in normalized.split("\n"):
        match = _CHOICE_LINE.fullmatch(line)
        if match is None:
            if in_choices:
                if line.strip():
                    raise ValueError(
                        "보기 이후의 각 줄은 A. ... / B. ... 형식이어야 합니다. "
                        "질문과 추가 설명은 첫 번째 보기 위에 입력해 주세요."
                    )
            else:
                question_lines.append(line)
            continue

        in_choices = True
        candidate_id, answer = match.groups()
        if candidate_id not in "ABCDEFGHIJ":
            raise ValueError("보기 이름은 대문자 A부터 J까지만 사용할 수 있습니다.")
        if candidate_id in choices:
            raise ValueError(f"보기 {candidate_id}가 중복되었습니다.")
        expected = chr(ord("A") + len(choices))
        if candidate_id != expected:
            raise ValueError("보기는 A부터 시작해 A, B, C 순서로 연속해서 입력해 주세요.")
        answer = answer.strip()
        if not answer:
            raise ValueError(f"보기 {candidate_id}의 내용을 입력해 주세요.")
        if len(answer) > 300:
            raise ValueError(f"보기 {candidate_id}는 300자 이하로 입력해 주세요.")
        choices[candidate_id] = answer

    if len(choices) < 2:
        raise ValueError(_NO_CHOICES)
    question = "\n".join(question_lines).strip()
    if not question:
        raise ValueError("첫 번째 보기 위에 질문을 입력해 주세요.")
    if len(question) > 1600:
        raise ValueError("질문은 1,600자 이하로 입력해 주세요.")

    contract = {
        "question": question,
        "choices": choices,
        "instruction": COMMON_INSTRUCTION,
    }
    serialized = json.dumps(contract, ensure_ascii=False, separators=(",", ":"))
    return {**contract, "task_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest()}
