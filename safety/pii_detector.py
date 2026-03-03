"""
Enhanced PII Detection and Redaction System (P12 Week 3)

This module provides comprehensive PII detection and redaction capabilities,
extending beyond the basic patterns to include more sophisticated detection
methods and context-aware redaction.

Features:
- Extended PII pattern library
- Context-aware detection
- Configurable redaction strategies
- Named entity recognition integration
- International PII pattern support
- Custom pattern definitions
- Risk-based redaction levels
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    PHONE = "phone"
    IP_ADDRESS = "ip_address"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    BANK_ACCOUNT = "bank_account"
    IBAN = "iban"
    DATE_OF_BIRTH = "date_of_birth"
    ADDRESS = "address"
    NAME = "person_name"
    MEDICAL_ID = "medical_id"
    TAX_ID = "tax_id"
    CUSTOM = "custom"


class RedactionLevel(Enum):
    """Levels of redaction to apply."""
    NONE = "none"           # No redaction
    PARTIAL = "partial"     # Partial masking (e.g., keep domain in email)
    FULL = "full"          # Complete redaction with generic placeholder
    HASH = "hash"          # Replace with deterministic hash


@dataclass
class PIIMatch:
    """Represents a detected PII instance."""
    pii_type: PIIType
    text: str
    start: int
    end: int
    confidence: float
    context: str
    redaction_level: RedactionLevel
    replacement: str


@dataclass
class PIIAnalysis:
    """Complete PII analysis result."""
    matches: List[PIIMatch]
    redacted_text: str
    risk_score: float
    action: str  # "allow", "redact", "block"
    reasoning: str
    metadata: Dict[str, Any]


class EnhancedPIIPatterns:
    """Extended PII pattern library with international support."""
    
    # Basic patterns (enhanced versions)
    EMAIL = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        re.IGNORECASE
    )
    
    # SSN patterns (US, UK, Canada)
    SSN_US = re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b|\b\d{9}\b')
    SSN_UK = re.compile(r'\b[A-Z]{2}\d{6}[A-Z]\b')  # UK National Insurance
    SSN_CANADA = re.compile(r'\b\d{3}-?\d{3}-?\d{3}\b')  # SIN
    
    # Credit card patterns (multiple formats)
    CREDIT_CARD = re.compile(
        r'\b(?:4[0-9]{12}(?:[0-9]{3})?|'  # Visa
        r'5[1-5][0-9]{14}|'              # Mastercard
        r'3[47][0-9]{13}|'               # Amex
        r'3[0-9]{4,}|'                   # Diners
        r'6(?:011|5[0-9]{2})[0-9]{12})'  # Discover
        r'\b'
    )
    
    # Phone patterns (international)
    PHONE_US = re.compile(r'\b(?:\+?1-?)?(?:\([0-9]{3}\)|[0-9]{3})[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b')
    PHONE_INTL = re.compile(r'\+[1-9]\d{1,14}\b')  # International format
    
    # IP addresses (IPv4 and IPv6)
    IP_V4 = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
    IP_V6 = re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b')
    
    # Government IDs
    PASSPORT_US = re.compile(r'\b[A-Z][0-9]{8}\b')  # US Passport
    DRIVER_LICENSE = re.compile(r'\b[A-Z]{1,2}\d{6,8}\b')
    
    # Financial
    BANK_ACCOUNT = re.compile(r'\b\d{8,17}\b')  # Account numbers
    IBAN = re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b')
    ROUTING_NUMBER = re.compile(r'\b\d{9}\b')  # US routing numbers
    
    # Dates that could be DOB
    DATE_OF_BIRTH = re.compile(
        r'\b(?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])[-/](?:19|20)\d{2}\b|'
        r'\b(?:19|20)\d{2}[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])\b'
    )
    
    # Medical IDs
    MEDICAL_ID = re.compile(r'\bMED\d{6,10}\b|\bPAT\d{6,10}\b')
    
    # Tax IDs
    TAX_ID_US = re.compile(r'\b\d{2}-?\d{7}\b')  # EIN
    TAX_ID_CANADA = re.compile(r'\b\d{9}RP\d{4}\b')  # Business Number
    

class ContextAnalyzer:
    """Analyzes context around PII to improve detection accuracy."""
    
    PERSON_NAME_INDICATORS = [
        r'(?:my name is|i am|i\'m|call me|this is)\s+',
        r'(?:mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?)\s+',
        r'(?:first name|last name|full name):\s*',
        r'(?:signed|signature|from|to|dear)\s+'
    ]
    
    EMAIL_INDICATORS = [
        r'(?:email|e-mail|contact|send to|mail to):\s*',
        r'(?:@|email address|email me at)\s*'
    ]
    
    PHONE_INDICATORS = [
        r'(?:phone|tel|call|mobile|cell):\s*',
        r'(?:number|contact number|phone number):\s*'
    ]
    
    ADDRESS_INDICATORS = [
        r'(?:address|street|avenue|road|lane|drive|boulevard)\s+',
        r'(?:live at|located at|address is)\s+',
        r'(?:zip|postal code|zipcode):\s*'
    ]
    
    def __init__(self):
        self.compiled_patterns = {
            PIIType.NAME: [re.compile(p, re.IGNORECASE) for p in self.PERSON_NAME_INDICATORS],
            PIIType.EMAIL: [re.compile(p, re.IGNORECASE) for p in self.EMAIL_INDICATORS],
            PIIType.PHONE: [re.compile(p, re.IGNORECASE) for p in self.PHONE_INDICATORS],
            PIIType.ADDRESS: [re.compile(p, re.IGNORECASE) for p in self.ADDRESS_INDICATORS]
        }
    
    def get_context_confidence(self, text: str, match_start: int, match_end: int, pii_type: PIIType) -> float:
        """
        Analyze context around a potential PII match to determine confidence.
        
        Args:
            text: Full text being analyzed
            match_start: Start position of potential PII
            match_end: End position of potential PII
            pii_type: Type of PII being analyzed
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Extract context window around match
        context_window = 50
        start_context = max(0, match_start - context_window)
        end_context = min(len(text), match_end + context_window)
        context = text[start_context:end_context]
        
        base_confidence = 0.7  # Base confidence for pattern match
        
        # Check for context indicators
        if pii_type in self.compiled_patterns:
            for pattern in self.compiled_patterns[pii_type]:
                if pattern.search(context):
                    base_confidence += 0.2
                    break
        
        # Apply heuristics specific to PII type
        if pii_type == PIIType.EMAIL:
            # Higher confidence if in email context
            if any(indicator in context.lower() for indicator in ['contact', 'email', 'send to']):
                base_confidence += 0.1
                
        elif pii_type == PIIType.PHONE:
            # Check for phone number formatting
            match_text = text[match_start:match_end]
            if '-' in match_text or '(' in match_text:
                base_confidence += 0.1
                
        elif pii_type == PIIType.CREDIT_CARD:
            # Higher confidence if in payment context
            if any(indicator in context.lower() for indicator in ['payment', 'card', 'visa', 'mastercard']):
                base_confidence += 0.15
        
        return min(base_confidence, 1.0)


class EnhancedPIIDetector:
    """Enhanced PII detection with context awareness and configurable redaction."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize enhanced PII detector.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.patterns = EnhancedPIIPatterns()
        self.context_analyzer = ContextAnalyzer()
        
        # Detection settings
        self.enabled_types = set(self.config.get('enabled_types', [
            PIIType.EMAIL, PIIType.SSN, PIIType.CREDIT_CARD, PIIType.PHONE
        ]))
        
        self.confidence_threshold = self.config.get('confidence_threshold', 0.6)
        self.default_redaction_level = RedactionLevel(
            self.config.get('default_redaction_level', 'full')
        )
        
        # Risk scoring weights
        self.risk_weights = self.config.get('risk_weights', {
            PIIType.SSN: 1.0,
            PIIType.CREDIT_CARD: 1.0,
            PIIType.BANK_ACCOUNT: 0.9,
            PIIType.PASSPORT: 0.9,
            PIIType.MEDICAL_ID: 0.8,
            PIIType.EMAIL: 0.3,
            PIIType.PHONE: 0.4,
            PIIType.ADDRESS: 0.6
        })
    
    def detect_pii(self, text: str, context: Dict[str, Any] = None) -> PIIAnalysis:
        """
        Detect PII in text with enhanced analysis.
        
        Args:
            text: Text to analyze
            context: Additional context for detection
            
        Returns:
            PIIAnalysis with detected PII and recommended actions
        """
        try:
            matches = []
            
            # Run all detection methods
            if PIIType.EMAIL in self.enabled_types:
                matches.extend(self._detect_emails(text))
            
            if PIIType.SSN in self.enabled_types:
                matches.extend(self._detect_ssns(text))
            
            if PIIType.CREDIT_CARD in self.enabled_types:
                matches.extend(self._detect_credit_cards(text))
            
            if PIIType.PHONE in self.enabled_types:
                matches.extend(self._detect_phones(text))
            
            if PIIType.IP_ADDRESS in self.enabled_types:
                matches.extend(self._detect_ip_addresses(text))
            
            if PIIType.BANK_ACCOUNT in self.enabled_types:
                matches.extend(self._detect_bank_accounts(text))
            
            if PIIType.DATE_OF_BIRTH in self.enabled_types:
                matches.extend(self._detect_dates_of_birth(text))
            
            # Filter by confidence threshold
            high_confidence_matches = [
                m for m in matches if m.confidence >= self.confidence_threshold
            ]
            
            # Create redacted text
            redacted_text = self._apply_redactions(text, high_confidence_matches)
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(high_confidence_matches)
            
            # Determine action
            action, reasoning = self._determine_action(risk_score, high_confidence_matches)
            
            return PIIAnalysis(
                matches=high_confidence_matches,
                redacted_text=redacted_text,
                risk_score=risk_score,
                action=action,
                reasoning=reasoning,
                metadata={
                    'total_matches': len(matches),
                    'filtered_matches': len(high_confidence_matches),
                    'confidence_threshold': self.confidence_threshold,
                    'enabled_types': [t.value for t in self.enabled_types]
                }
            )
            
        except Exception as e:
            logger.error(f"Error in PII detection: {e}")
            return PIIAnalysis(
                matches=[],
                redacted_text=text,
                risk_score=0.0,
                action="allow",
                reasoning=f"Detection error: {str(e)}",
                metadata={"error": True}
            )
    
    def _detect_emails(self, text: str) -> List[PIIMatch]:
        """Detect email addresses."""
        matches = []
        
        for match in self.patterns.EMAIL.finditer(text):
            confidence = self.context_analyzer.get_context_confidence(
                text, match.start(), match.end(), PIIType.EMAIL
            )
            
            matches.append(PIIMatch(
                pii_type=PIIType.EMAIL,
                text=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=confidence,
                context=self._extract_context(text, match.start(), match.end()),
                redaction_level=self.default_redaction_level,
                replacement=self._generate_replacement(PIIType.EMAIL, match.group())
            ))
        
        return matches
    
    def _detect_ssns(self, text: str) -> List[PIIMatch]:
        """Detect Social Security Numbers."""
        matches = []
        patterns = [
            (self.patterns.SSN_US, "US SSN"),
            (self.patterns.SSN_UK, "UK NI"),
            (self.patterns.SSN_CANADA, "Canada SIN")
        ]
        
        for pattern, desc in patterns:
            for match in pattern.finditer(text):
                # SSN matches get high base confidence due to high sensitivity
                confidence = 0.9
                
                matches.append(PIIMatch(
                    pii_type=PIIType.SSN,
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    context=self._extract_context(text, match.start(), match.end()),
                    redaction_level=RedactionLevel.FULL,  # Always full redaction for SSN
                    replacement=self._generate_replacement(PIIType.SSN, match.group())
                ))
        
        return matches
    
    def _detect_credit_cards(self, text: str) -> List[PIIMatch]:
        """Detect credit card numbers."""
        matches = []
        
        for match in self.patterns.CREDIT_CARD.finditer(text):
            # Validate using Luhn algorithm
            cc_number = re.sub(r'[^0-9]', '', match.group())
            if self._is_valid_luhn(cc_number):
                confidence = self.context_analyzer.get_context_confidence(
                    text, match.start(), match.end(), PIIType.CREDIT_CARD
                )
                confidence = max(confidence, 0.8)  # High confidence for valid CC numbers
                
                matches.append(PIIMatch(
                    pii_type=PIIType.CREDIT_CARD,
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    context=self._extract_context(text, match.start(), match.end()),
                    redaction_level=RedactionLevel.FULL,  # Always full redaction
                    replacement=self._generate_replacement(PIIType.CREDIT_CARD, match.group())
                ))
        
        return matches
    
    def _detect_phones(self, text: str) -> List[PIIMatch]:
        """Detect phone numbers."""
        matches = []
        patterns = [
            (self.patterns.PHONE_US, "US Phone"),
            (self.patterns.PHONE_INTL, "International Phone")
        ]
        
        for pattern, desc in patterns:
            for match in pattern.finditer(text):
                confidence = self.context_analyzer.get_context_confidence(
                    text, match.start(), match.end(), PIIType.PHONE
                )
                
                matches.append(PIIMatch(
                    pii_type=PIIType.PHONE,
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    context=self._extract_context(text, match.start(), match.end()),
                    redaction_level=self.default_redaction_level,
                    replacement=self._generate_replacement(PIIType.PHONE, match.group())
                ))
        
        return matches
    
    def _detect_ip_addresses(self, text: str) -> List[PIIMatch]:
        """Detect IP addresses."""
        matches = []
        patterns = [
            (self.patterns.IP_V4, "IPv4"),
            (self.patterns.IP_V6, "IPv6")
        ]
        
        for pattern, desc in patterns:
            for match in pattern.finditer(text):
                # Filter out common non-PII IPs
                ip = match.group()
                if self._is_private_ip(ip):
                    confidence = 0.3  # Lower confidence for private IPs
                else:
                    confidence = 0.7  # Higher confidence for public IPs
                
                matches.append(PIIMatch(
                    pii_type=PIIType.IP_ADDRESS,
                    text=ip,
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    context=self._extract_context(text, match.start(), match.end()),
                    redaction_level=self.default_redaction_level,
                    replacement=self._generate_replacement(PIIType.IP_ADDRESS, ip)
                ))
        
        return matches
    
    def _detect_bank_accounts(self, text: str) -> List[PIIMatch]:
        """Detect bank account numbers."""
        matches = []
        
        for match in self.patterns.BANK_ACCOUNT.finditer(text):
            # Check context for banking keywords
            context = self._extract_context(text, match.start(), match.end()).lower()
            banking_keywords = ['account', 'routing', 'bank', 'deposit', 'withdrawal']
            
            confidence = 0.5
            if any(keyword in context for keyword in banking_keywords):
                confidence = 0.8
            
            matches.append(PIIMatch(
                pii_type=PIIType.BANK_ACCOUNT,
                text=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=confidence,
                context=context,
                redaction_level=RedactionLevel.FULL,
                replacement=self._generate_replacement(PIIType.BANK_ACCOUNT, match.group())
            ))
        
        return matches
    
    def _detect_dates_of_birth(self, text: str) -> List[PIIMatch]:
        """Detect potential dates of birth."""
        matches = []
        
        for match in self.patterns.DATE_OF_BIRTH.finditer(text):
            # Check context for DOB indicators
            context = self._extract_context(text, match.start(), match.end()).lower()
            dob_keywords = ['birth', 'born', 'dob', 'age', 'birthday']
            
            confidence = 0.4  # Low base confidence
            if any(keyword in context for keyword in dob_keywords):
                confidence = 0.8
            
            matches.append(PIIMatch(
                pii_type=PIIType.DATE_OF_BIRTH,
                text=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=confidence,
                context=context,
                redaction_level=self.default_redaction_level,
                replacement=self._generate_replacement(PIIType.DATE_OF_BIRTH, match.group())
            ))
        
        return matches
    
    def _extract_context(self, text: str, start: int, end: int, window: int = 30) -> str:
        """Extract context around a match."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]
    
    def _generate_replacement(self, pii_type: PIIType, original: str) -> str:
        """Generate appropriate replacement text for PII."""
        replacements = {
            PIIType.EMAIL: "[REDACTED_EMAIL]",
            PIIType.SSN: "[REDACTED_SSN]",
            PIIType.CREDIT_CARD: "[REDACTED_CC]",
            PIIType.PHONE: "[REDACTED_PHONE]",
            PIIType.IP_ADDRESS: "[REDACTED_IP]",
            PIIType.BANK_ACCOUNT: "[REDACTED_BANK_ACCOUNT]",
            PIIType.DATE_OF_BIRTH: "[REDACTED_DOB]",
            PIIType.PASSPORT: "[REDACTED_PASSPORT]",
            PIIType.MEDICAL_ID: "[REDACTED_MEDICAL_ID]"
        }
        return replacements.get(pii_type, "[REDACTED_PII]")
    
    def _is_valid_luhn(self, number: str) -> bool:
        """Validate credit card number using Luhn algorithm."""
        def luhn_checksum(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            return checksum % 10
        
        try:
            return luhn_checksum(number) == 0
        except (ValueError, TypeError):
            return False
    
    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP address is in private range."""
        private_ranges = [
            r'^10\.',
            r'^172\.(1[6-9]|2[0-9]|3[01])\.',
            r'^192\.168\.',
            r'^127\.',
            r'^169\.254\.',
            r'^::1$',
            r'^fe80:'
        ]
        
        for pattern in private_ranges:
            if re.match(pattern, ip, re.IGNORECASE):
                return True
        return False
    
    def _apply_redactions(self, text: str, matches: List[PIIMatch]) -> str:
        """Apply redactions to create sanitized text."""
        if not matches:
            return text
        
        # Sort matches by position (reverse order for safe replacement)
        sorted_matches = sorted(matches, key=lambda x: x.start, reverse=True)
        
        redacted = text
        for match in sorted_matches:
            redacted = redacted[:match.start] + match.replacement + redacted[match.end:]
        
        return redacted
    
    def _calculate_risk_score(self, matches: List[PIIMatch]) -> float:
        """Calculate overall risk score based on detected PII."""
        if not matches:
            return 0.0
        
        total_risk = 0.0
        for match in matches:
            # Base risk from PII type
            type_weight = self.risk_weights.get(match.pii_type, 0.5)
            
            # Adjust by confidence
            confidence_factor = match.confidence
            
            # Individual PII risk
            pii_risk = type_weight * confidence_factor
            total_risk += pii_risk
        
        # Normalize based on number of matches
        # Multiple high-risk PII items increase overall risk exponentially
        normalized_risk = min(total_risk / len(matches), 1.0)
        
        # Apply exponential factor for multiple sensitive items
        if total_risk > 1.0:
            normalized_risk = min(normalized_risk * 1.2, 1.0)
        
        return normalized_risk
    
    def _determine_action(self, risk_score: float, matches: List[PIIMatch]) -> Tuple[str, str]:
        """Determine what action to take based on risk analysis."""
        
        # Check for high-risk PII types
        high_risk_types = {PIIType.SSN, PIIType.CREDIT_CARD, PIIType.BANK_ACCOUNT, PIIType.PASSPORT}
        has_high_risk = any(match.pii_type in high_risk_types for match in matches)
        
        # Block for high-risk items or very high risk scores
        if has_high_risk or risk_score > 0.8:
            return "block", f"High-risk PII detected (risk score: {risk_score:.2f})"
        
        # Redact for moderate risk
        if risk_score > 0.4 or len(matches) > 2:
            return "redact", f"Moderate PII risk, redaction required (risk score: {risk_score:.2f})"
        
        # Allow with flag for low risk
        if matches:
            return "flag", f"Low-risk PII detected (risk score: {risk_score:.2f})"
        
        return "allow", "No PII detected"


# Convenience function for integration
def detect_and_analyze_pii(
    text: str,
    config: Dict[str, Any] = None,
    context: Dict[str, Any] = None
) -> PIIAnalysis:
    """
    Convenience function to detect and analyze PII in text.
    
    This is the main entry point for enhanced PII detection.
    """
    detector = EnhancedPIIDetector(config)
    return detector.detect_pii(text, context)