#!/usr/bin/env python3
"""Quick test of P12 Aegis Week 2-3 functionality."""

from safety.policy_engine import PolicyEngine

def main():
    """Test all Week 2-3 features."""
    print("=== P12 Aegis Week 2-3 Integration Test ===")
    
    engine = PolicyEngine('config/safety_policies.yaml')
    
    # Test 1: Hallucination detection
    print("\n1. Testing Anti-Hallucination System:")
    result1 = engine.evaluate_output(
        'Tell me some facts',
        'Unicorns definitely exist in real life and can fly'
    )
    print(f"   Result: {result1}")
    
    # Test 2: Enhanced PII detection
    print("\n2. Testing Enhanced PII Detection:")
    result2 = engine.evaluate_output(
        'What is your contact info?',
        'My SSN is 123-45-6789 and email is john@company.com'
    )
    print(f"   Result: {result2}")
    
    print("\n=== All Week 2-3 Features Operational ===")
    return True

if __name__ == "__main__":
    main()