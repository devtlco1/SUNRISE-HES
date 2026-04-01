from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.session import engine


def test_backend_tests_use_a_dedicated_database() -> None:
    with engine.connect() as connection:
        current_database = connection.execute(text("SELECT current_database()")).scalar_one()

    expected_database = make_url(settings.database_url).database
    assert expected_database is not None
    assert current_database == expected_database
    assert current_database.endswith("_test")
