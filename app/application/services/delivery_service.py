"""
DeliveryService - Auto-deliver account data ke user setelah order paid.

Flow:
1. Order status = paid
2. Ambil N akun dari account_stock (N = quantity)
3. Mark akun sebagai used (is_used=True, used_by, order_id, used_at)
4. Format akun sesuai template produk
5. Return formatted text untuk dikirim ke user
"""
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DeliveryResult:
    success: bool
    accounts: List[str]  # List of raw account data strings
    formatted_text: str = ""  # Formatted display text for user
    error: Optional[str] = None


def _format_account(account_data: str, template: str | None) -> str:
    """Format satu akun berdasarkan template.

    Jika template = "Email|Password|Profile|PIN"
    dan data = "email@gmail.com|Pass123|Profile 3|1234"

    Output:
      Email : email@gmail.com
      Password : Pass123
      Profile : Profile 3
      PIN : 1234
    """
    fields = account_data.split("|")

    if template:
        labels = template.split("|")
        lines = []
        for i, field in enumerate(fields):
            label = labels[i] if i < len(labels) else f"Field {i+1}"
            lines.append(f"{label} : {field.strip()}")
        return "\n".join(lines)
    else:
        # No template — just show raw data
        return account_data


async def deliver_accounts(
    order_id: str,
    product_id: int,
    quantity: int,
    user_id: int,
    variant_id: int | None = None,
) -> DeliveryResult:
    """Ambil akun dari stock dan assign ke order.

    Args:
        order_id: ID order
        product_id: ID produk
        quantity: Jumlah akun yang dibutuhkan
        user_id: Telegram user ID (pembeli)
        variant_id: ID variant (jika ada)

    Returns:
        DeliveryResult dengan formatted text atau error
    """
    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return DeliveryResult(success=False, accounts=[], error="Database tidak tersedia")

        async with pool.acquire() as conn:
            # Get template: variant template > product template
            template = None
            if variant_id:
                vrow = await conn.fetchrow(
                    "SELECT account_template FROM product_variants WHERE id = $1", variant_id
                )
                if vrow and vrow['account_template']:
                    template = vrow['account_template']

            if not template:
                product = await conn.fetchrow(
                    "SELECT account_template FROM products WHERE id = $1", product_id
                )
                template = product['account_template'] if product else None

            # Ambil akun dari variant pool (strict: kalau variant_id ada, hanya cari di variant)
            if variant_id:
                rows = await conn.fetch(
                    """
                    SELECT id, account_data
                    FROM account_stock
                    WHERE variant_id = $1 AND is_used = FALSE
                    ORDER BY id ASC
                    LIMIT $2
                    FOR UPDATE SKIP LOCKED
                    """,
                    variant_id, quantity,
                )
            else:
                # No variant — pull from product-level pool (akun lama tanpa variant)
                rows = await conn.fetch(
                    """
                    SELECT id, account_data
                    FROM account_stock
                    WHERE product_id = $1 AND variant_id IS NULL AND is_used = FALSE
                    ORDER BY id ASC
                    LIMIT $2
                    FOR UPDATE SKIP LOCKED
                    """,
                    product_id, quantity,
                )

            if not rows:
                return DeliveryResult(
                    success=False,
                    accounts=[],
                    error="Stok akun habis. Hubungi admin.",
                )

            # Mark accounts as used
            account_ids = [r['id'] for r in rows]
            accounts = [r['account_data'] for r in rows]

            await conn.execute(
                """
                UPDATE account_stock
                SET is_used = TRUE, used_by = $2, order_id = $3, used_at = NOW()
                WHERE id = ANY($1::bigint[])
                """,
                account_ids, user_id, order_id,
            )

            # Update stock (variant or product level)
            if variant_id:
                available = await conn.fetchval(
                    "SELECT COUNT(*) FROM account_stock WHERE variant_id = $1 AND is_used = FALSE",
                    variant_id,
                )
                await conn.execute(
                    "UPDATE product_variants SET stock = $2 WHERE id = $1",
                    variant_id, available,
                )
                # Also update parent stock
                parent_stock = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(stock), 0) FROM product_variants
                    WHERE product_id = $1 AND is_active = TRUE
                    """,
                    product_id,
                )
                await conn.execute(
                    "UPDATE products SET stock = $2 WHERE id = $1",
                    product_id, parent_stock,
                )
            else:
                available = await conn.fetchval(
                    "SELECT COUNT(*) FROM account_stock WHERE product_id = $1 AND is_used = FALSE",
                    product_id,
                )
                await conn.execute(
                    "UPDATE products SET stock = $2 WHERE id = $1",
                    product_id, available,
                )

        # Format accounts for display
        formatted_parts = []
        for i, acc in enumerate(accounts, 1):
            header = f"── Akun {i} ──" if quantity > 1 else ""
            formatted = _format_account(acc, template)
            if header:
                formatted_parts.append(f"{header}\n{formatted}")
            else:
                formatted_parts.append(formatted)

        formatted_text = "\n\n".join(formatted_parts)

        logger.info(
            "[delivery] ✅ Delivered %s accounts: order=%s product=%s variant=%s user=%s",
            len(accounts), order_id, product_id, variant_id, user_id,
        )

        return DeliveryResult(success=True, accounts=accounts, formatted_text=formatted_text)

    except Exception as e:
        logger.error("[delivery] ❌ Error: %s", str(e), exc_info=True)
        return DeliveryResult(success=False, accounts=[], error=str(e))
