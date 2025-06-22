from dataclasses import dataclass
from typing import Optional
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

@dataclass
class MarketCapData:
    token_price_sol: float
    token_price_usd: float
    market_cap_usd: float

class PumpFunMarketCap:
    PGM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
    DIA_URL = "https://api.diadata.org/v1/assetQuotation/Solana/0x0000000000000000000000000000000000000000"

    def __init__(self, rpc_url: str, mint_str: str) -> None:
        self.client = Client(rpc_url)
        self.mint = Pubkey.from_string(mint_str)

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

    def _derive_bonding_curve_accounts(self) -> tuple[Optional[Pubkey], Optional[Pubkey]]:
        try:
            bc, _ = Pubkey.find_program_address(
                [b"bonding-curve", bytes(self.mint)],
                self.PGM_ID
            )
            atoken = get_associated_token_address(bc, self.mint)
            return bc, atoken
        except Exception:
            return None, None

    def _get_bonding_curve_data(self) -> Optional[BondingCurveData]:
        bc, atoken = self._derive_bonding_curve_accounts()
        if not bc or not atoken:
            return None

        vr = self._get_virtual_reserves(bc)
        if vr is None:
            return None

        return BondingCurveData(
            mint=self.mint,
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

    def get_market_cap(
        self,
        total_supply: int = 1_000_000_000,
        token_decimals: int = 6
    ) -> MarketCapData:
        """
        Returns a MarketCapData object for the initialized mint.
        """
        bc_data = self._get_bonding_curve_data()
        if bc_data is None:
            raise ValueError(f"Could not fetch bonding curve data for mint: {self.mint}")

        sol_usd = self._get_sol_price_usd()

        sol_reserve = bc_data.virtual_sol_reserves / 10 ** 9
        token_reserve = bc_data.virtual_token_reserves / 10 ** token_decimals

        token_price_sol = sol_reserve / token_reserve
        token_price_usd = token_price_sol * sol_usd
        market_cap_usd  = token_price_usd * total_supply

        return MarketCapData(
            token_price_sol=token_price_sol,
            token_price_usd=token_price_usd,
            market_cap_usd=market_cap_usd,
        )

if __name__ == "__main__":
    rpc = "https://api.mainnet-beta.solana.com"
    mint = "" 
    pump_fun_mc = PumpFunMarketCap(rpc, mint)
    mc_data = pump_fun_mc.get_market_cap()

    print(f"Token price (SOL): {mc_data.token_price_sol:.9f} SOL")
    print(f"Token price (USD): ${mc_data.token_price_usd:.9f}")
    print(f"Market cap (USD):     ${mc_data.market_cap_usd:,.2f}")
