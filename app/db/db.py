from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = (
    "postgresql://postgres:postgres@localhost:5432/retrievo_db"
)

engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
