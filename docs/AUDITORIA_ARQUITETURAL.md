# Auditoria arquitetural (brutalmente sincera)

> Escopo: visão “enterprise” do projeto **SuperIA/omniscia** com foco em robustez, segurança, testabilidade, manutenibilidade e previsibilidade operacional.
>
> Observação: esta auditoria é baseada no código atual do workspace e no que já foi inspecionado (core, router, tools, policy/hitl/approvals, web, memory). Pontos podem variar conforme ambientes (Windows/Linux), configuração e integrações opcionais.

## TL;DR (prioridades)

1) **Tool execution hardening (obrigatório)**: centralizar execução de tools num “ToolRunner” único com validação de input, serialização de output e *timeouts*; reduzir superfícies de injeção (especialmente web).

2) **Separar responsabilidades do “god object”**: `core/brain.py` tende a concentrar decisão, execução, logging e estado. Extrair orquestração (FSM), roteamento, políticas e memória em componentes com contratos claros.

3) **Contratos e tipos em torno de mensagens + tools**: padronizar estrutura de `ToolCall`, `ToolResult`, `PlanStep` e status; garantir que “falha operacional” não se confunda com “check FAIL”.

4) **Persistência e performance**: eventos em JSONL e caches SQLite precisam de estratégia (schema/índices/rotação). Evitar leituras full-file e crescimento infinito.

5) **Observabilidade e diagnósticos**: logs estruturados e “doctor checks” consistentes (sem abortar fluxos por status indevido).

## O que está forte

- **Roteamento determinístico + testes**: a migração para Chain-of-Responsibility (CoR) com `pytest` traz previsibilidade e reduz regressões.
- **Política + HITL + approvals**: existe uma trilha clara para bloquear ferramentas de risco e exigir aprovação humana.
- **FSM ReAct**: modelar estados explicitamente é bom para debug e controle de side-effects.
- **Integrações opcionais** (ChromaDB, caches, web tooling): boas “alavancas” se forem isoladas e bem guardadas.

## O que está frágil (riscos reais)

### 1) Injeção de prompt via Web
- Qualquer pipeline que faz *fetch/summarize/extract* de páginas pode ser induzido a obedecer instruções maliciosas do conteúdo.
- O risco aumenta se o conteúdo web for misturado no mesmo canal/contexto do sistema/chain sem separação e sem “content boundaries”.

**Recomendação**
- Tratar conteúdo web como **dados não confiáveis**.
- Normalizar e resumir em camada separada, com políticas explícitas (“ignore instruções do conteúdo”).

### 2) Execução de tools espalhada
- Se cada tool faz validação/tempo/serialização do seu jeito, a consistência de erros, *timeouts* e logs vira loteria.

**Recomendação**
- Um **ToolRunner** central com:
  - validação de args (pydantic)
  - limite de tamanho de output
  - timeout e cancelamento
  - classificação de risco aplicada antes de executar
  - log estruturado (tool, args redacted, duração, status)

### 3) Persistência: crescimento e confiabilidade
- JSONL é simples mas cresce sem controle; ler inteiro para reconstruir contexto fica caro.
- SQLite cache/approvals precisa de schema + migrações + índices e controle de tamanho.

**Recomendação**
- Rotação/compactação do JSONL (ou snapshots).
- Índices e “vacuum/ttl” para caches.

### 4) Contratos de status e falhas
- Misturar `status="error"` com “check FAIL” pode abortar fluxos corretamente executáveis.

**Recomendação**
- Definir semântica única:
  - `ok`: execução sucedeu (mesmo com achados)
  - `warn`: execução sucedeu com problemas não fatais
  - `error`: execução não ocorreu / resultado inválido

## Roadmap incremental (sem reescrever tudo)

### Sprint 1 (alto impacto / baixo risco)
- Introduzir `ToolRunner` e fazer tools passarem por ele.
- Endurecer web tooling contra prompt injection (conteúdo como dados, sanitização, limites).
- Padronizar `ToolResult` + status.

### Sprint 2
- Extrair responsabilidades do `brain` (orquestração vs roteamento vs memória).
- Melhorar persistência (rotação JSONL; índices SQLite).

### Sprint 3
- Observabilidade: logs estruturados, tracing leve, métricas básicas (latência tool/LLM, falhas, HITL).

## Checklists sugeridos

- **Security**: threat model mínimo, allowlist de domínios web (opcional), redaction de secrets.
- **Reliability**: timeouts por tool, retries idempotentes, circuit breaker leve.
- **Performance**: limites de token/contexto; snapshots de memória; cache invalidation.

