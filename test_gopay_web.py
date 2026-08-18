import asyncio
import os
import sys
from dotenv import load_dotenv
import aiohttp

# Load variables dari .env
load_dotenv()

async def test_api():
    api_url = os.getenv("GOBIZ_API_URL")
    cookie = os.getenv("GOBIZ_COOKIE")
    authorization = os.getenv("GOBIZ_AUTHORIZATION")
    
    if not api_url:
        print("❌ GOBIZ_API_URL belum di-setting di .env")
        return
        
    print(f"Mengambil data dari: {api_url[:50]}...")
    
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    
    if cookie:
        headers["Cookie"] = cookie
    if authorization:
        headers["Authorization"] = authorization
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                print(f"Status Code: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    transactions = data.get("transactions", [])
                    print(f"Berhasil! Ditemukan {len(transactions)} transaksi terbaru.")
                    
                    if transactions:
                        print("\nContoh Transaksi Terakhir:")
                        last_trx = transactions[0]
                        amount = last_trx.get("gross_amount", 0) // 100
                        print(f"- Waktu : {last_trx.get('transaction_time')}")
                        print(f"- Nominal : Rp {amount:,}")
                        print(f"- Status : {last_trx.get('transaction_status')}")
                else:
                    text = await response.text()
                    print(f"Gagal mengambil data. Response: {text[:200]}")
    except Exception as e:
        print(f"Error koneksi: {e}")

if __name__ == "__main__":
    # Menghindari error RuntimeError di Windows (ProactorEventLoop)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_api())
