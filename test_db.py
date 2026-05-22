"""
Test script untuk verify semua repository (Product, User, Order).

Cara pakai:
    python test_db.py
"""
import asyncio
import logging

from app.infrastructure.database import (
    get_product_repository,
    get_user_repository,
    get_order_repository,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_db")


async def test_repositories():
    """Test semua repository."""
    try:
        # ===== TEST PRODUCT REPOSITORY =====
        logger.info("=" * 60)
        logger.info("Testing ProductRepository...")
        logger.info("=" * 60)
        prod_repo = await get_product_repository()
        logger.info("✅ ProductRepository initialized: %s", type(prod_repo).__name__)

        total_products = await prod_repo.count()
        logger.info("Total produk: %s", total_products)

        products = await prod_repo.list_paginated(limit=5, offset=0)
        logger.info("List produk (limit=5):")
        for prod in products:
            logger.info("  - [%s] %s | Rp %s | stock=%s", prod.id, prod.name, prod.price, prod.stock)

        if products:
            first = products[0]
            detail = await prod_repo.get_by_id(first.id)
            logger.info("Detail produk ID %s: %s", first.id, detail.name)

            # Test decrement
            logger.info("Test decrement_stock (ID=%s, qty=1)...", first.id)
            success = await prod_repo.decrement_stock(first.id, 1)
            logger.info("Decrement: %s", "✅ sukses" if success else "❌ gagal")

        # ===== TEST USER REPOSITORY =====
        logger.info("=" * 60)
        logger.info("Testing UserRepository...")
        logger.info("=" * 60)
        user_repo = await get_user_repository()
        logger.info("✅ UserRepository initialized: %s", type(user_repo).__name__)

        # Get or create user
        test_user_id = 123456789
        user = await user_repo.get_or_create(test_user_id)
        logger.info("User created/fetched: ID=%s, balance=%s", user.telegram_id, user.balance)

        # Add balance
        logger.info("Test add_balance (amount=100000)...")
        success = await user_repo.add_balance(test_user_id, 100000)
        logger.info("Add balance: %s", "✅ sukses" if success else "❌ gagal")

        # Check balance
        user_updated = await user_repo.get_by_id(test_user_id)
        logger.info("User balance after add: %s", user_updated.balance if user_updated else "N/A")

        # Deduct balance
        logger.info("Test deduct_balance (amount=50000)...")
        success = await user_repo.deduct_balance(test_user_id, 50000)
        logger.info("Deduct balance: %s", "✅ sukses" if success else "❌ gagal")

        user_updated = await user_repo.get_by_id(test_user_id)
        logger.info("User balance after deduct: %s", user_updated.balance if user_updated else "N/A")

        # ===== TEST ORDER REPOSITORY =====
        logger.info("=" * 60)
        logger.info("Testing OrderRepository...")
        logger.info("=" * 60)
        order_repo = await get_order_repository()
        logger.info("✅ OrderRepository initialized: %s", type(order_repo).__name__)

        # Create order
        if products:
            product = products[0]
            logger.info("Creating order (user=%s, product=%s, qty=2)...", test_user_id, product.id)
            order = await order_repo.create(
                user_id=test_user_id,
                product_id=product.id,
                quantity=2,
                total_price=product.price * 2,
                payment_method="saldo",
            )
            logger.info("Order created: ID=%s, status=%s, total=%s", order.id, order.status, order.total_price)

            # Get order
            order_fetched = await order_repo.get_by_id(order.id)
            logger.info("Order fetched: %s", order_fetched.id if order_fetched else "NOT FOUND")

            # Get user orders
            user_orders = await order_repo.get_by_user(test_user_id, limit=10)
            logger.info("User orders: %s", len(user_orders))

            # Update order status
            logger.info("Updating order status to 'paid'...")
            success = await order_repo.update_status(order.id, "paid")
            logger.info("Update status: %s", "✅ sukses" if success else "❌ gagal")

            order_updated = await order_repo.get_by_id(order.id)
            logger.info("Order status after update: %s", order_updated.status if order_updated else "N/A")

        logger.info("=" * 60)
        logger.info("✅ All tests completed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception("❌ Error: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(test_repositories())
