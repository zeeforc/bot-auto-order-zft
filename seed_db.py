"""
Seed script: Insert sample products + test user ke Supabase DB.

Jalankan sekali setelah migrate schema:
    python seed_db.py

Script ini idempotent - bisa dijalankan ulang tanpa duplikasi
(pakai ON CONFLICT DO NOTHING untuk products, UPSERT untuk user).
"""
import asyncio
import asyncpg
from config.settings import DATABASE_URL


PRODUCTS = [
    # (name, description, category, price, stock)
    # ⚠️ ALL PRICES SET TO Rp 1.000 FOR TESTING (Tripay minimum = Rp 1.000)
    ("CANVA PRO TEAM 1 TAHUN", "Canva Pro Team Annual Subscription", "design", 1000, 277),
    ("CANVA PRO TEAM 6 BULAN", "Canva Pro Team 6 Months", "design", 1000, 200),
    ("CANVA PRO TEAM 3 BULAN", "Canva Pro Team 3 Months", "design", 1000, 150),
    ("CANVA PRO TEAM 1 BULAN", "Canva Pro Team 1 Month", "design", 1000, 300),
    ("NETFLIX PREMIUM 1 BULAN", "Netflix Premium 1 Month Shared", "streaming", 1000, 100),
    ("NETFLIX PREMIUM 2 BULAN", "Netflix Premium 2 Months Shared", "streaming", 1000, 80),
    ("SPOTIFY PREMIUM 1 BULAN", "Spotify Premium Individual 1 Month", "streaming", 1000, 200),
    ("SPOTIFY PREMIUM 3 BULAN", "Spotify Premium Individual 3 Months", "streaming", 1000, 150),
    ("YOUTUBE PREMIUM 1 BULAN", "YouTube Premium 1 Month", "streaming", 1000, 120),
    ("YOUTUBE PREMIUM 3 BULAN", "YouTube Premium 3 Months", "streaming", 1000, 90),
    ("ADOBE PHOTOSHOP CC 1 TAHUN", "Adobe Photoshop CC Annual License", "software", 1000, 50),
    ("ADOBE PREMIERE PRO 1 TAHUN", "Adobe Premiere Pro CC Annual", "software", 1000, 45),
    ("MICROSOFT OFFICE 365 1 TAHUN", "Microsoft 365 Personal Annual", "software", 1000, 300),
    ("CHATGPT PLUS 1 BULAN", "ChatGPT Plus Subscription 1 Month", "ai", 1000, 60),
    ("MIDJOURNEY BASIC 1 BULAN", "Midjourney Basic Plan 1 Month", "ai", 1000, 40),
    ("GRAMMARLY PREMIUM 1 TAHUN", "Grammarly Premium Annual", "software", 1000, 180),
    ("ZOOM PRO 1 BULAN", "Zoom Pro Meeting 1 Month", "software", 1000, 100),
    ("FIGMA PROFESSIONAL 1 BULAN", "Figma Professional Plan 1 Month", "design", 1000, 75),
    ("NOTION PLUS 1 TAHUN", "Notion Plus Annual Plan", "productivity", 1000, 200),
    ("CAPCUT PRO 1 TAHUN", "CapCut Pro Annual Subscription", "design", 1000, 250),
    ("ALIGHT MOTION PRO 1 TAHUN", "Alight Motion Pro Annual", "design", 1000, 350),
]


async def seed():
    print("🔌 Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # --- Seed Products ---
        print(f"\n📦 Inserting {len(PRODUCTS)} products...")
        inserted = 0
        for name, desc, category, price, stock in PRODUCTS:
            result = await conn.execute(
                """
                INSERT INTO products (name, description, category, price, stock, is_active)
                VALUES ($1, $2, $3, $4, $5, TRUE)
                ON CONFLICT DO NOTHING
                """,
                name, desc, category, price, stock,
            )
            if "INSERT" in result:
                inserted += 1

        print(f"   ✅ {inserted} products inserted (skipped existing)")

        # --- Verify products ---
        count = await conn.fetchval("SELECT COUNT(*) FROM products WHERE is_active = TRUE")
        print(f"   📊 Total active products in DB: {count}")

        # --- Show products ---
        rows = await conn.fetch(
            "SELECT id, name, price, stock FROM products WHERE is_active = TRUE ORDER BY id"
        )
        print("\n   📋 Product List:")
        for row in rows:
            print(f"   [{row['id']:>2}] {row['name']:<35} Rp {row['price']:>10,}  Stock: {row['stock']}")

        # --- Seed test user (your Telegram ID) ---
        # Ganti dengan Telegram ID lu kalau mau test saldo
        TEST_USER_ID = 0  # Will be auto-created saat /start
        print(f"\n👤 Test user will be auto-created when you /start the bot")

        print("\n✅ Seed complete! Database ready.")
        print("   Run: python main.py")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
