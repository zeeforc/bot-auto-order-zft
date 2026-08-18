from aiogram.fsm.state import StatesGroup, State


class OrderStates(StatesGroup):
    waiting_for_qty_or_checkout = State()
    waiting_for_note_choice = State()
    waiting_for_note_text = State()
    waiting_for_confirmation = State()


class DepositStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_confirmation = State()


class AddProductStates(StatesGroup):
    """FSM untuk add product step-by-step."""
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_category = State()
    waiting_for_price = State()
    waiting_for_stock = State()
    waiting_for_confirmation = State()


class EditProductStates(StatesGroup):
    """FSM untuk edit product step-by-step."""
    waiting_for_id = State()
    waiting_for_field = State()
    waiting_for_value = State()


class DelProductStates(StatesGroup):
    """FSM untuk delete product."""
    waiting_for_id = State()
    waiting_for_confirmation = State()


class BulkAddStates(StatesGroup):
    """FSM untuk bulk add product (paste multi-line)."""
    waiting_for_data = State()
    waiting_for_confirmation = State()


class AddVariantStates(StatesGroup):
    """FSM untuk add variant ke produk induk (interactive)."""
    waiting_for_name = State()
    waiting_for_code = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_confirmation = State()


class AddStockStates(StatesGroup):
    """FSM untuk add account stock ke variant (interactive)."""
    waiting_for_variant_select = State()
    waiting_for_accounts = State()


class EditVariantStates(StatesGroup):
    """FSM untuk edit variant (interactive)."""
    waiting_for_variant_select = State()
    waiting_for_field = State()
    waiting_for_value = State()


class DelVariantStates(StatesGroup):
    """FSM untuk delete variant (interactive)."""
    waiting_for_variant_select = State()
    waiting_for_confirmation = State()


class RefundRejectStates(StatesGroup):
    """FSM untuk admin reject refund (input alasan)."""
    waiting_for_reason = State()


class DelAllStockStates(StatesGroup):
    """FSM untuk /delallstock - hapus semua stok di variant tertentu."""
    waiting_for_product_select = State()
    waiting_for_variant_select = State()
    waiting_for_confirmation = State()
