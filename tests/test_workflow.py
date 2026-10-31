import pytest

from app.services.workflow import (
    Forbidden,
    InvalidTransition,
    Role,
    Status,
    check_transition,
)


def test_creator_cannot_approve():
    with pytest.raises(Forbidden):
        check_transition(Status.IN_REVIEW, Status.APPROVED, Role.CREATOR)


def test_reviewer_can_approve_in_review():
    check_transition(Status.IN_REVIEW, Status.APPROVED, Role.REVIEWER)


def test_unapproved_publish_is_invalid():
    with pytest.raises(InvalidTransition):
        check_transition(Status.IN_REVIEW, Status.PUBLISHED, Role.CREATOR)


def test_approved_can_publish():
    check_transition(Status.APPROVED, Status.PUBLISHED, Role.CREATOR)


def test_send_back_requires_comment():
    with pytest.raises(ValueError):
        check_transition(Status.IN_REVIEW, Status.CHANGES_REQUESTED, Role.REVIEWER, comment="  ")
    check_transition(
        Status.IN_REVIEW, Status.CHANGES_REQUESTED, Role.REVIEWER, comment="Fix the price"
    )


def test_fact_change_moves_published_to_revalidation_by_system_only():
    check_transition(Status.PUBLISHED, Status.NEEDS_REVALIDATION, Role.AI_CHECK)
    with pytest.raises(Forbidden):
        check_transition(Status.PUBLISHED, Status.NEEDS_REVALIDATION, Role.CREATOR)


def test_draft_cannot_skip_to_review():
    with pytest.raises(InvalidTransition):
        check_transition(Status.DRAFT, Status.IN_REVIEW, Role.CREATOR)
