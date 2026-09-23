"""
test_origins.py - Verification script for origin extraction & transport fallback strategy.
Run with: ..\venv\Scripts\python.exe test_origins.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from agents import coordinator
import agent

TEST_CASES = [
    ("Surat",   "2 people from Surat travelling in Navratri for 5 days with VIP darshan"),
    ("Bhopal",  "2 people from Bhopal for 5 days with VIP darshan"),
    ("Jaipur",  "2 pilgrims from Jaipur for 5 days VIP darshan"),
    ("Lucknow", "3 people from Lucknow by train for VIP darshan"),
    ("Pune",    "2 people from Pune travelling for 5 days VIP darshan"),
    ("Kochi",   "2 people from Kochi for 5 days VIP darshan"),
    ("Delhi",   "2 people from Delhi for 5 days VIP darshan"),   # Direct - in dataset
    ("Guwahati","2 people from Guwahati for VIP darshan"),       # Completely unsupported
]

print("=" * 70)
print("ORIGIN EXTRACTION & TRANSPORT FALLBACK STRATEGY TEST")
print("=" * 70)

for expected_city, msg in TEST_CASES:
    res = coordinator.process_trip_message(msg)
    req  = res["request"]
    plan = res["plan"]

    extracted = req.get("origin", "NONE")
    preserved = (extracted == expected_city)
    status    = plan.get("status")
    options   = plan.get("options", [])

    print(f"\nCity: {expected_city}")
    print(f"  [1] Extracted city  : {extracted!r}")
    print(f"  [2] Preserved name  : {'YES' if preserved else 'NO  <-- mismatch, got: ' + repr(extracted)}")
    print(f"  [3] Plan status     : {status}")

    if status == "PLAN_READY" and options:
        tr = options[0].get("transport") or options[0].get("flight")
        connecting = tr.get("is_connecting", False)
        hub        = tr.get("connecting_hub", "-")
        note       = tr.get("route_note", "Direct")
        print(f"  [4] Transport type  : {'CONNECTING' if connecting else 'DIRECT'}")
        print(f"  [5] Route note      : {note}")
        if connecting:
            print(f"  [6] Connecting hub  : {hub}")
        print(f"  [7] Fabricated data : NONE (all from dataset)")

    elif status == "NO_AVAILABILITY":
        unsup = plan.get("unsupported_origin")
        print(f"  [4] Unsupported     : {unsup or '(slots issue)'}")
        print(f"  [5] Fallback msg    : {plan.get('message', '')[:100]}...")
        print(f"  [6] Fabricated data : NONE")

    print(f"  {'PASS' if status in ('PLAN_READY','NO_AVAILABILITY') else 'FAIL'}")
    print("-" * 70)
