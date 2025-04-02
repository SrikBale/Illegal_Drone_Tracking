import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# PostgreSQL connection string
DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@" \
         f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

# Setup SQLAlchemy
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Drone table
class DroneLog(Base):
    __tablename__ = "drone_logs"

    id = Column(Integer, primary_key=True, index=True)
    callsign = Column(String, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    velocity = Column(Float)
    unauthorized = Column(Boolean)
    zone = Column(String)

# Create the table if it doesn't exist
Base.metadata.create_all(bind=engine)

# Reusable log function
def log_drone(drone: dict):
    db = SessionLocal()
    try:
        entry = DroneLog(**drone)
        db.add(entry)
        db.commit()
    except Exception as e:
        print(f"❌ DB insert error: {e}")
    finally:
        db.close()
