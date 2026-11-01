from app.database import engine
from sqlalchemy import text


try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

        print("DATABASE CONNECTION SUCCESSFUL")
        print("Result:", result.scalar())

except Exception as e:
    print("DATABASE CONNECTION FAILED")
    print("Error:", e)