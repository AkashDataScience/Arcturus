
import asyncio
import os
import sys

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from voice.intent_gate import IntentRouter, IntentType

class MockOrchestrator:
    def __init__(self):
        self.state = "IDLE"
        self._lock = None
        self._dictation_session = None

    def start_dictation(self):
        print("Mock: Starting dictation")
        self.state = "DICTATING"

    def _should_use_streaming(self):
        return False

    def _nexus_then_speak(self, utterance):
        print(f"Mock: Routing to Nexus: {utterance}")

    def _enter_follow_up(self):
        print("Mock: Entering follow-up")

    def tts(self):
        pass

async def test_classification():
    orch = MockOrchestrator()
    router = IntentRouter(orch)
    
    test_cases = [
        "open the dashboard",
        "start dictation",
        "how is the weather in Bangalore?",
        "summarize my recent emails",
        "write down that I need to buy milk"
    ]
    
    print("\n--- Testing Intent Classification ---\n")
    for utterance in test_cases:
        print(f"Testing: \"{utterance}\"")
        decision = router.route(utterance)
        print(f"Result: {decision.intent_type} (conf={decision.confidence})")
        print(f"Reasoning: {decision.reasoning}\n")

if __name__ == "__main__":
    asyncio.run(test_classification())
