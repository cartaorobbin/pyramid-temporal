"""Scope of a single activity execution.

One activity execution equals one Pyramid request and one transaction. Both
bound activity flavours, async and sync, go through the same context manager, so
the unit of work is identical whichever way the activity body is written.
"""

import logging
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from .context import ActivityContext
from .environment import PyramidEnvironment
from .transaction_manager import is_transaction_active, safe_abort, safe_commit

logger = logging.getLogger(__name__)


def _begin_transaction(request: Any) -> Optional[Any]:
    """Begin this execution's transaction and return its manager.

    Returns None when the application has no pyramid_tm configured, in which
    case the execution runs without transaction management.
    """
    tm = getattr(request, "tm", None)
    if tm is None:
        return None

    if not is_transaction_active(tm):
        tm.begin()

    return tm


@contextmanager
def activity_execution(env: PyramidEnvironment, *, threadlocal_request: bool) -> Iterator[ActivityContext]:
    """Give one activity execution its own request and its own transaction.

    The transaction commits when the body returns and aborts when it raises, and
    the request is closed either way. Nothing is shared with any other
    execution, so activities are safe to run concurrently.

    Args:
        env: PyramidEnvironment the request is built from
        threadlocal_request: Publish the request on Pyramid's threadlocal stack.
            See ``ActivityContext.create_request``.

    Yields:
        The ActivityContext for this execution
    """
    context = ActivityContext(env=env)
    request = context.create_request(threadlocal_request=threadlocal_request)
    tm = None

    try:
        tm = _begin_transaction(request)
        yield context
    except Exception as e:
        if tm is not None:
            logger.warning("Activity failed with exception: %s, aborting transaction", e)
            safe_abort(tm)
        raise
    else:
        if tm is not None:
            safe_commit(tm)
    finally:
        context.close_request()
