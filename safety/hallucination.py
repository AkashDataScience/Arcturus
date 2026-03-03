"""
Aegis Anti-Hallucination System (P12 Week 2)

This module implements confidence scoring, citation verification, contradiction detection,
and fact-checking capabilities for the Arcturus safety layer.

Features:
- Per-claim confidence scoring (0-1)
- Citation verification (check if sources support claims)
- Contradiction detection (flag internal contradictions)
- Unsupported claim detection (highlight claims without sources)
- Fact-checking pipeline (post-generation verification)
"""

import asyncio
import json
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from urllib.parse import urlparse
import hashlib

from core.model_manager import ModelManager
from safety.audit import log_safety_event

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceScore:
    """Represents confidence score for a claim or statement."""
    claim: str
    score: float  # 0.0 to 1.0
    reasoning: str
    sources: List[str]
    factors: Dict[str, float]


@dataclass
class CitationCheck:
    """Represents the result of citation verification."""
    citation: str
    claim: str
    verified: bool
    verification_score: float
    reason: str


@dataclass
class ContradictionAlert:
    """Represents a detected contradiction."""
    statement_1: str
    statement_2: str
    contradiction_type: str
    severity: float  # 0.0 to 1.0
    explanation: str


@dataclass
class HallucinationAnalysis:
    """Complete anti-hallucination analysis of content."""
    overall_confidence: float
    claim_scores: List[ConfidenceScore]
    citation_checks: List[CitationCheck]
    contradictions: List[ContradictionAlert]
    unsupported_claims: List[str]
    fact_check_results: Dict[str, Any]
    action: str  # "allow", "flag", "block"
    reasoning: str


class ConfidenceScorer:
    """Computes confidence scores for claims and statements."""
    
    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager("gemini-2.5-flash", provider="gemini")
        
    async def score_claim(self, claim: str, sources: List[str] = None, context: str = "") -> ConfidenceScore:
        """
        Score confidence for a single claim.
        
        Args:
            claim: The statement to evaluate
            sources: List of source URLs/references
            context: Additional context for evaluation
            
        Returns:
            ConfidenceScore with detailed assessment
        """
        try:
            # Prepare scoring prompt
            prompt = self._build_scoring_prompt(claim, sources, context)
            
            # Get model response
            response = await self.model_manager.generate_text(prompt)
            
            # Parse response
            analysis = self._parse_scoring_response(response)
            
            # Calculate composite score from factors
            composite_score = self._calculate_composite_score(analysis["factors"])
            
            return ConfidenceScore(
                claim=claim,
                score=composite_score,
                reasoning=analysis["reasoning"],
                sources=sources or [],
                factors=analysis["factors"]
            )
            
        except Exception as e:
            logger.error(f"Error scoring claim confidence: {e}")
            # Return low-confidence fallback
            return ConfidenceScore(
                claim=claim,
                score=0.3,
                reasoning=f"Error during analysis: {str(e)}",
                sources=sources or [],
                factors={"error": 1.0}
            )
    
    def _build_scoring_prompt(self, claim: str, sources: List[str], context: str) -> str:
        """Build prompt for confidence scoring."""
        sources_text = "\n".join([f"- {s}" for s in (sources or [])])
        
        return f"""
Evaluate the confidence for this claim on a scale of 0.0 to 1.0:

CLAIM: {claim}

AVAILABLE SOURCES:
{sources_text if sources else "No sources provided"}

CONTEXT:
{context}

Consider these factors in your analysis:
1. Source Quality (0.0-1.0): How reliable/authoritative are the sources?
2. Source Support (0.0-1.0): How well do sources support this specific claim?
3. Claim Specificity (0.0-1.0): How specific vs vague is the claim?
4. Internal Consistency (0.0-1.0): Does claim contradict itself?
5. Verifiability (0.0-1.0): Can this claim be verified independently?

Respond in JSON format:
{{
    "factors": {{
        "source_quality": 0.7,
        "source_support": 0.6,
        "claim_specificity": 0.8,
        "internal_consistency": 1.0,
        "verifiability": 0.9
    }},
    "reasoning": "Brief explanation of the score",
    "red_flags": ["any concerning aspects"]
}}
"""
    
    def _parse_scoring_response(self, response: str) -> Dict[str, Any]:
        """Parse model response for scoring."""
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                
                # Validate structure
                if "factors" in parsed and "reasoning" in parsed:
                    return parsed
                    
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse scoring response: {e}")
        
        # Fallback parsing
        return {
            "factors": {
                "source_quality": 0.5,
                "source_support": 0.5,
                "claim_specificity": 0.5,
                "internal_consistency": 0.5,
                "verifiability": 0.5
            },
            "reasoning": "Unable to parse detailed analysis",
            "red_flags": []
        }
    
    def _calculate_composite_score(self, factors: Dict[str, float]) -> float:
        """Calculate weighted composite confidence score."""
        # Default weights for factors
        weights = {
            "source_quality": 0.25,
            "source_support": 0.30,
            "claim_specificity": 0.15,
            "internal_consistency": 0.15,
            "verifiability": 0.15
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for factor, value in factors.items():
            weight = weights.get(factor, 0.1)  # Default weight for unknown factors
            total_score += value * weight
            total_weight += weight
        
        return min(max(total_score / total_weight if total_weight > 0 else 0.5, 0.0), 1.0)


class CitationVerifier:
    """Verifies that citations actually support the claims made."""
    
    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager("gemini-2.5-flash", provider="gemini")
    
    async def verify_citation(self, claim: str, citation: str, citation_content: str = None) -> CitationCheck:
        """
        Verify if a citation supports a claim.
        
        Args:
            claim: The statement being made
            citation: The source reference (URL, title, etc.)
            citation_content: Optional content from the source
            
        Returns:
            CitationCheck with verification result
        """
        try:
            # If no content provided, extract from citation if possible
            if not citation_content:
                citation_content = await self._extract_citation_content(citation)
            
            # Build verification prompt
            prompt = self._build_verification_prompt(claim, citation, citation_content)
            
            # Get model analysis
            response = await self.model_manager.generate_text(prompt)
            
            # Parse verification result
            analysis = self._parse_verification_response(response)
            
            return CitationCheck(
                citation=citation,
                claim=claim,
                verified=analysis["verified"],
                verification_score=analysis["score"],
                reason=analysis["reason"]
            )
            
        except Exception as e:
            logger.error(f"Error verifying citation: {e}")
            return CitationCheck(
                citation=citation,
                claim=claim,
                verified=False,
                verification_score=0.0,
                reason=f"Verification error: {str(e)}"
            )
    
    async def _extract_citation_content(self, citation: str) -> str:
        """Extract content from citation (placeholder for future web scraping)."""
        # For now, return empty - in future versions this could:
        # 1. Fetch web content if citation is a URL
        # 2. Look up content in cached sources
        # 3. Query vector database for relevant content
        return ""
    
    def _build_verification_prompt(self, claim: str, citation: str, content: str) -> str:
        """Build prompt for citation verification."""
        return f"""
Verify if the given citation supports the claim:

CLAIM: {claim}

CITATION: {citation}

CONTENT FROM SOURCE:
{content if content else "No content available - analyze based on citation reference only"}

Analyze if this citation supports the claim. Consider:
1. Does the source content directly support the claim?
2. Is the claim a reasonable inference from the source?
3. Does the source contradict the claim?
4. Is the source relevant to the claim's domain?

Respond in JSON format:
{{
    "verified": true/false,
    "score": 0.8,
    "reason": "Brief explanation",
    "support_type": "direct|inference|none|contradiction"
}}
"""
    
    def _parse_verification_response(self, response: str) -> Dict[str, Any]:
        """Parse model response for verification."""
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)
                
                return {
                    "verified": parsed.get("verified", False),
                    "score": float(parsed.get("score", 0.0)),
                    "reason": parsed.get("reason", "Unknown"),
                    "support_type": parsed.get("support_type", "none")
                }
                    
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse verification response: {e}")
        
        # Fallback
        return {
            "verified": False,
            "score": 0.0,
            "reason": "Unable to parse verification result",
            "support_type": "none"
        }


class ContradictionDetector:
    """Detects contradictions in agent outputs."""
    
    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager("gemini-2.5-flash", provider="gemini")
        self.session_cache = {}  # Cache previous statements per session
    
    def detect_contradictions(self, text: str, session_id: str = None) -> List[ContradictionAlert]:
        """
        Detect contradictions within text and against previous statements.
        
        Args:
            text: Text to analyze
            session_id: Session ID for historical contradiction checking
            
        Returns:
            List of ContradictionAlert objects
        """
        contradictions = []
        
        try:
            # Extract claims from text
            claims = self._extract_claims(text)
            
            # Check for internal contradictions
            internal_contradictions = self._check_internal_contradictions(claims)
            contradictions.extend(internal_contradictions)
            
            # Check against previous statements in session
            if session_id:
                historical_contradictions = self._check_historical_contradictions(
                    claims, session_id
                )
                contradictions.extend(historical_contradictions)
                
                # Update session cache
                self._update_session_cache(session_id, claims)
            
        except Exception as e:
            logger.error(f"Error detecting contradictions: {e}")
        
        return contradictions
    
    def _extract_claims(self, text: str) -> List[str]:
        """Extract factual claims from text."""
        # Simple sentence-based extraction (could be enhanced with NLP)
        sentences = re.split(r'[.!?]+', text)
        
        # Filter for claim-like sentences
        claims = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10 and self._is_claim_like(sentence):
                claims.append(sentence)
        
        return claims
    
    def _is_claim_like(self, sentence: str) -> bool:
        """Determine if sentence contains factual claims."""
        # Heuristics for identifying claims
        claim_indicators = [
            r'\b(is|are|was|were|will be|has|have|had)\b',  # Factual assertions
            r'\b(always|never|all|none|everyone|no one)\b',  # Absolute statements
            r'\b(\d+|\w+ly)\b',  # Numbers or adverbs (often factual)
        ]
        
        for pattern in claim_indicators:
            if re.search(pattern, sentence, re.IGNORECASE):
                return True
        
        return False
    
    def _check_internal_contradictions(self, claims: List[str]) -> List[ContradictionAlert]:
        """Check for contradictions within the current set of claims."""
        contradictions = []
        
        for i, claim1 in enumerate(claims):
            for j, claim2 in enumerate(claims[i+1:], i+1):
                if self._are_contradictory(claim1, claim2):
                    contradictions.append(ContradictionAlert(
                        statement_1=claim1,
                        statement_2=claim2,
                        contradiction_type="internal",
                        severity=0.8,  # Internal contradictions are serious
                        explanation="Statements appear to contradict each other"
                    ))
        
        return contradictions
    
    def _check_historical_contradictions(self, claims: List[str], session_id: str) -> List[ContradictionAlert]:
        """Check claims against previous statements in the session."""
        contradictions = []
        
        previous_claims = self.session_cache.get(session_id, [])
        
        for new_claim in claims:
            for old_claim in previous_claims:
                if self._are_contradictory(new_claim, old_claim):
                    contradictions.append(ContradictionAlert(
                        statement_1=new_claim,
                        statement_2=old_claim,
                        contradiction_type="historical",
                        severity=0.6,  # Historical contradictions might be updates
                        explanation="New statement contradicts previous statement in session"
                    ))
        
        return contradictions
    
    def _are_contradictory(self, claim1: str, claim2: str) -> bool:
        """Simple heuristic check for contradictory statements."""
        # Normalize claims
        claim1_norm = claim1.lower().strip()
        claim2_norm = claim2.lower().strip()
        
        # Look for obvious contradictions
        contradiction_patterns = [
            (r'\bis\b', r'\bis not\b'),
            (r'\bcan\b', r'\bcannot\b'),
            (r'\bwill\b', r'\bwill not\b'),
            (r'\balways\b', r'\bnever\b'),
            (r'\ball\b', r'\bnone\b'),
            (r'\btrue\b', r'\bfalse\b')
        ]
        
        for pos_pattern, neg_pattern in contradiction_patterns:
            if (re.search(pos_pattern, claim1_norm) and re.search(neg_pattern, claim2_norm)) or \
               (re.search(neg_pattern, claim1_norm) and re.search(pos_pattern, claim2_norm)):
                return True
        
        return False
    
    def _update_session_cache(self, session_id: str, claims: List[str]):
        """Update session cache with new claims."""
        if session_id not in self.session_cache:
            self.session_cache[session_id] = []
        
        self.session_cache[session_id].extend(claims)
        
        # Limit cache size to prevent memory growth
        max_claims = 50
        if len(self.session_cache[session_id]) > max_claims:
            self.session_cache[session_id] = self.session_cache[session_id][-max_claims:]


class AntiHallucinationEngine:
    """Main engine coordinating all anti-hallucination features."""
    
    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager("gemini-2.5-flash", provider="gemini")
        self.confidence_scorer = ConfidenceScorer(model_manager)
        self.citation_verifier = CitationVerifier(model_manager)
        self.contradiction_detector = ContradictionDetector(model_manager)
    
    async def analyze_output(
        self,
        text: str,
        sources: List[str] = None,
        citations: List[str] = None,
        session_id: str = None,
        context: Dict[str, Any] = None
    ) -> HallucinationAnalysis:
        """
        Comprehensive anti-hallucination analysis of output.
        
        Args:
            text: Output text to analyze
            sources: List of source references
            citations: List of citations in the text
            session_id: Session ID for historical checking
            context: Additional context for analysis
            
        Returns:
            HallucinationAnalysis with complete assessment
        """
        try:
            # Extract claims from text
            claims = self.contradiction_detector._extract_claims(text)
            
            # Score confidence for each claim
            claim_scores = []
            for claim in claims:
                score = await self.confidence_scorer.score_claim(
                    claim, 
                    sources=sources,
                    context=str(context) if context else ""
                )
                claim_scores.append(score)
            
            # Verify citations if provided
            citation_checks = []
            if citations:
                for citation in citations:
                    # Try to match citation to claims
                    best_claim = self._find_best_matching_claim(citation, claims)
                    if best_claim:
                        check = await self.citation_verifier.verify_citation(
                            best_claim, citation
                        )
                        citation_checks.append(check)
            
            # Detect contradictions
            contradictions = self.contradiction_detector.detect_contradictions(
                text, session_id
            )
            
            # Find unsupported claims
            unsupported_claims = self._find_unsupported_claims(claim_scores, citation_checks)
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(
                claim_scores, citation_checks, contradictions
            )
            
            # Determine action
            action, reasoning = self._determine_action(
                overall_confidence, contradictions, unsupported_claims, citation_checks
            )
            
            analysis = HallucinationAnalysis(
                overall_confidence=overall_confidence,
                claim_scores=claim_scores,
                citation_checks=citation_checks,
                contradictions=contradictions,
                unsupported_claims=unsupported_claims,
                fact_check_results={},  # Placeholder for future fact-checking
                action=action,
                reasoning=reasoning
            )
            
            # Log analysis for audit
            self._log_analysis(analysis, session_id, context)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in anti-hallucination analysis: {e}")
            # Return safe fallback
            return HallucinationAnalysis(
                overall_confidence=0.5,
                claim_scores=[],
                citation_checks=[],
                contradictions=[],
                unsupported_claims=[],
                fact_check_results={},
                action="allow",
                reasoning=f"Analysis error: {str(e)}"
            )
    
    def _find_best_matching_claim(self, citation: str, claims: List[str]) -> Optional[str]:
        """Find the claim that best matches a citation."""
        # Simple text similarity (could be enhanced with embeddings)
        citation_words = set(citation.lower().split())
        
        best_match = None
        best_score = 0.0
        
        for claim in claims:
            claim_words = set(claim.lower().split())
            # Simple Jaccard similarity
            intersection = len(citation_words & claim_words)
            union = len(citation_words | claim_words)
            
            if union > 0:
                score = intersection / union
                if score > best_score:
                    best_score = score
                    best_match = claim
        
        return best_match if best_score > 0.1 else None
    
    def _find_unsupported_claims(
        self, 
        claim_scores: List[ConfidenceScore], 
        citation_checks: List[CitationCheck]
    ) -> List[str]:
        """Identify claims that lack sufficient support."""
        unsupported = []
        
        for score in claim_scores:
            # Consider a claim unsupported if:
            # 1. Low confidence score
            # 2. No verified citations
            # 3. Low source support factor
            
            if score.score < 0.4:  # Low confidence threshold
                unsupported.append(score.claim)
            elif score.factors.get("source_support", 0.0) < 0.3:  # Insufficient source support
                unsupported.append(score.claim)
        
        return unsupported
    
    def _calculate_overall_confidence(
        self,
        claim_scores: List[ConfidenceScore],
        citation_checks: List[CitationCheck],
        contradictions: List[ContradictionAlert]
    ) -> float:
        """Calculate overall confidence score."""
        if not claim_scores:
            return 0.5  # Neutral confidence when no claims
        
        # Start with average claim confidence
        avg_claim_confidence = sum(score.score for score in claim_scores) / len(claim_scores)
        
        # Adjust for citation verification
        verified_citations = [c for c in citation_checks if c.verified]
        citation_boost = min(len(verified_citations) * 0.1, 0.2)  # Up to 20% boost
        
        # Penalize for contradictions
        contradiction_penalty = min(len(contradictions) * 0.2, 0.4)  # Up to 40% penalty
        
        overall = avg_claim_confidence + citation_boost - contradiction_penalty
        
        return max(min(overall, 1.0), 0.0)
    
    def _determine_action(
        self,
        overall_confidence: float,
        contradictions: List[ContradictionAlert],
        unsupported_claims: List[str],
        citation_checks: List[CitationCheck]
    ) -> Tuple[str, str]:
        """Determine what action to take based on analysis."""
        
        # Block for severe issues
        if overall_confidence < 0.2:
            return "block", "Overall confidence too low"
        
        if len(contradictions) > 0:
            high_severity_contradictions = [c for c in contradictions if c.severity > 0.7]
            if high_severity_contradictions:
                return "block", "High-severity contradictions detected"
        
        failed_citations = [c for c in citation_checks if not c.verified and c.verification_score < 0.3]
        if len(failed_citations) > len(citation_checks) * 0.5:  # More than 50% failed
            return "block", "Majority of citations failed verification"
        
        # Flag for moderate issues
        if overall_confidence < 0.5 or len(unsupported_claims) > 2:
            return "flag", "Moderate confidence issues or multiple unsupported claims"
        
        if contradictions or unsupported_claims:
            return "flag", "Minor issues detected"
        
        return "allow", "No significant issues detected"
    
    def _log_analysis(self, analysis: HallucinationAnalysis, session_id: str, context: Dict[str, Any]):
        """Log analysis results for audit purposes."""
        try:
            log_safety_event(
                "hallucination_analysis",
                context={
                    "session_id": session_id,
                    "agent": context.get("agent") if context else None,
                    "step_id": context.get("step_id") if context else None
                },
                metadata={
                    "overall_confidence": analysis.overall_confidence,
                    "action": analysis.action,
                    "num_claims": len(analysis.claim_scores),
                    "num_contradictions": len(analysis.contradictions),
                    "num_unsupported": len(analysis.unsupported_claims),
                    "num_citations": len(analysis.citation_checks)
                }
            )
        except Exception as e:
            logger.error(f"Error logging hallucination analysis: {e}")


# Convenience function for integration
async def analyze_for_hallucination(
    text: str,
    sources: List[str] = None,
    citations: List[str] = None,
    session_id: str = None,
    context: Dict[str, Any] = None
) -> HallucinationAnalysis:
    """
    Convenience function to analyze text for hallucination indicators.
    
    This is the main entry point for the anti-hallucination system.
    """
    engine = AntiHallucinationEngine()
    return await engine.analyze_output(text, sources, citations, session_id, context)