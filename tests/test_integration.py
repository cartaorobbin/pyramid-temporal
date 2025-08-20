"""Integration test for pyramid-temporal functionality."""

import asyncio
import logging
import time
from typing import Any, Dict

import pytest
from sqlalchemy.orm import Session

from tests.app.models import User

logger = logging.getLogger(__name__)


def test_user_creation_and_enrichment(
    webtest_app,
    temporal_worker,
    temporal_client,
    dbsession,
    poll_query
):
    """Test complete flow: create user → trigger workflow → verify enrichment.
    
    This test validates the entire pyramid-temporal integration:
    1. Create user via POST /users (Pyramid + pyramid_tm)
    2. Trigger Temporal workflow automatically
    3. Execute activity with pyramid_temporal transaction management
    4. Verify user was enriched in database
    
    Args:
        webtest_app: WebTest app with Temporal integration
        temporal_worker: Temporal worker with pyramid_temporal interceptor
        temporal_client: Temporal client for workflow operations
        dbsession: Database session for verification (transaction-managed)
    """
    logger.info("Starting integration test: user creation and enrichment")
    
    # Test data
    user_data = {
        'name': 'John Doe',
        'email': 'john.doe@example.com'
    }
    
    # 1. Create user via POST /users
    logger.info("Step 1: Creating user via POST /users")
    response = webtest_app.post_json('/users', user_data)
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json
    assert response_data['status'] == 'created'
    assert response_data['workflow_started'] is True
    assert 'user' in response_data
    assert 'workflow_id' in response_data
    
    user_id = response_data['user']['id']
    workflow_id = response_data['workflow_id']
    
    logger.info("User created with ID: %s, workflow ID: %s", user_id, workflow_id)
    
    # 2. Verify user created but not enriched yet
    logger.info("Step 2: Verifying user is created but not enriched")
    logger.info("TEST: Using session ID: %s", id(dbsession))
    user = dbsession.query(User).filter(User.id == user_id).first()
    assert user is not None
    assert user.name == user_data['name']
    assert user.email == user_data['email']
    assert user.enriched is False  # Should not be enriched yet
    
    # 3. Wait for workflow completion using poll_query
    logger.info("Step 3: Polling for user enrichment completion")
    
    # Create query to check for enriched user
    enriched_query = dbsession.query(User).filter(
        User.id == user_id, 
        User.enriched == True
    )
    
    # Poll until user is enriched or timeout
    success = poll_query(
        enriched_query, 
        timeout=15.0, 
        description=f"user {user_id} enrichment"
    )
    
    assert success, "User should be enriched within timeout"
    
    # 4. Verify final state
    logger.info("Step 4: Verifying final user state")
    
    user = dbsession.query(User).filter(User.id == user_id).first()
    
    assert user is not None, "User should exist after workflow completion"
    assert user.enriched is True, "User should be enriched after workflow completion"
    
    logger.info("✅ Integration test passed: User was successfully enriched!")
    logger.info("User found: enriched=%s", user.enriched)