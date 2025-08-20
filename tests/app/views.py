"""Pyramid views for testing pyramid-temporal integration."""

import asyncio
import logging
import uuid
from typing import Dict, Any

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPCreated
from sqlalchemy.exc import IntegrityError
from temporalio.client import Client

from tests.app.models import User
from tests.app.workflows import UserEnrichmentWorkflow

logger = logging.getLogger(__name__)


@view_config(route_name='create_user', request_method='POST', renderer='json')
def create_user_view(request) -> Dict[str, Any]:
    """Create a new user and trigger enrichment workflow.
    
    This view demonstrates the integration between Pyramid web requests
    (managed by pyramid_tm) and Temporal workflows (managed by pyramid_temporal).
    
    Args:
        request: Pyramid request object
        
    Returns:
        dict: User data and workflow information
        
    Raises:
        HTTPBadRequest: If request data is invalid
    """
    logger.info("Creating new user")
    
    # Log session ID for tracking
    session = request.dbsession
    logger.info("VIEW: Using session ID: %s", id(session))
    
    # Get request data
    try:
        data = request.json_body
        name = data.get('name')
        email = data.get('email')
        
        if not name or not email:
            raise HTTPBadRequest("Name and email are required")
            
    except (ValueError, TypeError):
        raise HTTPBadRequest("Invalid JSON data")
    
    # Get database session from request
    session = request.dbsession
    
    try:
        # Create new user
        user = User(name=name, email=email)
        session.add(user)
        session.flush()  # Get the user ID
        
        user_id = user.id
        logger.info("Created user with ID: %s", user_id)
        
        # Get Temporal client from request (provided by pyramid_temporal)
        temporal_client = request.temporal_client
        
        # Start enrichment workflow
        workflow_id = f"enrich-user-{user_id}-{uuid.uuid4().hex[:8]}"
        
        # Create a new event loop for this operation
        async def start_workflow_async():
            return await temporal_client.start_workflow(
                UserEnrichmentWorkflow.run,
                user_id,
                id=workflow_id,
                task_queue="pyramid-temporal-test",
            )
        
        # Use asyncio.run to properly handle the async operation
        workflow_handle = asyncio.run(start_workflow_async())
        
        logger.info("Started enrichment workflow: %s", workflow_id)
        
        # Return success response
        request.response.status = 200
        return {
            'status': 'created',
            'user': user.to_dict(),
            'workflow_started': True,
            'workflow_id': workflow_id,
            'message': 'User created and enrichment workflow started'
        }
        
    except IntegrityError as e:
        logger.error("Database integrity error: %s", e)
        raise HTTPBadRequest("Email already exists")
        
    except Exception as e:
        logger.error("Error creating user: %s", e)
        raise HTTPBadRequest(f"Error creating user: {str(e)}")



