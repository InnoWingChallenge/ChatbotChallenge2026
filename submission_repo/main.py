"""Chatbot Challenge 2026 entry point. DO NOT EDIT. The grading harness
runs this file exactly as it is.

    python main.py "question"
    python main.py "question one" "question two"

One question uses rag_answer. More than one uses rag_answer_batch. The
answer is printed to stdout, one line per question. Everything else this
file prints goes to stderr, where the grader does not look.
"""
import sys
import time

from bot.answer import rag_answer, rag_answer_batch

TIME_LIMIT = 30


def main() -> None:
    questions = sys.argv[1:]
    if not questions:
        print('usage: python main.py "question" ["question" ...]', file=sys.stderr)
        sys.exit(1)

    started = time.time()
    try:
        if len(questions) == 1:
            answers = [rag_answer(questions[0])]
        else:
            answers = list(rag_answer_batch(questions))
    except Exception as exc:                        # noqa: BLE001
        # One bad question must not zero a whole run.
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        answers = [""] * len(questions)

    if len(answers) != len(questions):
        print(
            f"[error] got {len(answers)} answers for {len(questions)} questions",
            file=sys.stderr,
        )
        answers = (answers + [""] * len(questions))[: len(questions)]

    per_question = (time.time() - started) / len(questions)
    if per_question > TIME_LIMIT:
        print(
            f"[warning] {per_question:.1f}s per question, over the {TIME_LIMIT}s limit",
            file=sys.stderr,
        )

    for answer in answers:
        print("" if answer is None else str(answer))


if __name__ == "__main__":
    main()
