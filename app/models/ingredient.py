from sqlalchemy import Column, BigInteger, Integer, String, Numeric, TypeDecorator
from sqlalchemy.dialects.postgresql import BIT
from app.core.database import Base


class _BitToInt(TypeDecorator):
    """PostgreSQL BIT 컬럼을 Python int로 자동 변환."""
    impl = BIT
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if type(value).__name__ == "BitString":
            # asyncpg BitString.as_string() → '10000...' 형태, '1'의 위치가 bit_id
            return value.as_string().index("1")
        return int(value)


class IngredientMaster(Base):
    __tablename__ = "ingredient_master"

    id = Column(BigInteger, primary_key=True)
    bit_id = Column(_BitToInt, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    default_shelf_days = Column(Integer, nullable=False)
    risk_factor = Column(Numeric, nullable=False)
