"""An activity body annotated with a type that only a type checker can see.

``from __future__ import annotations`` leaves every annotation a string, so this
module imports cleanly and ``Decimal`` is only ever looked up by whoever asks for
the type hints. The body is left undecorated, so the test chooses when that
happens.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyramid_temporal import ActivityContext

if TYPE_CHECKING:
    from decimal import Decimal


def deferred_annotation_body(context: ActivityContext, amount: Decimal) -> bool:
    """Undecorated: ``Decimal`` resolves for a type checker and nowhere else."""
    return bool(amount)
