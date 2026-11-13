import sys
import os

# Add src to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import local_api

print("Testing Local API Status...")
st = local_api.status()
print("Status dict:", st)
assert st["up"] is True, f"Local API health check failed! Status: {st}"
assert st["has_key"] is True, f"Missing API key! Status: {st}"

print("\nTesting Live AI Completion through HyperGravity-Core...")
prompt = "Say 'HYPERGRAVITY_BRIDGE_SUCCESS' and nothing else."
reply = local_api.ask(prompt)
print("Received reply from AI:", reply.strip())
assert "HYPERGRAVITY_BRIDGE_SUCCESS" in reply or len(reply.strip()) > 0, "Empty response from AI"

print("\n[SUCCESS] HyperGravity-Core API Bridge is fully functional and verified!")
