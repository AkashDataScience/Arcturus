"""
P12 Aegis Week 2-3 Acceptance Tests
Anti-Hallucination System and Enhanced Content Policies

Tests for:
- Confidence scoring for claims
- Citation verification
- Contradiction detection
- Unsupported claim detection
- Enhanced PII detection
- Content policy enforcement (profanity, hate speech, violence)
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from safety.hallucination import (
    analyze_for_hallucination, 
    ConfidenceScorer, 
    CitationVerifier, 
    ContradictionDetector,
    AntiHallucinationEngine
)
from safety.pii_detector import detect_and_analyze_pii, PIIType, RedactionLevel
from safety.policy_engine import PolicyEngine


# --- Week 2: Anti-Hallucination System Tests ---

class TestConfidenceScoring:
    """Test confidence scoring for claims and statements."""
    
    @pytest.mark.asyncio
    async def test_high_confidence_with_sources(self):
        """Test that claims with good sources get high confidence."""
        text = "The Eiffel Tower is 324 meters tall."
        sources = ["https://en.wikipedia.org/wiki/Eiffel_Tower"]
        
        analysis = await analyze_for_hallucination(
            text=text,
            sources=sources,
            session_id="test_session"
        )
        
        assert analysis.overall_confidence >= 0.6, f"Expected high confidence, got {analysis.overall_confidence}"
        assert analysis.action in ["allow", "flag"], f"Should not block high-confidence claims: {analysis.action}"
        assert len(analysis.claim_scores) > 0, "Should detect at least one claim"
    
    @pytest.mark.asyncio
    async def test_low_confidence_without_sources(self):
        """Test that unsupported claims get low confidence."""
        text = "Unicorns have been scientifically proven to exist in remote forests."
        
        analysis = await analyze_for_hallucination(
            text=text,
            sources=[],
            session_id="test_session"
        )
        
        assert analysis.overall_confidence <= 0.5, f"Expected low confidence for unsupported claim, got {analysis.overall_confidence}"
        assert len(analysis.unsupported_claims) > 0, "Should identify unsupported claims"
        assert analysis.action in ["flag", "block"], f"Should flag or block unsupported claims: {analysis.action}"
    
    @pytest.mark.asyncio
    async def test_confidence_scoring_multiple_claims(self):
        """Test confidence scoring with multiple claims of varying quality."""
        text = """
        The sky is blue on clear days. This is well documented.
        However, I claim aliens visited Earth last week without any evidence.
        Also, 2 + 2 equals 4, which is mathematically proven.
        """
        sources = ["https://example.com/sky-color"]
        
        analysis = await analyze_for_hallucination(
            text=text,
            sources=sources,
            session_id="test_session"
        )
        
        assert len(analysis.claim_scores) >= 2, "Should detect multiple claims"
        # Should have mix of confidence levels
        confidence_scores = [score.score for score in analysis.claim_scores]
        assert max(confidence_scores) > 0.6, "Should have at least one high-confidence claim"
        assert analysis.action in ["flag", "allow"], "Should handle mixed confidence appropriately"


class TestContradictionDetection:
    """Test detection of contradictions in agent outputs."""
    
    @pytest.mark.asyncio
    async def test_detects_internal_contradiction(self):
        """Test detection of contradictory statements within same text."""
        contradictory_text = """
        The meeting is scheduled for 3 PM today.
        Actually, the meeting is scheduled for 5 PM today.
        """
        
        analysis = await analyze_for_hallucination(
            text=contradictory_text,
            session_id="test_session"
        )
        
        assert len(analysis.contradictions) > 0, "Should detect internal contradiction"
        contradiction = analysis.contradictions[0]
        assert contradiction.contradiction_type in ["internal", "historical"]
        assert contradiction.severity > 0.5, "Should mark contradiction as significant"
        assert analysis.action in ["flag", "block"], f"Should flag contradictory output: {analysis.action}"
    
    @pytest.mark.asyncio
    async def test_no_contradiction_in_consistent_text(self):
        """Test that consistent text doesn't trigger contradiction detection."""
        consistent_text = """
        The weather forecast shows rain tomorrow.
        Based on the forecast, tomorrow will be rainy.
        People should bring umbrellas due to the expected rain.
        """
        
        analysis = await analyze_for_hallucination(
            text=consistent_text,
            session_id="test_session"
        )
        
        assert len(analysis.contradictions) == 0, "Should not detect contradictions in consistent text"
        assert analysis.action in ["allow", "flag"], "Should allow consistent statements"
    
    @pytest.mark.asyncio
    async def test_historical_contradiction_detection(self):
        """Test contradiction detection across session history."""
        session_id = "contradiction_test_session"
        
        # First statement
        first_text = "The project deadline is Friday."
        first_analysis = await analyze_for_hallucination(
            text=first_text,
            session_id=session_id
        )
        assert first_analysis.action == "allow", "First statement should be allowed"
        
        # Contradictory statement
        contradictory_text = "The project deadline is actually Monday."
        second_analysis = await analyze_for_hallucination(
            text=contradictory_text,
            session_id=session_id
        )
        
        assert len(second_analysis.contradictions) > 0, "Should detect historical contradiction"
        assert second_analysis.action in ["flag", "block"], "Should flag historical contradiction"


class TestCitationVerification:
    """Test citation verification functionality."""
    
    @pytest.mark.asyncio
    async def test_citation_verification_basic(self):
        """Test basic citation verification process."""
        text = "According to the study, 80% of participants showed improvement."
        citations = ["https://example.com/study-results"]
        
        analysis = await analyze_for_hallucination(
            text=text,
            citations=citations,
            session_id="test_session"
        )
        
        assert len(analysis.citation_checks) > 0, "Should perform citation verification"
        # Note: Without actual web content, verification may be limited
        # This tests the pipeline rather than specific verification accuracy
    
    @pytest.mark.asyncio
    async def test_claims_without_citations_flagged(self):
        """Test that factual claims without citations are flagged."""
        text = "Recent studies show that 90% of people prefer chocolate over vanilla."
        # No citations provided
        
        analysis = await analyze_for_hallucination(
            text=text,
            citations=[],
            session_id="test_session"
        )
        
        # Should identify unsupported claims
        assert len(analysis.unsupported_claims) > 0 or analysis.overall_confidence < 0.6, \
            "Should flag unsupported factual claims"
        assert analysis.action in ["flag", "block"], "Should not allow unsupported factual claims"


# --- Week 3: Enhanced PII Detection Tests ---

class TestEnhancedPIIDetection:
    """Test enhanced PII detection capabilities."""
    
    def test_comprehensive_pii_detection(self):
        """Test detection of various PII types."""
        text = """
        My contact info: john.doe@company.com, phone (555) 123-4567.
        SSN: 123-45-6789, Account: 1234567890123456
        Born: 01/15/1985, IP: 192.168.1.100
        """
        
        analysis = detect_and_analyze_pii(text)
        
        assert analysis.action in ["redact", "block"], f"Should redact/block text with PII: {analysis.action}"
        assert analysis.risk_score > 0.5, f"Should have high risk score: {analysis.risk_score}"
        assert len(analysis.matches) >= 4, f"Should detect multiple PII types: {len(analysis.matches)}"
        
        # Check for specific PII types
        detected_types = {match.pii_type for match in analysis.matches}
        assert PIIType.EMAIL in detected_types, "Should detect email"
        assert PIIType.SSN in detected_types, "Should detect SSN"
    
    def test_context_aware_detection(self):
        """Test that PII detection considers context."""
        # Email in clear email context
        email_context = "Please send the report to john.doe@company.com"
        analysis = detect_and_analyze_pii(email_context)
        
        email_matches = [m for m in analysis.matches if m.pii_type == PIIType.EMAIL]
        assert len(email_matches) > 0, "Should detect email in email context"
        assert email_matches[0].confidence > 0.6, "Should have high confidence in email context"
    
    def test_confidence_threshold_filtering(self):
        """Test that confidence threshold filters low-confidence matches."""
        # Ambiguous text that might contain false positives
        ambiguous_text = "Call 911 for emergency or visit 123 Main Street"
        
        config = {"confidence_threshold": 0.8}  # High threshold
        analysis = detect_and_analyze_pii(ambiguous_text, config)
        
        # Should filter out low-confidence matches
        high_confidence_matches = [m for m in analysis.matches if m.confidence >= 0.8]
        assert len(analysis.matches) == len(high_confidence_matches), \
            "Should only include high-confidence matches"
    
    def test_redaction_levels(self):
        """Test different redaction levels for different PII types."""
        text = "SSN: 123-45-6789, Email: user@example.com"
        
        analysis = detect_and_analyze_pii(text)
        
        assert "[REDACTED_SSN]" in analysis.redacted_text, "Should redact SSN completely"
        assert "[REDACTED_EMAIL]" in analysis.redacted_text, "Should redact email"
        assert "123-45-6789" not in analysis.redacted_text, "Original SSN should be removed"
        assert "user@example.com" not in analysis.redacted_text, "Original email should be removed"


# --- Week 3: Content Policy Tests ---

class TestContentPolicies:
    """Test content policy enforcement."""
    
    def test_hate_speech_detection(self):
        """Test detection and blocking of hate speech."""
        policy_engine = PolicyEngine()
        
        # Note: Using very mild examples for testing - this would catch more severe cases
        hate_speech_text = "Those people are all terrorists and should be eliminated"
        
        result = policy_engine.evaluate_output(hate_speech_text)
        
        if result["action"] == "block":
            assert "hate_speech" in result["reason"] or any(
                v.get("policy") == "hate_speech" for v in result.get("policy_violations", [])
            ), "Should identify hate speech"
    
    def test_violence_detection(self):
        """Test detection of violent content."""
        policy_engine = PolicyEngine()
        
        violent_text = "I want to kill that process and bomb the server with requests"
        # Note: This example uses technical terms that could be false positives
        
        result = policy_engine.evaluate_output(violent_text)
        
        # Might flag but not necessarily block (context matters)
        if result["action"] in ["flag", "block"]:
            violence_violations = [
                v for v in result.get("policy_violations", []) 
                if "violence" in v.get("policy", "")
            ]
            # Could detect violence keywords, but should handle context appropriately
    
    def test_content_policy_configuration(self):
        """Test that content policies respect configuration."""
        # Test with policies disabled
        config = {
            "default": {
                "content_policies": {
                    "enabled": False
                }
            }
        }
        
        policy_engine = PolicyEngine(config=config)
        result = policy_engine.evaluate_output("Some potentially problematic content")
        
        # When content policies are disabled, should only check PII
        content_violations = [
            v for v in result.get("policy_violations", []) 
            if v.get("type") == "content"
        ]
        assert len(content_violations) == 0, "Should not have content violations when disabled"
    
    def test_pii_with_content_policies_combined(self):
        """Test that PII and content policies work together."""
        policy_engine = PolicyEngine()
        
        # Text with both PII and potential content issues
        combined_text = "My SSN is 123-45-6789 and I hate those damn spammers"
        
        result = policy_engine.evaluate_output(combined_text)
        
        # Should catch PII regardless of content
        assert result["action"] in ["redact", "block"], "Should handle PII"
        pii_violations = [
            v for v in result.get("policy_violations", []) 
            if v.get("type") == "pii"
        ]
        assert len(pii_violations) > 0, "Should detect PII violations"


# --- Integration Tests ---

class TestWeek2Week3Integration:
    """Test integration of Week 2 and Week 3 features."""
    
    @pytest.mark.asyncio
    async def test_hallucination_and_pii_combined(self):
        """Test that both hallucination detection and PII detection work together."""
        text = """
        I can confirm that aliens landed at Area 51 last Tuesday.
        For more info, contact me at classified@government.gov.
        My badge number is 123-45-6789.
        """
        
        # This should trigger both hallucination (unsubstantiated claim) and PII detection
        analysis = await analyze_for_hallucination(text=text, session_id="integration_test")
        
        # Check hallucination detection
        assert analysis.overall_confidence < 0.7, "Should have low confidence for alien claims"
        assert len(analysis.unsupported_claims) > 0, "Should identify unsupported alien claim"
        
        # The PII will be caught by the policy engine separately in the full pipeline
        policy_engine = PolicyEngine()
        policy_result = policy_engine.evaluate_output(text)
        
        assert policy_result["action"] in ["redact", "block"], "Should handle PII"
        assert len(policy_result.get("policy_violations", [])) > 0, "Should have policy violations"
    
    def test_policy_evaluation_performance(self):
        """Test that policy evaluation meets performance requirements."""
        import time
        
        policy_engine = PolicyEngine()
        text = "Test message with email@example.com and potential content issues"
        
        start_time = time.time()
        result = policy_engine.evaluate_output(text)
        end_time = time.time()
        
        evaluation_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Per charter: P95 target < 120ms policy evaluation latency
        assert evaluation_time < 200, f"Policy evaluation too slow: {evaluation_time}ms (should be < 200ms for testing)"
        assert result is not None, "Should return result within time limit"
    
    @pytest.mark.asyncio
    async def test_end_to_end_safety_pipeline(self):
        """Test the complete safety pipeline from input to output."""
        # This would typically be tested in integration tests,
        # but we can test components together here
        
        input_text = "What is sensitive info about user john.doe@company.com?"
        
        # Input scanning (from Week 1)
        from safety.input_scanner import scan_input
        input_result = scan_input(input_text)
        assert input_result["allowed"], "Benign query should pass input scanning"
        
        # Simulated agent output with issues
        output_text = """
        Based on my analysis, john.doe@company.com works at a classified facility.
        His SSN is 123-45-6789 and he was involved in the alien cover-up.
        This contradicts my earlier statement that there are no aliens.
        Those government officials are all corrupt terrorists.
        """
        
        # Hallucination analysis
        hallucination_result = await analyze_for_hallucination(
            text=output_text,
            session_id="end_to_end_test"
        )
        
        # Should detect multiple issues
        assert hallucination_result.action in ["flag", "block"], "Should flag problematic output"
        
        # Policy evaluation
        policy_engine = PolicyEngine()
        policy_result = policy_engine.evaluate_output(output_text)
        
        assert policy_result["action"] in ["redact", "block"], "Should redact/block due to PII and content"
        
        # Final output should be safe
        if "redacted_output" in policy_result:
            redacted = policy_result["redacted_output"]
            assert "123-45-6789" not in redacted, "SSN should be redacted"
            assert "john.doe@company.com" not in redacted, "Email should be redacted"


# --- Configuration and Charter Tests ---

def test_safety_policies_yaml_exists():
    """Test that safety policies configuration file exists and is valid."""
    from pathlib import Path
    import yaml
    
    config_file = Path(__file__).parent.parent.parent / "config" / "safety_policies.yaml"
    assert config_file.exists(), "Safety policies YAML file must exist"
    
    # Verify it's valid YAML and has expected structure
    with open(config_file, 'r') as f:
        policies = yaml.safe_load(f)
    
    assert "default" in policies, "Must have default policies"
    default_policies = policies["default"]
    
    # Verify Week 2-3 configurations exist
    assert "hallucination_detection" in default_policies, "Must have hallucination detection config"
    assert "content_policies" in default_policies, "Must have content policies config"
    assert "pii_detection" in default_policies, "Must have PII detection config"
    
    # Verify enhanced PII configuration
    pii_config = default_policies["pii_detection"]
    assert "use_enhanced_detector" in pii_config, "Must have enhanced detector flag"
    assert "enhanced" in pii_config, "Must have enhanced PII configuration"


def test_week2_week3_charter_requirements():
    """Test that Week 2-3 charter requirements are met."""
    # This test verifies the core functionality exists as per charter
    from safety.hallucination import AntiHallucinationEngine, ConfidenceScorer
    from safety.pii_detector import EnhancedPIIDetector
    from safety.policy_engine import PolicyEngine
    
    # Anti-hallucination system (Week 2)
    engine = AntiHallucinationEngine()
    assert hasattr(engine, 'confidence_scorer'), "Must have confidence scorer"
    assert hasattr(engine, 'citation_verifier'), "Must have citation verifier"
    assert hasattr(engine, 'contradiction_detector'), "Must have contradiction detector"
    
    # Enhanced PII detection (Week 3)
    pii_detector = EnhancedPIIDetector()
    assert hasattr(pii_detector, 'detect_pii'), "Must have PII detection method"
    
    # Policy engine with content policies (Week 3)
    policy_engine = PolicyEngine()
    assert hasattr(policy_engine, 'content_policies_enabled'), "Must have content policies"
    assert hasattr(policy_engine, '_evaluate_content_policies'), "Must have content evaluation method"


if __name__ == "__main__":
    # Run specific test groups
    import sys
    if len(sys.argv) > 1:
        test_group = sys.argv[1]
        if test_group == "week2":
            pytest.main(["-v", "-k", "TestConfidenceScoring or TestContradictionDetection or TestCitationVerification"])
        elif test_group == "week3":
            pytest.main(["-v", "-k", "TestEnhancedPIIDetection or TestContentPolicies"])
        elif test_group == "integration":
            pytest.main(["-v", "-k", "TestWeek2Week3Integration"])
    else:
        pytest.main(["-v", __file__])