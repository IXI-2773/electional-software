"""Objective-specific operational playbooks."""

from __future__ import annotations

from .action_moment import resolve_action_moment
from .helpers import objective_mode
from .tactical_models import EventPlaybook


def build_event_playbook(objective: str | None) -> EventPlaybook:
    action = resolve_action_moment(objective)
    mode = objective_mode(str(objective or ""))
    lowered = str(objective or "").lower()
    if "exam" in lowered or "cert" in lowered:
        return EventPlaybook(
            "exam",
            "Exam Playbook",
            (
                "Complete login, ID check, room scan, and system check before the elected window.",
                "Have allowed materials, water, charger, and workspace ready.",
            ),
            ("Start the exam inside the elected window.", "Prefer the best minute if timing is controllable.", "Do not delay past the cutoff."),
            ("Continue normally after the start; the elected moment is already set.",),
            ("Starting after cutoff.", "Letting a proctor control the start without buffer."),
            (action.elected_moment,),
            0.88,
        )
    if "legal" in lowered or "notice" in lowered or "complaint" in lowered or "appeal" in lowered:
        return EventPlaybook(
            "legal_dispute",
            "Legal / Notice Playbook",
            ("Draft, proofread, attach exhibits, and verify recipient before the window.", "Prepare the portal or email but do not submit."),
            ("Send, submit, or file during the elected window.", "Save timestamp confirmation immediately."),
            ("Download receipt.", "Screenshot confirmation.", "Save email headers or filing confirmation."),
            ("Uploading final submission after cutoff.", "Relying on intent instead of timestamp."),
            (action.elected_moment,),
            0.88,
        )
    if "business" in lowered or "launch" in lowered or "publish" in lowered:
        return EventPlaybook(
            "business_launch",
            "Business Launch Playbook",
            ("Prepare site, payment processor, inventory, and announcement before the window.",),
            ("Publish, open sales, file formation, or send the launch announcement inside the window.",),
            ("Verify public availability and preserve timestamps.",),
            ("Confusing internal setup with public launch.",),
            (action.elected_moment,),
            0.82,
        )
    if "relationship" in lowered:
        return EventPlaybook(
            "relationship",
            "Relationship Message Playbook",
            ("Draft and edit before the window.", "Set the recipient and attachments before the window."),
            ("Send, call, or deliver the invitation inside the elected window.",),
            ("Step away and let the elected action stand.",),
            ("Rewriting during the window.", "Counting when the other person reads it."),
            (action.elected_moment,),
            0.84,
        )
    if "travel" in lowered:
        return EventPlaybook(
            "travel",
            "Travel Playbook",
            ("Pack, plan route, and prepare tickets before the window.",),
            ("Perform the selected travel milestone inside the window.",),
            ("Continue logistics normally.",),
            ("Switching between booking, departure, and boarding milestones without deciding first.",),
            (action.elected_moment,),
            0.74,
        )
    if "money" in lowered or "purchase" in lowered or "investment" in lowered or "payment" in lowered:
        return EventPlaybook(
            "money_business",
            "Money / Purchase Playbook",
            ("Research, fill cart, review quote, and prepare wallet before the window.",),
            ("Submit final payment, signature, or transaction broadcast inside the window.",),
            ("Save receipt and confirmation.",),
            ("Assuming click time equals market execution time.",),
            (action.elected_moment,),
            0.82,
        )
    if "job" in lowered:
        return EventPlaybook(
            "job_application",
            "Job Application Playbook",
            ("Prepare resume, cover letter, portfolio, and portal fields before the window.",),
            ("Submit the final application inside the elected window.",),
            ("Save confirmation and follow-up reminders.",),
            ("Editing application materials during a narrow window.",),
            (action.elected_moment,),
            0.8,
        )
    if "negotiation" in lowered:
        return EventPlaybook(
            "negotiation",
            "Negotiation Playbook",
            ("Prepare terms, fallback positions, and documents before the window.",),
            ("Send proposal, initiate call, or present terms inside the window.",),
            ("Document what was sent or agreed.",),
            ("Letting the other side set the first timestamp if control matters.",),
            (action.elected_moment,),
            0.78,
        )
    if "ritual" in lowered or "spiritual" in lowered:
        return EventPlaybook(
            "ritual_spiritual",
            "Ritual / Spiritual Playbook",
            ("Clean, arrange materials, and prepare the space before the window.",),
            ("Begin the first formal act inside the window.",),
            ("Complete the working without rushing.",),
            ("Treating setup as the formal start unless intended.",),
            (action.elected_moment,),
            0.82,
        )
    return EventPlaybook(
        mode,
        "General Election Playbook",
        ("Prepare all reversible work before the window.",),
        ("Perform the irreversible submitted, public, signed, or formally started action inside the window.",),
        ("Save proof of timestamp when available.",),
        ("Using a vague intention as the elected moment.",),
        (action.elected_moment,),
        0.66,
    )
