from sqlalchemy import Column, BigInteger, String, Numeric, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserInventory(Base):
    __tablename__ = "user_inventory"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(String, nullable=False)
    ingredient_master_id = Column(BigInteger, ForeignKey("ingredient_master.id"), nullable=False)
    quantity = Column(Numeric, nullable=False)
    unit = Column(String(50))
    expire_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ingredient = relationship("IngredientMaster", lazy="raise")
