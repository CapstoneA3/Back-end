from sqlalchemy import Column, BigInteger, Integer, String, Text, TypeDecorator, ForeignKey
from sqlalchemy.dialects.postgresql import BIT
from app.core.database import Base


class _BitMaskToInt(TypeDecorator):
    impl = BIT
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if type(value).__name__ == "BitString":
            # asyncpg BitString may include spaces; strip before parsing
            return int(value.as_string().replace(" ", ""), 2)
        return value


class Recipe(Base):
    __tablename__ = "recipe"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    cook_time_min = Column(Integer, nullable=True)
    servings = Column(Integer, nullable=True)
    recipe_bit = Column(_BitMaskToInt, nullable=True)


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredient"

    id = Column(BigInteger, primary_key=True)
    recipe_id = Column(BigInteger, ForeignKey("recipe.id"), nullable=False)
    ingredient_master_id = Column(BigInteger, ForeignKey("ingredient_master.id"), nullable=True)
    quantity = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    ingredient_name = Column(Text, nullable=True)


class RecipeStep(Base):
    __tablename__ = "recipe_step"

    id = Column(BigInteger, primary_key=True)
    recipe_id = Column(BigInteger, ForeignKey("recipe.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    tip = Column(Text, nullable=True)
