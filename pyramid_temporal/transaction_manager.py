"""Transaction management utilities for pyramid-temporal."""

import logging
from typing import Optional

import transaction

logger = logging.getLogger(__name__)


def is_transaction_active(tm: Optional[object] = None) -> bool:
    """Check if there is an active transaction.

    Args:
        tm: Optional transaction manager. If None, uses transaction.manager

    Returns:
        bool: True if there is an active transaction, False otherwise
    """
    transaction_manager = tm or transaction.manager
    try:
        current = transaction_manager.get()
        return current is not None and current.status != "NoTransaction"
    except Exception:
        return False


def safe_commit(tm: Optional[object] = None) -> bool:
    """Safely commit a transaction, handling doomed transactions.

    Args:
        tm: Optional transaction manager. If None, uses transaction.manager

    Returns:
        bool: True if committed successfully, False if skipped (doomed)

    Raises:
        Exception: If commit fails for reasons other than doomed transaction
    """
    transaction_manager = tm or transaction.manager
    try:
        logger.debug("Committing transaction")
        transaction_manager.commit()
        logger.info("Transaction committed successfully")
        return True
    except Exception as e:
        error_msg = str(e)
        # Check if this is a doomed transaction error
        if "doomed" in error_msg.lower():
            logger.debug("Transaction is doomed, skipping commit (will be rolled back by test framework)")
            return False

        logger.error("Failed to commit transaction: %s", e)
        # Try to abort the transaction if commit fails
        try:
            transaction_manager.abort()
            logger.debug("Transaction aborted after failed commit")
        except Exception as abort_error:
            logger.error("Failed to abort transaction after commit failure: %s", abort_error)
        raise


def safe_abort(tm: Optional[object] = None) -> None:
    """Safely abort a transaction without raising exceptions.

    Args:
        tm: Optional transaction manager. If None, uses transaction.manager
    """
    transaction_manager = tm or transaction.manager
    try:
        logger.debug("Aborting transaction")
        transaction_manager.abort()
        logger.debug("Transaction aborted successfully")
    except Exception as e:
        # Log the error but don't re-raise as this is called in error handlers
        logger.error("Failed to abort transaction: %s", e)
