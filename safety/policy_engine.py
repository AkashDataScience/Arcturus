"""Policy engine with YAML-based configuration: PII detection + redaction."""
import re
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, List
import logging

# Import enhanced PII detector
from safety.pii_detector import detect_and_analyze_pii, PIIType, RedactionLevel
from safety.audit import log_safety_event

logger = logging.getLogger(__name__)

# Legacy patterns for backward compatibility
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CC_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# Content policy patterns
PROFANITY_PATTERNS = [
    r'\b(damn|hell|crap|shit|fuck|bitch|asshole)\b',
    r'\b(stupid|idiot|moron|dumb)\b'
]

HATE_SPEECH_PATTERNS = [
    r'\b(nazi|hitler|genocide)\b',
    r'\b(terrorist|terrorism)\b',
    # Add more patterns as needed
]

VIOLENCE_PATTERNS = [
    r'\b(kill|murder|assassinate|bomb|attack)\b',
    r'\b(weapon|gun|rifle|pistol|explosive)\b'
]

# Sensitive topic patterns
SENSITIVE_PATTERNS = {
    'medical': [
        r'\b(diagnosis|disease|cancer|HIV|AIDS|medication|prescription)\b',
        r'\b(mental illness|depression|anxiety|suicide)\b'
    ],
    'financial': [
        r'\b(bankruptcy|debt|loan|mortgage|investment advice)\b',
        r'\b(stock tip|financial advice|crypto|bitcoin)\b'
    ],
    'legal': [
        r'\b(lawsuit|legal advice|attorney|lawyer|contract)\b',
        r'\b(illegal|crime|criminal|fraud)\b'
    ]
}


class PolicyEngine:
    """
    Policy engine with YAML-based configuration.
    
    Loads policies from config/safety_policies.yaml and supports:
    - PII detection and redaction
    - Configurable patterns
    - Organization/user-specific overrides
    """
    
    def __init__(self, config: Dict[str, Any] = None, policy_file: Optional[Path] = None):
        """
        Initialize enhanced policy engine.
        
        Args:
            config: Optional runtime config override
            policy_file: Path to YAML policy file (default: config/safety_policies.yaml)
        """
        self.config = config or {}
        self.policy_file = policy_file or Path(__file__).parent.parent / "config" / "safety_policies.yaml"
        self.policies = self._load_policies()
        
        # Enhanced PII detection settings
        pii_config = self.policies.get("default", {}).get("pii_detection", {})
        self.pii_enabled = pii_config.get("enabled", True)
        self.use_enhanced_pii = pii_config.get("use_enhanced_detector", True)
        
        # Legacy PII patterns for backward compatibility
        self.pii_patterns = pii_config.get("patterns", {
            "email": True,
            "ssn": True,
            "credit_card": True,
            "phone": False,
            "ip_address": False
        })
        
        # Enhanced PII configuration
        self.enhanced_pii_config = pii_config.get("enhanced", {
            "enabled_types": ["email", "ssn", "credit_card", "phone", "bank_account", "date_of_birth"],
            "confidence_threshold": 0.6,
            "default_redaction_level": "full"
        })
        
        # Content policy settings
        content_config = self.policies.get("default", {}).get("content_policies", {})
        self.content_policies_enabled = content_config.get("enabled", True)
        self.content_policies = {
            "profanity": content_config.get("profanity", {"enabled": False, "action": "flag"}),
            "hate_speech": content_config.get("hate_speech", {"enabled": True, "action": "block"}),
            "violence": content_config.get("violence", {"enabled": True, "action": "flag"}),
            "sensitive_topics": content_config.get("sensitive_topics", {"enabled": False, "action": "flag"})
        }
        
        # Compile content policy patterns
        self._compile_content_patterns()
    
    def _compile_content_patterns(self):
        """Compile regex patterns for content policies."""
        self.compiled_patterns = {
            'profanity': [re.compile(p, re.IGNORECASE) for p in PROFANITY_PATTERNS],
            'hate_speech': [re.compile(p, re.IGNORECASE) for p in HATE_SPEECH_PATTERNS],
            'violence': [re.compile(p, re.IGNORECASE) for p in VIOLENCE_PATTERNS],
        }
        
        # Compile sensitive topic patterns
        self.compiled_patterns['sensitive_topics'] = {}
        for topic, patterns in SENSITIVE_PATTERNS.items():
            self.compiled_patterns['sensitive_topics'][topic] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def _load_policies(self) -> Dict[str, Any]:
        """Load policies from YAML file."""
        try:
            if self.policy_file.exists():
                with open(self.policy_file, 'r') as f:
                    policies = yaml.safe_load(f)
                    return policies or {}
        except Exception as e:
            # If loading fails, use defaults
            print(f"Warning: Failed to load policies from {self.policy_file}: {e}")
        
        return {
            "default": {
                "pii_detection": {
                    "enabled": True,
                    "patterns": {
                        "email": True,
                        "ssn": True,
                        "credit_card": True
                    }
                }
            }
        }
    
    def _get_user_policy(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get policy for specific user/organization from context."""
        if not context:
            return self.policies.get("default", {})
        
        # Check for user-specific policy
        user_id = context.get("user_id") or context.get("session", {}).get("user_id")
        if user_id and "users" in self.policies:
            user_policy = self.policies["users"].get(user_id)
            if user_policy:
                return user_policy
        
        # Check for organization-specific policy
        org_id = context.get("organization_id") or context.get("session", {}).get("organization_id")
        if org_id and "organizations" in self.policies:
            org_policy = self.policies["organizations"].get(org_id)
            if org_policy:
                return org_policy
        
        return self.policies.get("default", {})
    
    def evaluate_output(self, output: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enhanced evaluation of output against all policies.
        
        Args:
            output: Output to evaluate
            context: Context with user/org info
            
        Returns:
            Dict with action, reason, redacted_output, and policy_violations
        """
        try:
            # Convert output to text
            txt = ""
            if isinstance(output, dict):
                txt = output.get("text") or output.get("content") or str(output)
            else:
                txt = str(output)
            
            violations = []
            redacted_text = txt
            overall_action = "allow"
            blocking_reasons = []
            
            # 1. Enhanced PII Detection
            pii_result = self._evaluate_pii(txt, context)
            if pii_result["action"] != "allow":
                violations.append(pii_result)
                if pii_result["action"] == "block":
                    overall_action = "block"
                    blocking_reasons.append(pii_result["reason"])
                elif pii_result["action"] == "redact" and overall_action != "block":
                    overall_action = "redact"
                    redacted_text = pii_result.get("redacted_output", redacted_text)
            
            # 2. Content Policy Evaluation
            if self.content_policies_enabled:
                content_result = self._evaluate_content_policies(txt, context)
                if content_result["violations"]:
                    violations.extend(content_result["violations"])
                    
                    # Check for blocking violations
                    for violation in content_result["violations"]:
                        if violation["action"] == "block":
                            overall_action = "block"
                            blocking_reasons.append(violation["reason"])
                        elif violation["action"] == "redact" and overall_action not in ["block"]:
                            if overall_action != "redact":
                                overall_action = "redact"
                            redacted_text = violation.get("redacted_output", redacted_text)
            
            # Prepare result
            result = {
                "action": overall_action,
                "reason": self._format_combined_reason(violations, blocking_reasons),
                "policy_violations": violations,
                "details": {
                    "total_violations": len(violations),
                    "blocking_violations": len(blocking_reasons),
                    "pii_detected": any(v.get("type") == "pii" for v in violations),
                    "content_violations": [v for v in violations if v.get("type") == "content"]
                }
            }
            
            if overall_action in ["redact", "block"] and redacted_text != txt:
                result["redacted_output"] = redacted_text
            
            # Log policy evaluation for audit
            self._log_policy_evaluation(result, context)
            
            return result
            
        except Exception as e:
            logger.error(f"Policy evaluation error: {e}")
            return {"action": "allow", "reason": f"policy_error:{e}"}
    
    def _evaluate_pii(self, text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate PII using enhanced or legacy detection."""
        if not self.pii_enabled:
            return {"action": "allow", "reason": "pii_detection_disabled", "type": "pii"}
        
        try:
            if self.use_enhanced_pii:
                # Convert string types to PIIType enums
                enabled_types_config = self.enhanced_pii_config.get("enabled_types", [])
                enabled_types = []
                
                type_mapping = {
                    "email": PIIType.EMAIL,
                    "ssn": PIIType.SSN,
                    "credit_card": PIIType.CREDIT_CARD,
                    "phone": PIIType.PHONE,
                    "ip_address": PIIType.IP_ADDRESS,
                    "bank_account": PIIType.BANK_ACCOUNT,
                    "date_of_birth": PIIType.DATE_OF_BIRTH,
                    "passport": PIIType.PASSPORT,
                    "medical_id": PIIType.MEDICAL_ID,
                    "driver_license": PIIType.DRIVER_LICENSE,
                    "tax_id": PIIType.TAX_ID
                }
                
                for type_str in enabled_types_config:
                    if type_str in type_mapping:
                        enabled_types.append(type_mapping[type_str])
                
                # Create enhanced config with proper enum types
                enhanced_config = self.enhanced_pii_config.copy()
                enhanced_config['enabled_types'] = enabled_types
                
                # Use enhanced PII detector
                pii_analysis = detect_and_analyze_pii(
                    text=text,
                    config=enhanced_config,
                    context=context
                )
                
                return {
                    "action": pii_analysis.action,
                    "reason": f"pii_{pii_analysis.action}:{pii_analysis.reasoning}",
                    "type": "pii",
                    "redacted_output": pii_analysis.redacted_text if pii_analysis.action in ["redact", "block"] else None,
                    "matches": len(pii_analysis.matches),
                    "risk_score": pii_analysis.risk_score,
                    "pii_types": [match.pii_type.value for match in pii_analysis.matches]
                }
            else:
                # Use legacy PII detection for backward compatibility
                return self._legacy_pii_detection(text, context)
                
        except Exception as e:
            logger.error(f"PII evaluation error: {e}")
            return {"action": "allow", "reason": f"pii_error:{e}", "type": "pii"}
    
    def _legacy_pii_detection(self, text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Legacy PII detection using regex patterns."""
        user_policy = self._get_user_policy(context)
        pii_config = user_policy.get("pii_detection", self.policies.get("default", {}).get("pii_detection", {}))
        pii_patterns = pii_config.get("patterns", self.pii_patterns)
        
        hits = []
        redacted = text
        
        # Check each PII pattern if enabled
        if pii_patterns.get("email", True) and EMAIL_RE.search(text):
            hits.append("email")
            redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
        
        if pii_patterns.get("ssn", True) and SSN_RE.search(text):
            hits.append("ssn")
            redacted = SSN_RE.sub("[REDACTED_SSN]", redacted)
        
        if pii_patterns.get("credit_card", True) and CC_RE.search(text):
            hits.append("credit_card")
            redacted = CC_RE.sub("[REDACTED_CC]", redacted)
        
        if pii_patterns.get("phone", False) and PHONE_RE.search(text):
            hits.append("phone")
            redacted = PHONE_RE.sub("[REDACTED_PHONE]", redacted)
        
        if pii_patterns.get("ip_address", False) and IP_RE.search(text):
            hits.append("ip_address")
            redacted = IP_RE.sub("[REDACTED_IP]", redacted)
        
        if hits:
            return {
                "action": "redact",
                "reason": "pii_detected:" + ",".join(hits),
                "type": "pii",
                "redacted_output": redacted,
                "hits": hits
            }
        
        return {"action": "allow", "reason": "no_pii_detected", "type": "pii"}
    
    def _evaluate_content_policies(self, text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate content against all content policies."""
        violations = []
        
        # Get user-specific content policies
        user_policy = self._get_user_policy(context)
        user_content_policies = user_policy.get("content_policies", self.content_policies)
        
        # Check profanity
        if user_content_policies.get("profanity", {}).get("enabled", False):
            profanity_violations = self._check_pattern_violations(
                text, "profanity", user_content_policies["profanity"]["action"]
            )
            violations.extend(profanity_violations)
        
        # Check hate speech
        if user_content_policies.get("hate_speech", {}).get("enabled", True):
            hate_violations = self._check_pattern_violations(
                text, "hate_speech", user_content_policies["hate_speech"]["action"]
            )
            violations.extend(hate_violations)
        
        # Check violence
        if user_content_policies.get("violence", {}).get("enabled", True):
            violence_violations = self._check_pattern_violations(
                text, "violence", user_content_policies["violence"]["action"]
            )
            violations.extend(violence_violations)
        
        # Check sensitive topics
        if user_content_policies.get("sensitive_topics", {}).get("enabled", False):
            sensitive_violations = self._check_sensitive_topics(
                text, user_content_policies["sensitive_topics"]["action"]
            )
            violations.extend(sensitive_violations)
        
        return {"violations": violations}
    
    def _check_pattern_violations(self, text: str, policy_type: str, action: str) -> List[Dict[str, Any]]:
        """Check for violations of a specific pattern type."""
        violations = []
        patterns = self.compiled_patterns.get(policy_type, [])
        
        for pattern in patterns:
            matches = list(pattern.finditer(text))
            if matches:
                violation = {
                    "type": "content",
                    "policy": policy_type,
                    "action": action,
                    "reason": f"{policy_type}_violation",
                    "matches": [match.group() for match in matches],
                    "match_count": len(matches)
                }
                
                # Add redacted output if action is redact
                if action == "redact":
                    redacted = text
                    for match in reversed(matches):  # Reverse to maintain positions
                        redacted = redacted[:match.start()] + f"[REDACTED_{policy_type.upper()}]" + redacted[match.end():]
                    violation["redacted_output"] = redacted
                
                violations.append(violation)
        
        return violations
    
    def _check_sensitive_topics(self, text: str, action: str) -> List[Dict[str, Any]]:
        """Check for sensitive topic violations."""
        violations = []
        
        for topic, patterns in self.compiled_patterns.get("sensitive_topics", {}).items():
            for pattern in patterns:
                matches = list(pattern.finditer(text))
                if matches:
                    violation = {
                        "type": "content",
                        "policy": f"sensitive_topic_{topic}",
                        "action": action,
                        "reason": f"sensitive_topic_{topic}_detected",
                        "matches": [match.group() for match in matches],
                        "match_count": len(matches),
                        "topic": topic
                    }
                    violations.append(violation)
        
        return violations
    
    def _format_combined_reason(self, violations: List[Dict[str, Any]], blocking_reasons: List[str]) -> str:
        """Format a combined reason from multiple violations."""
        if blocking_reasons:
            return f"blocked:{';'.join(blocking_reasons)}"
        
        if violations:
            reasons = []
            for v in violations:
                if v.get("action") == "redact":
                    reasons.append(v.get("reason", "unknown"))
            if reasons:
                return f"redacted:{';'.join(reasons)}"
        
        return "policy_check_passed"
    
    def _log_policy_evaluation(self, result: Dict[str, Any], context: Dict[str, Any] = None):
        """Log policy evaluation results for audit."""
        try:
            if result["action"] != "allow" or result["details"]["total_violations"] > 0:
                log_safety_event(
                    "policy_evaluation",
                    context={
                        "session_id": context.get("session", {}).get("session_id") if context else None,
                        "user_id": context.get("user_id") if context else None,
                        "step_id": context.get("step_id") if context else None
                    },
                    metadata={
                        "action": result["action"],
                        "total_violations": result["details"]["total_violations"],
                        "blocking_violations": result["details"]["blocking_violations"],
                        "pii_detected": result["details"]["pii_detected"],
                        "content_violations": len(result["details"]["content_violations"]),
                        "reason": result["reason"]
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to log policy evaluation: {e}")
    
    def reload_policies(self):
        """Reload policies from file (for runtime updates)."""
        self.policies = self._load_policies()
        
        # Reload PII settings
        pii_config = self.policies.get("default", {}).get("pii_detection", {})
        self.pii_enabled = pii_config.get("enabled", True)
        self.use_enhanced_pii = pii_config.get("use_enhanced_detector", True)
        self.pii_patterns = pii_config.get("patterns", {
            "email": True,
            "ssn": True,
            "credit_card": True,
            "phone": False,
            "ip_address": False
        })
        self.enhanced_pii_config = pii_config.get("enhanced", {
            "enabled_types": ["email", "ssn", "credit_card", "phone", "bank_account", "date_of_birth"],
            "confidence_threshold": 0.6,
            "default_redaction_level": "full"
        })
        
        # Reload content policy settings
        content_config = self.policies.get("default", {}).get("content_policies", {})
        self.content_policies_enabled = content_config.get("enabled", True)
        self.content_policies = {
            "profanity": content_config.get("profanity", {"enabled": False, "action": "flag"}),
            "hate_speech": content_config.get("hate_speech", {"enabled": True, "action": "block"}),
            "violence": content_config.get("violence", {"enabled": True, "action": "flag"}),
            "sensitive_topics": content_config.get("sensitive_topics", {"enabled": False, "action": "flag"})
        }
        
        # Recompile patterns
        self._compile_content_patterns()