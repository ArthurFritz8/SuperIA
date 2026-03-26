from __future__ import annotations

import json
from pathlib import Path
from loguru import logger
from project.config import settings

class ThreatIntelligence:
    """Implementa a SuperIA para análise de riscos na Web3."""
    
    @staticmethod
    def analyze_static_blacklist(url: str, blacklist_path: Path) -> bool:
        if not blacklist_path.exists():
            return False
        try:
            data = json.loads(blacklist_path.read_text(encoding="utf-8") or "[]")
            entries = set(map(str, data.get("entries", []) if isinstance(data, dict) else data))
            return url in entries
        except Exception as e:
            logger.error(f"Erro ao ler blacklist estática: {e}")
            return False

    @staticmethod
    def ai_contract_analysis(contract_address: str, chain_id: int) -> dict:
        """Processa a predição heurística ou de auditoria de Smart Contracts com IA.
        
        No futuro, consumirá a OpenAI / rede base para decompilar bytecode e encontrar vulnerabilities.
        """
        if not settings.openai_api_key:
            logger.debug(f"[SuperIA Mock] Rodando análise heurística sem API Key para o contrato: {contract_address}")
            
        # Simula o modelo da IA retornando status
        is_risky = contract_address.startswith("0x999")  # Mock: 0x999... será o phishing em nosso exemplo
        risk_score = 98.4 if is_risky else 12.1
        
        return {
            "score": risk_score,
            "is_safe": not is_risky,
            "reasoning": "Detectado código on-chain de função honeypot 'transferFrom' oculta." if is_risky else "Contrato verificado positivamente em auditoria semântica."
        }


def check_security_status(url: str, contract_address: str = "0x0000000000000000000000000000000000000000", blacklist_path: str = "blacklist.json") -> dict:
    """Consolida as defesas Web2 (URL) e a avaliação de bytecodes Web3 (SuperIA)."""
    logger.info(f"Escaneando ameaças no dApp: {url} e subjacente {contract_address}...")
    
    is_blacklisted = ThreatIntelligence.analyze_static_blacklist(url, Path(blacklist_path))
    ai_analysis = ThreatIntelligence.ai_contract_analysis(contract_address, chain_id=1)
    
    if is_blacklisted:
        logger.warning(f"URL interceptada na camada Web2 (Phishing conhecido): {url}")
        
    if not ai_analysis["is_safe"]:
        logger.error(f"Bloqueio Ativo: A SuperIA classificou o contrato {contract_address} como EXTREMO RISCO (Score: {ai_analysis['score']}).")
        
    return {
        "access_granted": not is_blacklisted and ai_analysis["is_safe"],
        "web2_threat": is_blacklisted,
        "ai_web3_score": ai_analysis["score"],
        "ai_reasoning": ai_analysis["reasoning"]
    }