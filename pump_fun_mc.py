from dataclasses import dataclass
from typing import Optional, Tuple
from solders.pubkey import Pubkey  # type: ignore
from solana.rpc.api import Client
import requests
from construct import Flag, Int64ul, Padding, Struct, Bytes
from spl.token.instructions import get_associated_token_address

@dataclass
class BondingCurveData:
    mint: Pubkey
    bonding_curve: Pubkey
    associated_bonding_curve: Pubkey
    virtual_token_reserves: int
    virtual_sol_reserves: int
    token_total_supply: int
    complete: bool
    creator: Pubkey

class PumpFunMarketCap:
    PGM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
    DIA_URL = "https://api.diadata.org/v1/assetQuotation/Solana/0x0000000000000000000000000000000000000000"

    def __init__(self, rpc_url: str) -> None:
        self.client = Client(rpc_url)

        self._curve_layout = Struct(
            Padding(8),
            "virtualTokenReserves" / Int64ul,
            "virtualSolReserves"   / Int64ul,
            "realTokenReserves"    / Int64ul,
            "realSolReserves"      / Int64ul,
            "tokenTotalSupply"     / Int64ul,
            "complete"             / Flag,
            "creator"              / Bytes(32),
        )

    def _get_virtual_reserves(self, bonding_curve: Pubkey) -> Optional[Struct]:
        try:
            info = self.client.get_account_info(bonding_curve)
            data = info.value.data
            return self._curve_layout.parse(data)
        except Exception:
            return None

    def _derive_bonding_curve_accounts(self, mint: Pubkey) -> Tuple[Optional[Pubkey], Optional[Pubkey]]:
        try:
            bc, _ = Pubkey.find_program_address(
                [b"bonding-curve", bytes(mint)],
                self.PGM_ID
            )
            atoken = get_associated_token_address(bc, mint)
            return bc, atoken
        except Exception:
            return None, None

    def _get_bonding_curve_data(self, mint_str: str) -> Optional[BondingCurveData]:
        mint = Pubkey.from_string(mint_str)
        bc, atoken = self._derive_bonding_curve_accounts(mint)
        if not bc or not atoken:
            return None
        vr = self._get_virtual_reserves(bc)
        if vr is None:
            return None
        return BondingCurveData(
            mint=mint,
            bonding_curve=bc,
            associated_bonding_curve=atoken,
            virtual_token_reserves=int(vr.virtualTokenReserves),
            virtual_sol_reserves=int(vr.virtualSolReserves),
            token_total_supply=int(vr.tokenTotalSupply),
            complete=bool(vr.complete),
            creator=Pubkey.from_bytes(vr.creator),
        )

    def _get_sol_price_usd(self) -> float:
        resp = requests.get(self.DIA_URL)
        resp.raise_for_status()
        return float(resp.json()["Price"])

    def get_market_cap(self, mint_str: str, total_supply: int = 1_000_000_000, token_decimals: int = 6
                 ) -> Tuple[float, float, float]:

        bc_data = self._get_bonding_curve_data(mint_str)
        if bc_data is None:
            raise ValueError("Could not fetch bonding curve data for mint: " + mint_str)

        sol_usd = self._get_sol_price_usd()

        sol_reserve = bc_data.virtual_sol_reserves / 10 ** 9
        token_reserve = bc_data.virtual_token_reserves / 10 ** token_decimals

        token_price_sol = sol_reserve / token_reserve
        token_price_usd = token_price_sol * sol_usd
        market_cap_usd  = token_price_usd * total_supply

        return token_price_sol, token_price_usd, market_cap_usd

if __name__ == "__main__":
    rpc = "https://api.mainnet-beta.solana.com"
    mint = ""
    token_price_sol, token_price_usd, market_cap_usd = PumpFunMarketCap(rpc).get_market_cap(mint)
    print(f"Pump Fun price (SOL): {token_price_sol:.9f} SOL")
    print(f"Pump Fun price (USD): ${token_price_usd:.9f}")
    print(f"Market cap (USD):     ${market_cap_usd:,.2f}")
