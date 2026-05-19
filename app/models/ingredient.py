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
            # as_string()은 4비트마다 공백 포함 → 공백 제거 필수
            # recipe_bit와 동일한 LSB-0 기준으로 변환: 426 - left_pos
            bit_str = value.as_string().replace(" ", "")
            left_pos = bit_str.index("1")
            return len(bit_str) - 1 - left_pos
        return int(value)


class IngredientMaster(Base):
    __tablename__ = "ingredient_master"

    id = Column(BigInteger, primary_key=True)
    bit_id = Column(_BitToInt, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    default_shelf_days = Column(Integer, nullable=False)
    risk_factor = Column(Numeric, nullable=False)
