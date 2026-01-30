"""Tests for the poll_query fixture."""

import logging

from tests.app.models import User

logger = logging.getLogger(__name__)


def test_poll_query_for_existing_record(dbsession, poll_query):
    """Test poll_query can find an existing record."""
    # Create a user
    user = User(name="Test User", email="test@example.com", enriched=False)
    dbsession.add(user)
    dbsession.flush()  # Get the ID
    user_id = user.id

    # Poll for user existence - should succeed immediately
    user_exists_query = dbsession.query(User).filter(User.id == user_id)
    success = poll_query(user_exists_query, timeout=1.0, description="user existence")

    assert success, "Should find existing user immediately"


def test_poll_query_timeout_for_nonexistent_condition(dbsession, poll_query):
    """Test poll_query times out when condition is never met."""
    # Create a user that's not enriched
    user = User(name="Test User", email="test@example.com", enriched=False)
    dbsession.add(user)
    dbsession.flush()
    user_id = user.id

    # Poll for enriched user - should timeout since we don't enrich it
    enriched_user_query = dbsession.query(User).filter(User.id == user_id, User.enriched == True)  # noqa: E712
    success = poll_query(enriched_user_query, timeout=1.0, description="enriched user")

    assert not success, "Should timeout waiting for enriched user"


def test_poll_query_waits_for_condition_to_become_true(dbsession, poll_query):
    """Test poll_query waits and succeeds when condition becomes true."""
    # Create a user that's not enriched
    user = User(name="Test User", email="test@example.com", enriched=False)
    dbsession.add(user)
    dbsession.flush()
    user_id = user.id

    # Set up the query for enriched user
    enriched_user_query = dbsession.query(User).filter(User.id == user_id, User.enriched == True)  # noqa: E712

    # Enrich the user (simulating what would happen in a real scenario)
    user.enriched = True
    dbsession.flush()

    # Poll should succeed
    success = poll_query(enriched_user_query, timeout=2.0, description="enriched user after update")

    assert success, "Should find enriched user after update"


def test_poll_query_with_complex_conditions(dbsession, poll_query):
    """Test poll_query works with complex query conditions."""
    # Create multiple users
    user1 = User(name="Alice", email="alice@example.com", enriched=False)
    user2 = User(name="Bob", email="bob@example.com", enriched=True)
    user3 = User(name="Charlie", email="charlie@example.com", enriched=False)

    dbsession.add_all([user1, user2, user3])
    dbsession.flush()

    # Query for users with specific name pattern and enriched status
    complex_query = dbsession.query(User).filter(User.name.like("B%"), User.enriched == True)  # noqa: E712

    success = poll_query(complex_query, timeout=1.0, description="user with name starting with B and enriched")

    assert success, "Should find Bob who matches the complex condition"


def test_poll_query_with_custom_timeout_and_interval(dbsession, poll_query):
    """Test poll_query respects custom timeout and interval parameters."""
    import time

    # Create a user
    user = User(name="Test User", email="test@example.com", enriched=False)
    dbsession.add(user)
    dbsession.flush()
    user_id = user.id

    # Query that will never succeed
    impossible_query = dbsession.query(User).filter(
        User.id == user_id, User.enriched == True, User.name == "NonExistent"  # noqa: E712
    )

    # Test with very short timeout
    start_time = time.time()
    success = poll_query(impossible_query, timeout=0.5, interval=0.1, description="impossible condition")
    elapsed_time = time.time() - start_time

    assert not success, "Should timeout for impossible condition"
    assert elapsed_time >= 0.5, "Should respect minimum timeout"
    assert elapsed_time < 1.0, "Should not take much longer than timeout"
