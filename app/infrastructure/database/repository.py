"""
Implementasi repository untuk akses data
Support: SQLAlchemy / Supabase
"""
from typing import List, Optional
from ...domain.entities import User, Product, Order
from ...domain.interfaces import UserRepository, ProductRepository, OrderRepository


class SQLAlchemyUserRepository(UserRepository):
    """Implementasi User Repository menggunakan SQLAlchemy"""

    def __init__(self, session):
        self.session = session

    async def create(self, user: User) -> User:
        """Create new user"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def update(self, user: User) -> User:
        """Update user"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def delete(self, telegram_id: int) -> bool:
        """Delete user"""
        # TODO: Implementasi dengan SQLAlchemy
        pass


class SQLAlchemyProductRepository(ProductRepository):
    """Implementasi Product Repository menggunakan SQLAlchemy"""

    def __init__(self, session):
        self.session = session

    async def create(self, product: Product) -> Product:
        """Create new product"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def get_all(self) -> List[Product]:
        """Get all products"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def update(self, product: Product) -> Product:
        """Update product"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def delete(self, product_id: str) -> bool:
        """Delete product"""
        # TODO: Implementasi dengan SQLAlchemy
        pass


class SQLAlchemyOrderRepository(OrderRepository):
    """Implementasi Order Repository menggunakan SQLAlchemy"""

    def __init__(self, session):
        self.session = session

    async def create(self, order: Order) -> Order:
        """Create new order"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def get_by_id(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def get_by_user(self, user_id: int) -> List[Order]:
        """Get orders by user"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def update(self, order: Order) -> Order:
        """Update order"""
        # TODO: Implementasi dengan SQLAlchemy
        pass

    async def delete(self, order_id: str) -> bool:
        """Delete order"""
        # TODO: Implementasi dengan SQLAlchemy
        pass
