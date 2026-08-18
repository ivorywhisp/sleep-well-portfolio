"""End-to-end test of the two-screen flow using Streamlit's AppTest.

Drives the assessment for two personas and asserts the results page
renders without exceptions.

    .venv/bin/python test_wizard.py
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


def run_flow(answers: dict, expect_tier: str) -> None:
    at = AppTest.from_file("app.py")
    at.run(timeout=60)
    assert not at.exception, at.exception

    for key, label in answers.items():
        at.radio(key=key).set_value(label)
    at.run(timeout=60)
    btn = next(b for b in at.button if "See my portfolio" in (b.label or ""))
    btn.click()
    at.run(timeout=180)
    assert not at.exception, f"results page raised: {at.exception}"

    prof = at.session_state["profile"]
    assert prof.tier == expect_tier, f"{prof.tier} != {expect_tier}"
    print(f"OK {expect_tier}: band={prof.band} tol={prof.tolerance} "
          f"horizon={prof.horizon_years}y")


if __name__ == "__main__":
    run_flow(ANSWERS_EXPERIENCED, "Experienced")
    run_flow(ANSWERS_BEGINNER, "Beginner")
    print("two-screen flow: PASS")
