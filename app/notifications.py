import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notifications")


def _should_fail() -> bool:
    return os.getenv("SIDE_EFFECT_SHOULD_FAIL", "false").lower() == "true"


def send_confirmation(submission_id: int, widget_id: int, data: dict) -> bool:
    """
    Fake confirmation email/webhook — logs to console.
    Returns True on 'success', False on 'failure'.
    Never raises: caller must not let this break the main path.
    """
    try:
        if _should_fail():
            raise RuntimeError("Simulated side-effect failure (SIDE_EFFECT_SHOULD_FAIL=true)")

        logger.info(
            f"[CONFIRMATION SENT] submission_id={submission_id} widget_id={widget_id} "
            f"to={data.get('email', 'unknown')}"
        )
        return True
    except Exception as e:
        logger.warning(f"[CONFIRMATION FAILED] submission_id={submission_id} error={e}")
        return False