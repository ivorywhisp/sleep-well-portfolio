"""Investor profiling: the onboarding questionnaire and its scoring.

The design mirrors what MiFID II requires of every EU broker/advisor:

* An APPROPRIATENESS assessment (knowledge & experience) decides which
  product tier the app may recommend at all — Rookie, Starter or MVP.
  Risk appetite never unlocks products; only demonstrated knowledge does.
* A SUITABILITY assessment (horizon, loss tolerance, capacity, goal)
  decides how much risk the recommendation should target, expressed as a
  maximum historical drawdown band.

One deliberate hard rule: a horizon under 3 years caps the risk band at
Cautious regardless of stated appetite — money needed soon cannot ride
out a bear market, however brave its owner feels today.
"""

from dataclasses import dataclass

# Each option is (label shown to the user, points). Dimension "knowledge"
# feeds the tier score; "risk" feeds the suitability score.
QUESTIONS = {
    "products": {
        "dimension": "knowledge",
        "text": "Which of these have you invested in before?",
        "options": [
            ("Nothing yet — this would be my first investment", 0),
            ("Investment funds or ETFs", 1),
            ("Funds/ETFs and individual stocks", 2),
            ("Also derivatives, leveraged products or crypto", 3),
        ],
    },
    "leverage_check": {
        "dimension": "knowledge",
        "text": ("Concept check: a 2x leveraged fund tracks an index that "
                 "falls 10% in one day. Your position falls about…"),
        "options": [
            ("5%", 0),
            ("10%", 0),
            ("20%", 2),
            ("Nothing — leverage only affects gains", 0),
        ],
    },
    "experience": {
        "dimension": "knowledge",
        "text": "How long have you been investing?",
        "options": [
            ("I haven't started / under 1 year", 0),
            ("1–3 years", 1),
            ("More than 3 years", 1),
        ],
    },
    "horizon": {
        "dimension": "risk",
        "text": "When will you need this money?",
        "options": [
            ("Within 3 years", 0),
            ("In 3–7 years", 1),
            ("In 7–15 years", 2),
            ("In more than 15 years", 3),
        ],
    },
    "panic": {
        "dimension": "risk",
        "text": ("Your €50,000 becomes €40,000 in one month. "
                 "What do you actually do?"),
        "options": [
            ("Sell everything — I can't watch it fall further", 0),
            ("Sell part of it to feel safer", 1),
            ("Hold and wait it out", 2),
            ("Buy more while it's cheap", 3),
        ],
    },
    "capacity": {
        "dimension": "risk",
        "text": "How much of your total savings is this investment?",
        "options": [
            ("Most of what I have", 0),
            ("Around half", 1),
            ("A small part — I have a solid cushion", 2),
        ],
    },
    "goal": {
        "dimension": "risk",
        "text": "What is this money for?",
        "options": [
            ("Preserving what I have", 0),
            ("Growing steadily over time", 1),
            ("Maximizing long-term growth", 1),
        ],
    },
}

# knowledge score -> product tier (max score 6). Reaching MVP requires
# BOTH hands-on experience with complex products AND passing the leverage
# concept check — neither alone is enough.
TIER_BANDS = [(0, 2, "Rookie"), (3, 4, "Starter"), (5, 6, "MVP")]

# risk score -> (band name, max tolerable drawdown as positive fraction)
RISK_BANDS = [
    (0, 2, "Cautious", 0.10),
    (3, 5, "Balanced", 0.15),
    (6, 7, "Growth", 0.25),
    (8, 9, "Aggressive", 0.35),
]

# horizon answer index -> years used by the projection screen (midpoints)
HORIZON_YEARS = [2, 5, 10, 20]


@dataclass
class Profile:
    tier: str
    band: str
    tolerance: float        # positive fraction, e.g. 0.15
    horizon_years: int
    knowledge_score: int
    risk_score: int
    capped: bool            # True when the <3y horizon rule forced Cautious


def score_answers(answers: dict[str, int]) -> Profile:
    """Turn {question_key: chosen option index} into a Profile."""
    knowledge = sum(QUESTIONS[k]["options"][answers[k]][1]
                    for k in QUESTIONS
                    if QUESTIONS[k]["dimension"] == "knowledge")
    risk = sum(QUESTIONS[k]["options"][answers[k]][1]
               for k in QUESTIONS if QUESTIONS[k]["dimension"] == "risk")

    tier = next(name for lo, hi, name in TIER_BANDS if lo <= knowledge <= hi)
    band, tolerance = next((name, tol) for lo, hi, name, tol in RISK_BANDS
                           if lo <= risk <= hi)

    capped = False
    if answers["horizon"] == 0 and band != "Cautious":
        band, tolerance, capped = "Cautious", 0.10, True

    return Profile(tier=tier, band=band, tolerance=tolerance,
                   horizon_years=HORIZON_YEARS[answers["horizon"]],
                   knowledge_score=knowledge, risk_score=risk, capped=capped)
