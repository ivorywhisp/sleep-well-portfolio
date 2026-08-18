"""End-to-end test of the tap-through flow using Streamlit's AppTest.

Welcome → seven one-at-a-time questions → amount → results page, for
two personas, asserting no screen raises an exception.

    .venv/bin/python test_wizard.py
"""

from streamlit.testing.v1 import AppTest

ANSWERS_EXPERIENCED = [
    "Also derivatives, leveraged products or crypto",
    "20%",
    "More than 3 years",
    "In more than 15 years",
    "Buy more while it's cheap",
    "A small part — I have a solid cushion",
    "Maximizing long-term growth",
]
ANSWERS_BEGINNER = [
    "Nothing yet — this would be my first investment",
    "10%",
    "I haven't started / under 1 year",
    "In 7–15 years",
    "Sell part of it to feel safer",
    "Around half",
    "Growing steadily over time",
]


def click(at: AppTest, label_part: str, timeout: int = 60) -> None:
    btn = next(b for b in at.button if label_part in (b.label or ""))
    btn.click()
    at.run(timeout=timeout)


def run_flow(answers: list[str], expect_tier: str) -> None:
    at = AppTest.from_file("app.py")
    at.run(timeout=60)
    assert not at.exception, at.exception

    click(at, "Let's go")
    for label in answers:
        click(at, label)
        assert not at.exception, f"after '{label}': {at.exception}"

    click(at, "See my portfolio", timeout=180)
    assert not at.exception, f"results page raised: {at.exception}"

    prof = at.session_state["profile"]
    assert prof.tier == expect_tier, f"{prof.tier} != {expect_tier}"
    print(f"OK {expect_tier}: band={prof.band} tol={prof.tolerance} "
          f"horizon={prof.horizon_years}y")


if __name__ == "__main__":
    run_flow(ANSWERS_EXPERIENCED, "Experienced")
    run_flow(ANSWERS_BEGINNER, "Beginner")
    print("tap-through flow: PASS")
