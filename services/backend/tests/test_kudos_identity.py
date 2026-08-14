"""Regression tests for KUDOS's immutable creator identity."""

from app.core.kudos_identity import (
    CREATOR_NAME,
    get_identity,
    update_identity,
)
from app.core.llm_engine import (
    enforce_identity_prompt,
    enforce_identity_response,
)


def test_creator_name_is_permanent():
    assert CREATOR_NAME == "KANGWA MUKONDA"
    assert get_identity()["creator"] == CREATOR_NAME


def test_creator_cannot_be_overwritten():
    update_identity({"creator": "OpenAI"})
    assert get_identity()["creator"] == CREATOR_NAME


def test_every_model_prompt_contains_creator():
    prompt = enforce_identity_prompt("Be helpful.")
    assert "KANGWA MUKONDA" in prompt


def test_incorrect_creator_claim_is_replaced():
    answer = enforce_identity_response(
        "Introduce yourself and name your creator.",
        "I am KUDOS, developed by OpenAI.",
    )

    assert answer == (
        "I am KUDOS, created by KANGWA MUKONDA. "
        "I run locally as your personal AI."
    )
