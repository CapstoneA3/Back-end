from sqlalchemy import Column, BigInteger, Integer, String, Numeric
from app.core.database import Base


class IngredientMaster(Base):
    __tablename__ = "ingredient_master"

    id = Column(BigInteger, primary_key=True)
    bit_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    default_shelf_days = Column(Integer, nullable=False)
    risk_factor = Column(Numeric, nullable=False)
