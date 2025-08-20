# Integration Test Planning

## Objective
Create a comprehensive integration test that validates the entire pyramid-temporal flow:
1. User creation via REST API
2. Temporal workflow triggering 
3. Activity execution with automatic transaction management
4. Database state verification

## Test Architecture

### Dependencies to Add
```bash
# Database and ORM
poetry add --group dev sqlalchemy alembic psycopg2-binary

# Pyramid transaction management
poetry add --group dev pyramid-tm

# Testing infrastructure  
poetry add --group dev testing-postgresql webtest pytest-asyncio

# Temporal testing
poetry add --group dev temporalio[testing]
```

### File Structure
```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures
├── app/
│   ├── __init__.py
│   ├── models.py            # SQLAlchemy User model
│   ├── views.py             # Pyramid views (create_user_view)
│   └── workflows.py         # Temporal workflows and activities
└── test_integration.py      # Main integration test

.dev-local/
└── docker-compose.yml       # Temporal + PostgreSQL services
```

## Implementation Plan

### 1. SQLAlchemy User Model
```python
# tests/app/models.py
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    enriched = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 2. Test Pyramid Application
```python
# tests/app/config.py
def create_test_app(db_session):
    config = Configurator()
    config.include('pyramid_tm')        # Web request transactions
    config.include('pyramid_temporal')  # Activity transactions
    
    # SQLAlchemy setup
    config.registry.dbmaker = sessionmaker(bind=engine)
    
    # Routes
    config.add_route('create_user', '/users')
    config.add_view(create_user_view, route_name='create_user', 
                   request_method='POST', renderer='json')
    
    return config.make_wsgi_app()

# tests/app/views.py
def create_user_view(request):
    # 1. Create user in database
    # 2. Trigger Temporal workflow for enrichment
    # 3. Return user data
```

### 3. Temporal Workflows and Activities
```python
# tests/app/workflows.py

@activity.defn
async def enrich_user_activity(user_id: int) -> bool:
    """Activity that enriches user - runs with pyramid_temporal transaction management"""
    # This will run inside an automatic transaction
    # Update user.enriched = True
    return True

@workflow.defn  
class UserEnrichmentWorkflow:
    @workflow.run
    async def run(self, user_id: int) -> bool:
        return await workflow.execute_activity(
            enrich_user_activity,
            user_id,
            schedule_to_close_timeout=60
        )
```

### 4. Pytest Fixtures
```python
# tests/conftest.py

@pytest.fixture
def postgresql_db():
    """PostgreSQL test database using testing-postgresql"""
    
@pytest.fixture  
def db_session(postgresql_db):
    """SQLAlchemy session with test database"""
    
@pytest.fixture
def pyramid_app(db_session):
    """Test Pyramid application with database"""
    
@pytest.fixture
def webtest_app(pyramid_app):
    """WebTest TestApp for making HTTP requests"""
    
@pytest.fixture
async def temporal_env():
    """Temporal test environment with worker"""
    # Try Temporal test framework first
    # Fallback to real temporal if needed
    
@pytest.fixture  
async def temporal_worker(temporal_env, db_session):
    """Temporal worker with pyramid_temporal interceptor"""
```

### 5. Integration Test
```python
# tests/test_integration.py

@pytest.mark.asyncio
async def test_user_creation_and_enrichment(webtest_app, temporal_worker, db_session):
    """Test complete flow: create user → trigger workflow → verify enrichment"""
    
    # 1. Create user via POST /users
    response = webtest_app.post_json('/users', {
        'name': 'John Doe',
        'email': 'john@example.com'
    })
    
    assert response.status_code == 201
    user_id = response.json['id']
    
    # 2. Verify user created but not enriched yet
    user = db_session.query(User).get(user_id)
    assert user.name == 'John Doe'
    assert user.enriched is False
    
    # 3. Wait for workflow completion (using Temporal test framework or polling)
    # This part will test that pyramid_temporal transaction management works
    
    # 4. Verify user was enriched
    db_session.refresh(user)
    assert user.enriched is True
```

### 6. Docker Compose for Development
```yaml
# .dev-local/docker-compose.yml
version: '3.8'
services:
  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"
      - "8233:8233"  # UI
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=postgresql
    depends_on:
      - postgresql
      
  postgresql:
    image: postgres:13
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: temporal
      POSTGRES_DB: temporal
    ports:
      - "5432:5432"
```

## Test Flow Validation

### What This Test Validates

1. **Pyramid Integration**: `config.include('pyramid_temporal')` works
2. **Transaction Management**: Activities get automatic transactions
3. **Database Operations**: SQLAlchemy operations are transactional
4. **Workflow Execution**: Temporal workflows trigger correctly
5. **End-to-End Flow**: HTTP → Database → Temporal → Database

### Success Criteria

- ✅ User created via REST API
- ✅ Temporal workflow triggered automatically  
- ✅ Activity executes with transaction management
- ✅ Database updated correctly (enriched=True)
- ✅ No manual transaction handling in activity code
- ✅ Test completes without errors

## Implementation Steps

1. **Add Dependencies** - Add all required packages
2. **Create Models** - SQLAlchemy User model
3. **Create Test App** - Pyramid app with all integrations
4. **Create Temporal Components** - Workflow and activity
5. **Create Fixtures** - Database, app, and Temporal setup
6. **Write Test** - Single integration test
7. **Create Docker Compose** - For manual testing/development
8. **Validate** - Ensure test passes and validates transaction management

## Potential Challenges

1. **Temporal Test Framework Complexity** - May need to fallback to polling
2. **Transaction Isolation** - Ensuring test database isolation
3. **Async Coordination** - Waiting for workflows to complete
4. **Dependency Integration** - Making sure pyramid_tm + pyramid_temporal work together

## Fallback Strategies

- If Temporal test framework is complex → Use database polling with timeout
- If PostgreSQL setup is problematic → Ensure testing-postgresql is properly configured
- If transaction conflicts → Use separate test database per test
