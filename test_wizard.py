"""End-to-end wizard test using Streamlit's AppTest (no browser needed).

Drives all four screens for an Experienced/Aggressive persona and a
Beginner persona, asserting no screen raises an exception.

    .venv/bin/python -m pytest test_wizard.py   (or run directly)
"""

from streamlit.testing.v1 import AppTest

ANSWERS_EXPERIENCED = {
    "q_products": "Also derivatives, leveraged products or crypto",
    "q_leverage_check": "20%",
    "q_experience": "More than 3 years",
    "q_horizon": "In more than 15 years",
    "q_panic": "Buy more while it's cheap",
    "q_capacity": "A small part — I have a solid cushion",
    "q_goal": "Maximizing long-term growth",
}
ANSWERS_BEGINNER = {
    "q_products": "Nothing yet — this would be my first investment",
    "q_leverage_check": "10%",
    "q_experience": "I haven't started / under 1 year",
    "q_horizon": "In 7–15 years",
    "q_panic": "Sell part of it to feel safer",
    "q_capacity": "Around half",
    "q_goal": "Growing steadily over time",
}


def click_button(at: AppTest, label_part: str) -> None:
    btn = next(b for b in at.button if label_part in (b.label or ""))
    btn.click()
    at.run(timeout=180)


def run_flow(answers: dict, expect_tier: str) -> None:
    at = AppTest.from_file("app.py")
    at.run(timeout=60)
    assert not at.exception, at.exception

    click_button(at, "Start my assessment")
    assert not at.exception

    for key, label in answers.items():
        at.radio(key=key).set_value(label)
    at.run(timeout=60)
    click_button(at, "See my profile")
    assert not at.exception
    prof = at.session_state["profile"]
    assert prof.tier == expect_tier, f"{prof.tier} != {expect_tier}"

    click_button(at, "Build my portfolio")
    assert not at.exception, f"step 3 raised: {at.exception}"

    click_button(at, "Where could this take me")
    assert not at.exception, f"step 4 raised: {at.exception}"
    print(f"OK {expect_tier}: tier={prof.tier} band={prof.band} "
          f"tol={prof.tolerance} horizon={prof.horizon_years}y")


if __name__ == "__main__":
    run_flow(ANSWERS_EXPERIENCED, "Experienced")
    run_flow(ANSWERS_BEGINNER, "Beginner")
    print("wizard end-to-end: PASS")
