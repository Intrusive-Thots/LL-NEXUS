# LL-NEXUS Architecture

Product loop: League State -> Context -> Recommendation -> Why? -> Authorized Action -> Verification -> Session Result.

Core/state is authoritative. Core/champions owns catalog and preferences. Core/recommendations performs deterministic explainable scoring. Core/automation gates consequential actions. Services/lcu owns client integration. Developer/simulation uses the same state and action boundaries. UI only presents and commands through AppController.

Automation refuses stale, unknown, syncing, or error confidence. The global kill switch is checked immediately before consequential actions.
