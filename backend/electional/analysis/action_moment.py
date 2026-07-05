"""Resolve the action that actually sets an electional moment."""

from __future__ import annotations

from dataclasses import replace

from ..objective_packs import load_objective_pack
from .helpers import objective_mode
from .tactical_models import ActionMoment


def resolve_action_moment_with_pack(objective: str | None) -> ActionMoment:
    action = resolve_action_moment(objective)
    try:
        pack = load_objective_pack(action.objective_type)
    except ValueError:
        return replace(action, warnings=(*action.warnings, "Objective pack invalid; using built-in action mapping."), confidence=min(action.confidence, 0.62))
    action_text = str(pack.get("fast_lane_action_text") or "")
    if not action_text:
        return action
    instructions = tuple([*action.instructions[:-1], action_text]) if action.instructions else (action_text,)
    return replace(action, instructions=instructions)


def resolve_action_moment(objective: str | None) -> ActionMoment:
    mode = objective_mode(str(objective or ""))
    lowered = str(objective or "").lower()
    if "email" in lowered or "message" in lowered or "contact" in lowered:
        return _message_action(mode)
    if "legal" in lowered or "notice" in lowered or "complaint" in lowered or "appeal" in lowered:
        return _legal_action()
    if "exam" in lowered or "cert" in lowered:
        return _exam_action()
    if "business" in lowered or "launch" in lowered or "publish" in lowered:
        return _business_action()
    if "purchase" in lowered or "investment" in lowered or "payment" in lowered or "money" in lowered:
        return _purchase_action()
    if "relationship" in lowered:
        return _relationship_action()
    if "travel" in lowered or "trip" in lowered or "flight" in lowered:
        return _travel_action()
    if "ritual" in lowered or "spiritual" in lowered:
        return _ritual_action()
    if "medical" in lowered or "health" in lowered:
        return _medical_action()
    return ActionMoment(
        objective_type=mode,
        elected_moment="the irreversible public, submitted, signed, or formally started action",
        preparation_allowed_before_window=True,
        must_happen_inside_window=("final submit/send/sign/start action",),
        may_happen_before_window=("drafting", "setup", "review", "preparation"),
        avoid_inside_window=("unclear or reversible gestures",),
        timestamp_source="the external timestamp when available; otherwise the actual start action",
        instructions=("Prepare everything before the window.", "Use the elected window for the irreversible action."),
        warnings=("Objective type is generic, so action-moment confidence is reduced.",),
        confidence=0.62,
    )


def _message_action(mode: str) -> ActionMoment:
    return ActionMoment(
        objective_type=mode,
        elected_moment="when the message is sent",
        preparation_allowed_before_window=True,
        must_happen_inside_window=("press send", "final platform submission if it timestamps the message"),
        may_happen_before_window=("drafting", "editing", "attaching files", "preparing recipient list"),
        avoid_inside_window=("rewriting under pressure", "scheduling send for an uncontrolled later time"),
        timestamp_source="message sent timestamp",
        instructions=("Draft and proof before the window.", "Press Send inside the elected window."),
        warnings=("Scheduled send counts when the platform actually sends, not when it is scheduled.",),
        confidence=0.9,
    )


def _legal_action() -> ActionMoment:
    return ActionMoment(
        objective_type="legal_dispute",
        elected_moment="when filing, notice, complaint, appeal, or email is submitted",
        preparation_allowed_before_window=True,
        must_happen_inside_window=("final submit", "final send", "timestamped filing action"),
        may_happen_before_window=("drafting", "printing", "organizing exhibits", "uploading attachments when final submit is separate"),
        avoid_inside_window=("submitting after cutoff", "relying on intention instead of the system timestamp"),
        timestamp_source="court portal, email, certified-mail acceptance, or filing confirmation timestamp",
        instructions=("Prepare the portal or packet before the window.", "Submit and save confirmation inside the window."),
        warnings=("If a system timestamp controls the filing, use that timestamp, not personal intention.",),
        confidence=0.88,
    )


def _exam_action() -> ActionMoment:
    return ActionMoment(
        objective_type="exam",
        elected_moment="when the test officially begins",
        preparation_allowed_before_window=True,
        must_happen_inside_window=("click Begin/Start", "actual exam start if a proctor controls it"),
        may_happen_before_window=("login", "identity verification", "desk check", "system check"),
        avoid_inside_window=("starting after cutoff", "leaving proctor delay unbuffered"),
        timestamp_source="exam platform or proctor start timestamp",
        instructions=("Complete login and ID checks before the window.", "Start the exam inside the elected window."),
        warnings=("If a proctor delays the start, timing control is reduced.",),
        confidence=0.86,
    )


def _business_action() -> ActionMoment:
    return ActionMoment(
        objective_type="business_launch",
        elected_moment="the public launch, first customer-facing availability, first transaction, or legal filing",
        preparation_allowed_before_window=True,
        must_happen_inside_window=("publish", "open sales", "file formation paperwork", "send launch announcement"),
        may_happen_before_window=("website design", "payment setup", "inventory", "internal testing"),
        avoid_inside_window=("changing the launch objective mid-window",),
        timestamp_source="public publish, transaction, announcement, or filing timestamp",
        instructions=("Define whether this election is for legal birth, public launch, or first sale.", "Execute that action inside the window."),
        warnings=("Do not mix legal formation, public launch, and first-sale timing unless they are intentionally the same election.",),
        confidence=0.82,
    )


def _purchase_action() -> ActionMoment:
    return ActionMoment(
        objective_type="money_business",
        elected_moment="when order, payment, transaction, or contract acceptance is submitted",
        preparation_allowed_before_window=True,
        must_happen_inside_window=("final payment click", "final signature", "transaction broadcast"),
        may_happen_before_window=("research", "cart setup", "wallet setup", "quote review"),
        avoid_inside_window=("market orders with uncontrolled execution time",),
        timestamp_source="merchant, broker, wallet, or contract timestamp",
        instructions=("Prepare the order before the window.", "Submit the irreversible payment or signature inside the window."),
        warnings=("Market execution timestamp may differ from click timestamp.",),
        confidence=0.82,
    )


def _relationship_action() -> ActionMoment:
    action = _message_action("relationship")
    return ActionMoment(
        objective_type="relationship",
        elected_moment="when the message is sent, call is initiated, or invitation is delivered",
        preparation_allowed_before_window=action.preparation_allowed_before_window,
        must_happen_inside_window=("send/call/invite action",),
        may_happen_before_window=action.may_happen_before_window,
        avoid_inside_window=("counting when they read it unless reception is the objective",),
        timestamp_source="sent/call/invitation timestamp",
        instructions=("Draft before the window.", "Send, call, or deliver the invitation inside the elected window."),
        warnings=("Do not count when they read it unless the objective is reception or response.",),
        confidence=0.86,
    )


def _travel_action() -> ActionMoment:
    return ActionMoment(
        objective_type="travel",
        elected_moment="booking payment, departure, or trip start depending on the selected travel objective",
        preparation_allowed_before_window=True,
        must_happen_inside_window=("booking payment", "leaving home", "boarding/departure action selected by the user"),
        may_happen_before_window=("packing", "planning", "checking maps"),
        avoid_inside_window=("using the wrong travel milestone as the elected moment",),
        timestamp_source="booking, departure, or trip-start timestamp",
        instructions=("Choose whether the election is for booking or beginning travel.", "Execute that milestone inside the window."),
        warnings=("Flight timing can depend on scheduled departure or boarding depending user setting.",),
        confidence=0.74,
    )


def _ritual_action() -> ActionMoment:
    return ActionMoment(
        objective_type="ritual_spiritual",
        elected_moment="the beginning of the ritual or first formal act",
        preparation_allowed_before_window=True,
        must_happen_inside_window=("first invocation", "first prayer", "first offering", "formal start"),
        may_happen_before_window=("setup", "cleaning", "preparation", "placing materials"),
        avoid_inside_window=("treating setup as the elected moment unless setup is the ritual"),
        timestamp_source="formal start time",
        instructions=("Prepare the space before the window.", "Begin the formal ritual action inside the window."),
        warnings=(),
        confidence=0.82,
    )


def _medical_action() -> ActionMoment:
    return ActionMoment(
        objective_type="medical_health",
        elected_moment="appointment, procedure, or medication-regimen start",
        preparation_allowed_before_window=True,
        must_happen_inside_window=("appointment start", "procedure start", "first dose if timing a regimen"),
        may_happen_before_window=("paperwork", "travel", "check-in"),
        avoid_inside_window=("treating this as medical advice"),
        timestamp_source="appointment, procedure, or regimen-start timestamp",
        instructions=("Use this only as calendar timing.", "Follow medical professionals for all health decisions."),
        warnings=("This is not medical advice.",),
        confidence=0.7,
    )
