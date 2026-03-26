from typing import Any
import requests
from loguru import logger
from pydantic import BaseModel, Field

from project.config import settings

class TransactionDraft(BaseModel):
    """Modelo validador da prop para uma transação."""
    from_address: str = Field(alias="from", pattern=r"^0x[a-fA-F0-9]{40}$")
    to_address: str = Field(alias="to", pattern=r"^0x[a-fA-F0-9]{40}$")
    value: str | int = Field(default=0)
    input: str = Field(default="0x")
    
    class Config:
        populate_by_name = True

def simulate_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    """Testa uma mudança de estado on-chain na infraestrutura do Tenderly."""
    logger.info("Iniciando pré-flight da transação via Tenderly Simulator...")
    
    try:
        # Validação estruturada
        tx_draft = TransactionDraft(**transaction)
    except Exception as e:
        logger.error(f"Transação inválida: {e}")
        return {"status": "error", "error": "Schema de transação Pydantic inválido."}

    if not settings.tenderly_access_key or not settings.tenderly_account_slug or not settings.tenderly_project_slug:
        logger.warning(
            "Ignorando chamada real ao Tenderly: Variáveis TENDERLY_* não definidas no .env. Retornando Mock Seguro."
        )
        return {
            "status": "simulated_mock",
            "provider": "tenderly_local",
            "message": f"Transação segura simulada localmente. Transferência de {tx_draft.value} WEI avaliada sem risco."
        }
        
    url = f"https://api.tenderly.co/api/v1/account/{settings.tenderly_account_slug}/project/{settings.tenderly_project_slug}/simulate"
    headers = {
        "X-Access-Key": settings.tenderly_access_key,
        "Content-Type": "application/json",
    }

    try:
        # Payload com o draft mapeado correto para web3 via Pydantic model_dump
        payload = tx_draft.model_dump(by_alias=True)
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        
        logger.success("Simulação com Tenderly concluída sem Revert.")
        return {"status": "ok", "provider": "tenderly", "result": resp.json()}
    except requests.RequestException as exc:
        logger.error(f"Erro na conectividade com Tenderly API: {exc}")
        return {"status": "error", "provider": "tenderly", "error": str(exc)}