from __future__ import annotations

import secrets
from pydantic import BaseModel, Field, SecretStr
from loguru import logger


class BurnerWallet(BaseModel):
    """Representa uma burner wallet com segurança de tipagem baseada no Pydantic."""

    address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$", description="Endereço Publico EOA (Hex format)")
    private_key: SecretStr = Field(description="Chave privada sensível ofuscada por default")


def create_burner_wallet() -> BurnerWallet:
    """Cria uma burner wallet para simulação isolada na abstração corrente.
    
    Implementação futura: Usar eth_account.Account.create() para mainnet.
    """

    pseudo_addr = "0x" + secrets.token_hex(20)
    pk = secrets.token_hex(32)
    
    wallet = BurnerWallet(address=pseudo_addr, private_key=SecretStr(pk))
    logger.info(f"Burner Wallet gerada e ofuscada em RAM: {wallet.address}")
    return wallet


def finance_burner_wallet(burner_wallet_address: str, amount_usd: float) -> dict[str, str]:
    """Valida o financiamento externo (DEX/CEX) para a EOA provisoriamente."""
    logger.warning(f"Aguardando financiamento on-chain de {amount_usd} USD para {burner_wallet_address}")

    return {
        "status": "manual_required",
        "message": "Nós bloqueamos envio automatizado de fundos da main wallet por segurança local.",
        "to_address": burner_wallet_address,
        "amount_usd": str(amount_usd),
    }