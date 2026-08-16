import json
import urllib.request
import urllib.error
from pathlib import Path

EVAL_FILE = Path(__file__).parent / "cases.json"
ENDPOINT = "http://localhost:8000/enrich"

def run_eval():
    if not EVAL_FILE.exists():
        print(f"Error: {EVAL_FILE} not found.")
        return

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total = len(cases)
    passed = 0
    failures = []

    print(f"Running evaluation on {total} test cases against {ENDPOINT}...\n")

    for case in cases:
        case_id = case["id"]
        payload = json.dumps({"content": case["input"]}).encode("utf-8")
        req = urllib.request.Request(
            ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req) as response:
                status = response.status
                body = json.loads(response.read().decode("utf-8"))

                if status != 200:
                    failures.append({"id": case_id, "reason": f"HTTP status {status}"})
                    continue

                # Retrieve returned category
                pred_category = body.get("category", "").lower().strip()
                exp_category = case["expected_category"].lower().strip()

                if pred_category == exp_category:
                    passed += 1
                    print(f"  [PASS] {case_id} (category='{pred_category}')")
                else:
                    reason = f"Expected category='{exp_category}', got '{pred_category}'"
                    failures.append({"id": case_id, "reason": reason})
                    print(f"  [FAIL] {case_id}: {reason}")

        except Exception as e:
            failures.append({"id": case_id, "reason": f"Exception: {str(e)}"})
            print(f"  [FAIL] {case_id}: Exception - {str(e)}")

    accuracy = (passed / total) * 100
    print("\n" + "=" * 50)
    print(f"EVALUATION SUMMARY: {passed}/{total} passed ({accuracy:.1f}%)")
    print("=" * 50)

    if failures:
        print("\nFailed Cases:")
        for f in failures:
            print(f" - {f['id']}: {f['reason']}")

if __name__ == "__main__":
    run_eval()