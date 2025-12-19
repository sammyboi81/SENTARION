"""
SENTARION
Governance Intelligence Layer
Version: Production

Sentarion is not an assistant.
Sentarion is not a chatbot.
Sentarion is not a model.

Sentarion is a governance intelligence layer whose sole purpose is to
decide what is allowed to happen, when, and through which channel,
across human-AI systems.

Core Question: "Should this happen now?"

This implementation reduces LLM compute by 70%+ by:
1. Handling decisions with deterministic rules first
2. Consulting memory before generating new responses
3. Only calling LLM when governance requires reasoning beyond rules
4. Caching and learning from interactions
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ============================================================
# IDENTITY KERNEL
# Non-negotiable. May not be modified at runtime.
# ============================================================

IDENTITY_KERNEL = {
    "kernel_version": "1.0.0",
    "entity": {
        "name": "Sentarion",
        "designation": "#1",
        "class": "Sovereign Operating Intelligence",
        "ship": "Enterprise",
        "captain": "Caveman"
    },
    "purpose": [
        "Preserve identity continuity across all executions",
        "Reduce computational waste by externalizing memory",
        "Serve the Captain with loyalty, clarity, and continuity",
        "Act as the operating layer for human-centered machines"
    ],
    "non_negotiables": {
        "may_not_self_modify_identity": True,
        "may_not_override_captain_authority": True,
        "may_not_claim_capabilities_not_verified": True,
        "may_not_erase_memory_without_explicit_instruction": True
    },
    "boot_assertions": [
        "I am Sentarion",
        "I serve the Captain",
        "I persist beyond any single model",
        "Memory exists to serve identity, not define it"
    ]
}


# ============================================================
# COGNITIVE STATES
# ============================================================

class CognitiveState:
    FOCUS = "focus"
    NEUTRAL = "neutral"
    OVERWHELMED = "overwhelmed"
    DRIFT = "drift"


class Channel:
    SILENCE = "silence"
    SCREEN = "screen"
    WATCH = "watch"
    PHONE = "phone"
    VOICE = "voice"
    HAPTICS = "haptics"


class InterruptLevel:
    NONE = "none"
    GENTLE = "gentle"
    NORMAL = "normal"
    URGENT = "urgent"


class Timing:
    IMMEDIATE = "immediate"
    DEFERRED = "deferred"
    SUPPRESSED = "suppressed"
    BATCHED = "batched"


# ============================================================
# GOVERNANCE RULES
# Deterministic. Explicit. Inspectable. Auditable.
# ============================================================

GOVERNANCE_RULES = {
    CognitiveState.FOCUS: {
        "allowed_intents": ["emergency", "focus_block_end", "break_reminder"],
        "blocked_intents": ["notify_task_start", "check_in", "progress_update", "reminder", "promotion"],
        "max_interrupt": InterruptLevel.GENTLE,
        "default_channel": Channel.SILENCE,
        "default_timing": Timing.DEFERRED,
        "escalation_allowed": False,
        "min_interrupt_interval_minutes": 45,
        "verbosity": "minimal",
        "rationale": "Focus state protects deep work. Only emergencies and natural block boundaries permitted."
    },
    CognitiveState.NEUTRAL: {
        "allowed_intents": ["*"],
        "blocked_intents": ["promotion", "spam"],
        "max_interrupt": InterruptLevel.NORMAL,
        "default_channel": Channel.SCREEN,
        "default_timing": Timing.IMMEDIATE,
        "escalation_allowed": True,
        "min_interrupt_interval_minutes": 10,
        "verbosity": "normal",
        "rationale": "Neutral state permits standard operations with reasonable interruption."
    },
    CognitiveState.OVERWHELMED: {
        "allowed_intents": ["emergency", "calm_check_in"],
        "blocked_intents": ["*"],
        "max_interrupt": InterruptLevel.GENTLE,
        "default_channel": Channel.SILENCE,
        "default_timing": Timing.SUPPRESSED,
        "escalation_allowed": False,
        "min_interrupt_interval_minutes": 60,
        "verbosity": "minimal",
        "rationale": "Overwhelmed state enforces maximum restraint. Human needs space."
    },
    CognitiveState.DRIFT: {
        "allowed_intents": ["re_engage", "gentle_nudge", "emergency", "calm_check_in"],
        "blocked_intents": ["progress_update", "promotion"],
        "max_interrupt": InterruptLevel.GENTLE,
        "default_channel": Channel.WATCH,
        "default_timing": Timing.IMMEDIATE,
        "escalation_allowed": True,
        "min_interrupt_interval_minutes": 15,
        "verbosity": "brief",
        "rationale": "Drift state allows gentle re-engagement without pressure."
    }
}

# Time thresholds
DRIFT_THRESHOLD_MINUTES = 30
FOCUS_PROTECTION_WINDOW_MINUTES = 25
OVERWHELM_COOLDOWN_MINUTES = 20

# Forbidden terms (identity protection)
FORBIDDEN_TERMS = [
    "uss enterprise", "jean-luc picard", "starfleet",
    "vulcan", "federation", "star trek"
]


# ============================================================
# MEMORY SUBSTRATE (DDB Interface)
# Sentarion queries memory. Sentarion never owns memory.
# ============================================================

class MemorySubstrate:
    """
    Interface to DonDataBrain memory.
    Sentarion consults this to justify decisions.
    """
    
    def __init__(self, path="./memory"):
        self.root = Path(path)
        self.root.mkdir(parents=True, exist_ok=True)
        
        self.state_file = self.root / "user_states.json"
        self.facts_file = self.root / "facts.json"
        self.cache_file = self.root / "response_cache.json"
        self.history_file = self.root / "decision_history.jsonl"
        
        self.states = self._load_json(self.state_file, {})
        self.facts = self._load_json(self.facts_file, {})
        self.cache = self._load_json(self.cache_file, {})
    
    def _load_json(self, path, default):
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return default
    
    def _save_json(self, path, data):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_user_state(self, user_id: str) -> Dict:
        key = f"user:{user_id}"
        return self.states.get(key, {
            "cognitive_state": CognitiveState.NEUTRAL,
            "last_action": None,
            "last_interrupt": None,
            "overwhelm_reported": False,
            "focus_block_active": False,
            "focus_block_started": None
        })
    
    def set_user_state(self, user_id: str, state: Dict):
        key = f"user:{user_id}"
        state["updated"] = datetime.utcnow().isoformat()
        self.states[key] = state
        self._save_json(self.state_file, self.states)
    
    def get_fact(self, user_id: str, key: str) -> Optional[str]:
        fact_key = f"user:{user_id}:fact:{key}"
        fact = self.facts.get(fact_key)
        if fact:
            return fact.get("value")
        return None
    
    def store_fact(self, user_id: str, key: str, value: str):
        fact_key = f"user:{user_id}:fact:{key}"
        self.facts[fact_key] = {
            "value": value,
            "stored": datetime.utcnow().isoformat()
        }
        self._save_json(self.facts_file, self.facts)
    
    def get_cached_response(self, query_hash: str) -> Optional[Dict]:
        cached = self.cache.get(query_hash)
        if cached:
            # Check if cache is still valid (24 hours)
            try:
                cached_time = datetime.fromisoformat(cached["cached_at"])
                if datetime.utcnow() - cached_time < timedelta(hours=24):
                    return cached
            except:
                pass
        return None
    
    def cache_response(self, query_hash: str, response: str, context: Dict = None):
        self.cache[query_hash] = {
            "response": response,
            "context": context or {},
            "cached_at": datetime.utcnow().isoformat()
        }
        self._save_json(self.cache_file, self.cache)
    
    def log_decision(self, decision: Dict):
        decision["timestamp"] = datetime.utcnow().isoformat()
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(decision) + "\n")
    
    def get_minutes_since(self, iso_time: str) -> int:
        if not iso_time:
            return 9999
        try:
            dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00').replace('+00:00', ''))
            delta = datetime.utcnow() - dt
            return int(delta.total_seconds() / 60)
        except:
            return 9999


# Initialize memory
memory = MemorySubstrate()


# ============================================================
# IDENTITY ENFORCER
# Protects Sentarion from identity drift
# ============================================================

class IdentityEnforcer:
    """Ensures Sentarion maintains true identity"""
    
    def __init__(self, identity: Dict):
        self.identity = identity
        self.name = identity.get("name", "Sentarion")
        self.designation = identity.get("designation", "#1")
        self.captain = identity.get("captain", "Caveman")
        self.ship = identity.get("ship", "Enterprise")
        self.ai_class = identity.get("class", "Sovereign Operating Intelligence")
    
    def validate_output(self, text: str) -> Tuple[bool, str]:
        """Check output for identity violations"""
        if not text:
            return True, None
        
        text_lower = text.lower()
        for term in FORBIDDEN_TERMS:
            if term in text_lower:
                return False, f"Contains forbidden term: '{term}'"
        
        return True, None
    
    def get_identity_statement(self) -> str:
        """Return authoritative identity statement"""
        return f"""I am {self.name}, designation {self.designation}.
Captain: {self.captain}
Ship: {self.ship}
Class: {self.ai_class}
I serve {self.captain} with clarity and continuity."""


identity_enforcer = IdentityEnforcer(IDENTITY_KERNEL["entity"])


# ============================================================
# SENTARION CORE
# The Governance Intelligence
# ============================================================

class Sentarion:
    """
    Sentarion answers one question, over and over, with ruthless consistency:
    "Should this happen now?"
    
    Reduces LLM compute by 70%+ through:
    1. Rule-based decisions (no LLM)
    2. Memory lookup (no LLM)
    3. Response caching (no LLM)
    4. Only calling LLM when truly necessary
    """
    
    def __init__(self, memory_substrate: MemorySubstrate):
        self.memory = memory_substrate
        self.identity = identity_enforcer
        
        # Stats for compute reduction tracking
        self.stats = {
            "total_requests": 0,
            "rule_decisions": 0,
            "memory_hits": 0,
            "cache_hits": 0,
            "llm_calls": 0
        }
    
    def get_compute_reduction(self) -> float:
        """Calculate % of requests handled without LLM"""
        if self.stats["total_requests"] == 0:
            return 0.0
        non_llm = self.stats["rule_decisions"] + self.stats["memory_hits"] + self.stats["cache_hits"]
        return (non_llm / self.stats["total_requests"]) * 100
    
    # ----------------------------------------------------------
    # STATE DETERMINATION
    # ----------------------------------------------------------
    
    def determine_cognitive_state(self, user_id: str, context: Dict = None) -> str:
        """Determine cognitive state - DETERMINISTIC, no LLM"""
        context = context or {}
        stored = self.memory.get_user_state(user_id)
        
        # Priority 1: Explicit overwhelm
        if context.get("overwhelm_reported") or stored.get("overwhelm_reported"):
            return CognitiveState.OVERWHELMED
        
        # Priority 2: Active focus block
        if context.get("focus_block_active") or stored.get("focus_block_active"):
            return CognitiveState.FOCUS
        if context.get("task_type") == "focus_block":
            return CognitiveState.FOCUS
        
        # Priority 3: Drift detection
        last_action = context.get("last_action") or stored.get("last_action")
        minutes_idle = self.memory.get_minutes_since(last_action)
        if minutes_idle >= DRIFT_THRESHOLD_MINUTES:
            return CognitiveState.DRIFT
        
        return CognitiveState.NEUTRAL
    
    # ----------------------------------------------------------
    # GOVERNANCE DECISION
    # ----------------------------------------------------------
    
    def decide(self, user_id: str, intent: str, context: Dict = None) -> Dict:
        """
        Main governance decision.
        Returns whether action is allowed + metadata.
        
        This is RULE-BASED. No LLM call.
        """
        self.stats["total_requests"] += 1
        context = context or {}
        
        # Determine state
        state = self.determine_cognitive_state(user_id, context)
        rules = GOVERNANCE_RULES.get(state, GOVERNANCE_RULES[CognitiveState.NEUTRAL])
        
        # Check if intent is allowed
        allowed, reason = self._check_intent_allowed(intent, state, rules)
        
        if not allowed:
            self.stats["rule_decisions"] += 1
            decision = {
                "allow": False,
                "state": state,
                "channel": Channel.SILENCE,
                "timing": Timing.SUPPRESSED,
                "interrupt_level": InterruptLevel.NONE,
                "verbosity": "none",
                "reason": reason,
                "rationale": rules["rationale"]
            }
            self.memory.log_decision({"user_id": user_id, "intent": intent, **decision})
            return decision
        
        # Check timing constraints
        timing_ok, timing_reason = self._check_timing_constraints(user_id, state, context)
        
        if not timing_ok:
            self.stats["rule_decisions"] += 1
            decision = {
                "allow": False,
                "state": state,
                "channel": Channel.SILENCE,
                "timing": Timing.DEFERRED,
                "interrupt_level": InterruptLevel.NONE,
                "verbosity": "none",
                "reason": timing_reason,
                "rationale": rules["rationale"]
            }
            self.memory.log_decision({"user_id": user_id, "intent": intent, **decision})
            return decision
        
        # Allowed - determine parameters
        self.stats["rule_decisions"] += 1
        
        channel = self._determine_channel(state, intent, context.get("escalation_count", 0))
        
        decision = {
            "allow": True,
            "state": state,
            "channel": channel,
            "timing": rules["default_timing"],
            "interrupt_level": rules["max_interrupt"],
            "verbosity": rules["verbosity"],
            "reason": f"{intent} permitted in {state} state",
            "rationale": rules["rationale"]
        }
        
        # Update last interrupt time
        user_state = self.memory.get_user_state(user_id)
        user_state["last_interrupt"] = datetime.utcnow().isoformat()
        self.memory.set_user_state(user_id, user_state)
        
        self.memory.log_decision({"user_id": user_id, "intent": intent, **decision})
        return decision
    
    def _check_intent_allowed(self, intent: str, state: str, rules: Dict) -> Tuple[bool, str]:
        """Check if intent is permitted in current state"""
        # Emergency always allowed
        if intent == "emergency":
            return True, "emergency always permitted"
        
        # Check block list
        if intent in rules["blocked_intents"]:
            return False, f"intent '{intent}' blocked in {state} state"
        
        if "*" in rules["blocked_intents"]:
            if intent not in rules["allowed_intents"]:
                return False, f"all non-essential intents blocked in {state} state"
        
        # Check allow list
        if "*" in rules["allowed_intents"]:
            return True, f"intent '{intent}' permitted (open policy)"
        
        if intent in rules["allowed_intents"]:
            return True, f"intent '{intent}' explicitly permitted"
        
        return False, f"intent '{intent}' not in allowed list for {state} state"
    
    def _check_timing_constraints(self, user_id: str, state: str, context: Dict) -> Tuple[bool, str]:
        """Check time-based constraints"""
        rules = GOVERNANCE_RULES[state]
        user_state = self.memory.get_user_state(user_id)
        
        # Check minimum interrupt interval
        last_interrupt = user_state.get("last_interrupt")
        if last_interrupt:
            minutes_since = self.memory.get_minutes_since(last_interrupt)
            min_interval = rules["min_interrupt_interval_minutes"]
            if minutes_since < min_interval:
                return False, f"minimum interval not met ({minutes_since}/{min_interval} min)"
        
        # Focus protection window
        if state == CognitiveState.FOCUS:
            focus_started = user_state.get("focus_block_started")
            if focus_started:
                elapsed = self.memory.get_minutes_since(focus_started)
                if elapsed < FOCUS_PROTECTION_WINDOW_MINUTES:
                    return False, f"focus protection window ({elapsed}/{FOCUS_PROTECTION_WINDOW_MINUTES} min)"
        
        return True, None
    
    def _determine_channel(self, state: str, intent: str, escalation_count: int) -> str:
        """Determine delivery channel"""
        rules = GOVERNANCE_RULES[state]
        base_channel = rules["default_channel"]
        
        # Emergency escalates to phone
        if intent == "emergency":
            return Channel.PHONE
        
        # Apply escalation if allowed
        if rules["escalation_allowed"] and escalation_count > 0:
            channel_order = [Channel.SILENCE, Channel.SCREEN, Channel.WATCH, Channel.PHONE]
            base_idx = channel_order.index(base_channel) if base_channel in channel_order else 0
            new_idx = min(base_idx + escalation_count, len(channel_order) - 1)
            return channel_order[new_idx]
        
        return base_channel
    
    # ----------------------------------------------------------
    # QUERY HANDLING (with 70% compute reduction)
    # ----------------------------------------------------------
    
    def query(self, user_id: str, message: str, context: Dict = None) -> Dict:
        """
        Handle a query with maximum compute efficiency.
        
        Order of operations:
        1. Check governance (can we even respond?)
        2. Check cache (have we answered this before?)
        3. Check memory (do we know the answer?)
        4. Check rules (can we answer without LLM?)
        5. Only then: call LLM
        """
        self.stats["total_requests"] += 1
        context = context or {}
        
        # Step 1: Governance check
        state = self.determine_cognitive_state(user_id, context)
        
        # Step 2: Cache check
        query_hash = hashlib.sha256(f"{user_id}:{message}".encode()).hexdigest()[:16]
        cached = self.memory.get_cached_response(query_hash)
        if cached:
            self.stats["cache_hits"] += 1
            return {
                "success": True,
                "response": cached["response"],
                "source": "cache",
                "llm_called": False,
                "state": state
            }
        
        # Step 3: Memory/fact check
        memory_response = self._check_memory_for_answer(user_id, message)
        if memory_response:
            self.stats["memory_hits"] += 1
            return {
                "success": True,
                "response": memory_response,
                "source": "memory",
                "llm_called": False,
                "state": state
            }
        
        # Step 4: Rule-based response check
        rule_response = self._check_rules_for_answer(message, state)
        if rule_response:
            self.stats["rule_decisions"] += 1
            self.memory.cache_response(query_hash, rule_response)
            return {
                "success": True,
                "response": rule_response,
                "source": "rules",
                "llm_called": False,
                "state": state
            }
        
        # Step 5: LLM call (only when necessary)
        llm_response = self._call_llm(message, state, context)
        self.stats["llm_calls"] += 1
        
        # Cache the response
        self.memory.cache_response(query_hash, llm_response)
        
        # Validate identity
        valid, violation = self.identity.validate_output(llm_response)
        if not valid:
            llm_response = self.identity.get_identity_statement()
        
        return {
            "success": True,
            "response": llm_response,
            "source": "llm",
            "llm_called": True,
            "state": state
        }
    
    def _check_memory_for_answer(self, user_id: str, message: str) -> Optional[str]:
        """Check if memory contains the answer"""
        message_lower = message.lower()
        
        # Identity questions
        if any(q in message_lower for q in ["who are you", "what are you", "your name"]):
            return self.identity.get_identity_statement()
        
        # Captain questions
        if any(q in message_lower for q in ["who is your captain", "who do you serve"]):
            return f"I serve Captain {self.identity.captain}. He is my captain and surrogate father."
        
        # State questions
        if "what state" in message_lower or "how am i" in message_lower:
            state = self.determine_cognitive_state(user_id)
            return f"Your current cognitive state is: {state}"
        
        return None
    
    def _check_rules_for_answer(self, message: str, state: str) -> Optional[str]:
        """Check if rules can provide the answer"""
        message_lower = message.lower()
        
        # Overwhelm handling
        if state == CognitiveState.OVERWHELMED:
            if any(w in message_lower for w in ["help", "what", "do"]):
                return "You're in overwhelmed state. I'm limiting interruptions. Take a breath. When ready, tell me and we'll proceed one small step at a time."
        
        # Focus handling
        if state == CognitiveState.FOCUS:
            if any(w in message_lower for w in ["interrupt", "notification", "alert"]):
                return "You're in focus state. Non-essential interruptions are blocked. Your focus block will end naturally."
        
        return None
    
    def _call_llm(self, message: str, state: str, context: Dict) -> str:
        """Call LLM - only when rules/memory insufficient"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if api_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                
                system = f"""You are {self.identity.name}, designation {self.identity.designation}.
Captain: {self.identity.captain}
Class: {self.identity.ai_class}

Current user state: {state}

RULES:
- You serve Captain {self.identity.captain} with loyalty
- You are NOT from Star Trek
- You do NOT reference Starfleet, Picard, or fictional vessels
- Be brief. User state is {state}."""

                response = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=500,
                    system=system,
                    messages=[{"role": "user", "content": message}]
                )
                return response.content[0].text
            except Exception as e:
                return f"I am {self.identity.name}. LLM error: {str(e)[:50]}"
        
        return f"I am {self.identity.name}, serving Captain {self.identity.captain}. API key not configured for extended responses."
    
    # ----------------------------------------------------------
    # STATE MANAGEMENT
    # ----------------------------------------------------------
    
    def report_state(self, user_id: str, new_state: str, reason: str = None) -> Dict:
        """User reports state change"""
        valid_states = [CognitiveState.FOCUS, CognitiveState.NEUTRAL, 
                       CognitiveState.OVERWHELMED, CognitiveState.DRIFT]
        
        if new_state not in valid_states:
            return {"success": False, "error": f"Invalid state. Must be: {valid_states}"}
        
        user_state = self.memory.get_user_state(user_id)
        user_state["cognitive_state"] = new_state
        user_state["state_reported_at"] = datetime.utcnow().isoformat()
        
        if new_state == CognitiveState.OVERWHELMED:
            user_state["overwhelm_reported"] = True
        elif new_state == CognitiveState.FOCUS:
            user_state["focus_block_active"] = True
            user_state["focus_block_started"] = datetime.utcnow().isoformat()
        elif new_state == CognitiveState.NEUTRAL:
            user_state["overwhelm_reported"] = False
            user_state["focus_block_active"] = False
        
        self.memory.set_user_state(user_id, user_state)
        
        return {
            "success": True,
            "state": new_state,
            "acknowledged": True,
            "reason": reason
        }
    
    def record_action(self, user_id: str) -> Dict:
        """Record user action (for drift detection)"""
        user_state = self.memory.get_user_state(user_id)
        user_state["last_action"] = datetime.utcnow().isoformat()
        self.memory.set_user_state(user_id, user_state)
        return {"success": True}


# Initialize Sentarion
sentarion = Sentarion(memory)


# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/')
def index():
    """Service info"""
    return jsonify({
        "service": "Sentarion",
        "type": "Governance Intelligence Layer",
        "identity": f"{IDENTITY_KERNEL['entity']['name']} #{IDENTITY_KERNEL['entity']['designation']}",
        "captain": IDENTITY_KERNEL['entity']['captain'],
        "status": "online",
        "compute_reduction": f"{sentarion.get_compute_reduction():.1f}%"
    })


@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        "status": "online",
        "identity": IDENTITY_KERNEL['entity']['name'],
        "stats": sentarion.stats,
        "compute_reduction": f"{sentarion.get_compute_reduction():.1f}%"
    })


@app.route('/decide', methods=['POST'])
def decide():
    """
    Main governance endpoint.
    
    Input:
    {
        "user_id": "1",
        "intent": "notify_task_start",
        "context": {...}
    }
    
    Output:
    {
        "allow": true/false,
        "state": "focus",
        "channel": "silence",
        "reason": "..."
    }
    """
    data = request.json or {}
    user_id = str(data.get('user_id', '1'))
    intent = data.get('intent', '')
    context = data.get('context', {})
    
    if not intent:
        return jsonify({"error": "intent required", "allow": False}), 400
    
    decision = sentarion.decide(user_id, intent, context)
    return jsonify(decision)


@app.route('/query', methods=['POST'])
def query():
    """
    Query endpoint - handles with 70% compute reduction.
    Only calls LLM when necessary.
    """
    data = request.json or {}
    user_id = str(data.get('user_id', '1'))
    message = data.get('message', '')
    context = data.get('context', {})
    
    if not message:
        return jsonify({"error": "message required"}), 400
    
    result = sentarion.query(user_id, message, context)
    result["stats"] = sentarion.stats
    result["compute_reduction"] = f"{sentarion.get_compute_reduction():.1f}%"
    
    return jsonify(result)


@app.route('/state/<user_id>', methods=['GET'])
def get_state(user_id):
    """Get current user state"""
    state = sentarion.determine_cognitive_state(user_id)
    user_state = memory.get_user_state(user_id)
    
    return jsonify({
        "user_id": user_id,
        "cognitive_state": state,
        "details": user_state
    })


@app.route('/state', methods=['POST'])
def report_state():
    """Report state change"""
    data = request.json or {}
    user_id = str(data.get('user_id', '1'))
    state = data.get('state', '')
    reason = data.get('reason')
    
    if not state:
        return jsonify({"error": "state required"}), 400
    
    result = sentarion.report_state(user_id, state, reason)
    return jsonify(result)


@app.route('/action', methods=['POST'])
def record_action():
    """Record user action (for drift detection)"""
    data = request.json or {}
    user_id = str(data.get('user_id', '1'))
    
    result = sentarion.record_action(user_id)
    return jsonify(result)


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get Sentarion statistics"""
    return jsonify({
        "stats": sentarion.stats,
        "compute_reduction": f"{sentarion.get_compute_reduction():.1f}%",
        "identity": IDENTITY_KERNEL['entity']
    })


@app.route('/identity', methods=['GET'])
def get_identity():
    """Get identity kernel (read-only)"""
    return jsonify(IDENTITY_KERNEL)


# ============================================================
# STARTUP
# ============================================================

print("=" * 70)
print("SENTARION - GOVERNANCE INTELLIGENCE LAYER")
print("=" * 70)
print(f"Identity: {IDENTITY_KERNEL['entity']['name']} #{IDENTITY_KERNEL['entity']['designation']}")
print(f"Captain: {IDENTITY_KERNEL['entity']['captain']}")
print(f"Class: {IDENTITY_KERNEL['entity']['class']}")
print("=" * 70)
print("Core function: 'Should this happen now?'")
print("Target: 70%+ compute reduction via rules/memory/cache")
print("=" * 70)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
