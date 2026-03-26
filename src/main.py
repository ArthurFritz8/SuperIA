import sys
from pathlib import Path

# Configuração de Paths da Arquitetura
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# Agora os imports devem ser após adicionar o ROOT_DIR ao sys.path.
from loguru import logger
from project.config import settings
from project.crypto_tools import create_burner_wallet, finance_burner_wallet
from project.smart_account_utils import create_session_key, auto_claim_airdrop
from project.simulator import simulate_transaction
from project.blacklist_manager import check_security_status

def setup_logger():
    """Configura o logger global de nível empresarial."""
    logger.remove()
    logger.add(
        sys.stdout, 
        colorize=True, 
        format="<level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )

def main():
    setup_logger()
    logger.info("Iniciando Kernel Backend SuperIA (Web3 Security AI)")
    
    # 1. Pipeline de Criação de Wallet Efêmera (Burner / EOA)
    logger.debug("--- [ETAPA 1: Gestão de Identidade] ---")
    burner_wallet = create_burner_wallet()
    finance_status = finance_burner_wallet(burner_wallet.address, 20)
    logger.info(f"Status Financiamento: {finance_status['message']}")
    
    # 2. Account Abstraction (ERC-4337) Session Keys
    logger.debug("--- [ETAPA 2: Acordo de Delegação ERC-4337] ---")
    session_key = create_session_key(48 * 60 * 60, auto_sign=True)
    logger.info(f"Pareamento WalletConnect URI estabelecido.")
    
    # 3. SuperIA - Security Check & Sandbox Simulator
    logger.debug("--- [ETAPA 3: Auditoria Ativa de Riscos - SuperIA AI] ---")
    safe_contract = "0x89205A3A3b2A69De6Dbf7f01ED13B2108B2c43e7"
    scam_contract = "0x99905A3A3b2A69De6Dbf7f01ED13B2108B2c4ScAm"

    # Testando contrato malicioso interceptado pela IA
    security_eval = check_security_status(
        url='https://fake-airdrop.verify.com', 
        contract_address=scam_contract,
        blacklist_path=str(ROOT_DIR / "blacklist.json")
    )
    
    if not security_eval["access_granted"]:
        logger.error("🛑 Transação Abortada: Acesso de auto-assinatura revogado temporariamente devido a risco iminente.")
    
    # 4. Transacionar com Segurança Garantida (Mock)
    logger.debug("--- [ETAPA 4: Transação via Client (Tenderly Simular) ] ---")
    transaction_data = {
        'from': burner_wallet.address,
        'to': safe_contract,
        'value': 1000000000000000000 # 1 ETH/Token default
    }
    
    # Valida usando pydantic simulator framework
    simulation_result = simulate_transaction(transaction_data)
    
    if simulation_result.get("status") in ["ok", "simulated_mock"]:
        # 5. Efetivar Delegação Bundler (ERC-4337)
        logger.debug("--- [ETAPA 5: Executar Assinatura Automática] ---")
        claim_result = auto_claim_airdrop(session_key, safe_contract)
        logger.success(f"Fluxo Completo! {claim_result['message']}")
    else:
        logger.critical("O Bundler rejeitou ou a Simulação Tenderly alertou revert!")


if __name__ == "__main__":
    main()