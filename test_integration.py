"""
Quick integration test: verify DB connection + repositories work with real data.
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

async def test():
    from app.infrastructure.database.connection import init_pool, close_pool, test_db_connection
    from app.infrastructure.database.factory import get_product_repository, get_user_repository, get_order_repository

    print("=" * 60)
    print("🧪 Integration Test: DB + Repositories")
    print("=" * 60)

    # 1. Test DB connection
    print("\n[1] Testing DB connection...")
    ok = await test_db_connection()
    assert ok, "❌ DB connection failed!"
    print("   ✅ DB connection OK")

    # 2. Test ProductRepository
    print("\n[2] Testing ProductRepository...")
    repo = await get_product_repository()
    print(f"   Type: {type(repo).__name__}")

    count = await repo.count()
    print(f"   Total products: {count}")
    assert count == 21, f"Expected 21, got {count}"

    products = await repo.list_paginated(limit=5, offset=0)
    print(f"   Page 1 (5 items): {[p.name for p in products]}")
    assert len(products) == 5

    product = await repo.get_by_id(1)
    print(f"   Product #1: {product.name} | Rp {product.price:,} | Stock: {product.stock}")
    assert product is not None
    assert product.name == "CANVA PRO TEAM 1 TAHUN"

    # 3. Test UserRepository
    print("\n[3] Testing UserRepository...")
    user_repo = await get_user_repository()
    print(f"   Type: {type(user_repo).__name__}")

    # Create test user
    user = await user_repo.get_or_create(telegram_id=123456789)
    print(f"   Test user: telegram_id={user.telegram_id}, balance={user.balance}")
    assert user.telegram_id == 123456789

    # Add balance
    added = await user_repo.add_balance(123456789, 100000)
    print(f"   Add 100k balance: {added}")
    assert added

    # Check balance
    user = await user_repo.get_by_id(123456789)
    print(f"   Balance after add: Rp {user.balance:,}")
    assert user.balance >= 100000

    # Deduct balance
    deducted = await user_repo.deduct_balance(123456789, 50000)
    print(f"   Deduct 50k: {deducted}")
    assert deducted

    user = await user_repo.get_by_id(123456789)
    print(f"   Balance after deduct: Rp {user.balance:,}")

    # 4. Test OrderRepository
    print("\n[4] Testing OrderRepository...")
    order_repo = await get_order_repository()
    print(f"   Type: {type(order_repo).__name__}")

    order = await order_repo.create(
        user_id=123456789,
        product_id=1,
        quantity=2,
        total_price=30000,
        payment_method="saldo",
    )
    print(f"   Created order: id={order.id}, status={order.status}")
    assert order.id is not None

    # Update status
    updated = await order_repo.update_status(order.id, "paid")
    print(f"   Update status to 'paid': {updated}")
    assert updated

    # Get order
    fetched = await order_repo.get_by_id(order.id)
    print(f"   Fetched order: status={fetched.status}")
    assert fetched.status == "paid"

    # 5. Test OrderService
    print("\n[5] Testing OrderService...")
    from app.application.services.factory import get_order_service
    order_svc = await get_order_service()

    # Ensure test user has enough balance
    await user_repo.add_balance(123456789, 500000)

    result = await order_svc.execute_order(
        user_id=123456789,
        product_id=1,
        quantity=1,
        payment_method="saldo",
    )
    print(f"   Execute order result: success={result.success}")
    if result.success:
        print(f"   Order ID: {result.order.id}")
    else:
        print(f"   Error: {result.error_code} - {result.error_message}")
    assert result.success, f"Order failed: {result.error_message}"

    # Check balance was deducted
    user = await user_repo.get_by_id(123456789)
    print(f"   User balance after order: Rp {user.balance:,}")

    # Check stock was decremented
    product = await repo.get_by_id(1)
    print(f"   Product #1 stock after order: {product.stock}")

    print("\n" + "=" * 60)
    print("✅ ALL INTEGRATION TESTS PASSED!")
    print("=" * 60)

    await close_pool()


if __name__ == "__main__":
    asyncio.run(test())
