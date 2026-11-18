import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from analyzer import analyze


sys.stdout.reconfigure(encoding="utf-8")

CACHE_PATH = Path("eval_cache.json")
RESULT_COLUMNS = [
    "message",
    "correct_verdict",
    "correct_type",
    "predicted_verdict",
    "predicted_type",
    "confidence",
    "reason",
    "model_used",
    "status",
]


def percent(correct, total):
    if total == 0:
        return 0.0
    return correct * 100.0 / total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    if args.fresh:
        CACHE_PATH.unlink(missing_ok=True)
        cache = {}
    elif CACHE_PATH.exists():
        with CACHE_PATH.open("r", encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
        if not isinstance(cache, dict):
            raise ValueError("eval_cache.json must contain a JSON object.")
        cache = {
            message: result
            for message, result in cache.items()
            if isinstance(message, str)
            and isinstance(result, dict)
            and "error" not in result
        }
    else:
        cache = {}

    data = pd.read_csv("test_data.csv", encoding="utf-8-sig")
    if args.limit is not None:
        data = data.head(max(args.limit, 0))

    results = []
    api_error_count = 0
    total = len(data)
    consecutive_errors = 0
    last_was_api_call = False

    for position, (_, row) in enumerate(data.iterrows(), start=1):
        message = str(row["message"])
        cached = message in cache
        print(f"[{position}/{total}]" + (" cached" if cached else ""))
        if cached:
            result = cache[message]
            consecutive_errors = 0
        else:
            if last_was_api_call:
                time.sleep(4)
            result = analyze(text=message)
            last_was_api_call = True

        if "error" in result:
            api_error_count += 1
            consecutive_errors += 1
            status = "api_error"
        else:
            consecutive_errors = 0
            status = "evaluated"
            if not cached:
                cache[message] = result
                with CACHE_PATH.open("w", encoding="utf-8") as cache_file:
                    json.dump(cache, cache_file, ensure_ascii=False, indent=2)

        predicted_verdict = result.get("verdict", "suspicious")
        predicted_type = result.get("scam_type", "none")
        confidence = result.get("confidence", "low")
        reason = result.get("reason", "")
        model_used = result.get("model_used", "")

        results.append({
            "message": message,
            "correct_verdict": row["correct_verdict"],
            "correct_type": row["correct_type"],
            "predicted_verdict": predicted_verdict,
            "predicted_type": predicted_type,
            "confidence": confidence,
            "reason": reason,
            "model_used": model_used,
            "status": status,
        })

        if consecutive_errors >= 3:
            completed = len(results)
            print(
                "তিনটি সারিতে পরপর API ত্রুটি হয়েছে। "
                f"এখন পর্যন্ত {completed}টি সারি সম্পন্ন হয়েছে।"
            )
            print(
                "Stopping early after 3 consecutive API errors. "
                f"{completed} rows completed so far."
            )
            break

    results_df = pd.DataFrame(results, columns=RESULT_COLUMNS)
    results_df.to_csv("results.csv", index=False, encoding="utf-8-sig")

    evaluated = results_df[results_df["status"] == "evaluated"].copy()
    evaluated_count = len(evaluated)

    verdict_matches = (
        evaluated["predicted_verdict"] == evaluated["correct_verdict"]
    ).sum()
    exact_verdict_accuracy = percent(verdict_matches, evaluated_count)

    risky = {"scam", "suspicious"}
    correct_binary = evaluated["correct_verdict"].map(
        lambda value: "risky" if value in risky else "safe"
    )
    predicted_binary = evaluated["predicted_verdict"].map(
        lambda value: "risky" if value in risky else "safe"
    )
    binary_matches = (correct_binary == predicted_binary).sum()
    binary_safety_accuracy = percent(binary_matches, evaluated_count)

    scam_rows = evaluated[evaluated["correct_verdict"] == "scam"]
    scam_detected = scam_rows["predicted_verdict"].isin(["scam", "suspicious"]).sum()
    missed_scams = (scam_rows["predicted_verdict"] == "safe").sum()
    scam_recall = percent(scam_detected, len(scam_rows))

    safe_rows = evaluated[evaluated["correct_verdict"] == "safe"]
    false_alarm_scam = (safe_rows["predicted_verdict"] == "scam").sum()
    false_alarm_suspicious = (
        safe_rows["predicted_verdict"] == "suspicious"
    ).sum()
    false_alarm_scam_rate = percent(false_alarm_scam, len(safe_rows))
    false_alarm_suspicious_rate = percent(
        false_alarm_suspicious,
        len(safe_rows),
    )

    type_scope = scam_rows[
        (scam_rows["predicted_verdict"] == "scam")
    ]
    type_matches = (
        type_scope["predicted_type"] == type_scope["correct_type"]
    ).sum()
    scam_type_accuracy = percent(type_matches, len(type_scope))

    print("Total rows evaluated:", len(results_df))
    print("api_errors:", api_error_count)
    print(f"Exact verdict accuracy: {exact_verdict_accuracy:.1f}%")
    print(f"Binary safety accuracy: {binary_safety_accuracy:.1f}%")
    print(
        f"Scam recall: {scam_recall:.1f}% "
        f"(missed scams: {missed_scams})"
    )
    print(
        f"False alarm rate - scam: {false_alarm_scam_rate:.1f}%"
    )
    print(
        f"False alarm rate - suspicious: "
        f"{false_alarm_suspicious_rate:.1f}%"
    )
    print(f"Scam type accuracy: {scam_type_accuracy:.1f}%")

    print("\nConfusion table:")
    confusion = pd.crosstab(
        evaluated["correct_verdict"],
        evaluated["predicted_verdict"],
    )
    print(confusion.to_string())

    print("\nWrong rows:")
    wrong = evaluated[
        (evaluated["predicted_verdict"] != evaluated["correct_verdict"])
        | (evaluated["predicted_type"] != evaluated["correct_type"])
    ]
    # Verdict mismatch is enough for reporting wrong rows; type mismatches
    # are also shown when the verdict itself is correct.
    for _, row in wrong.iterrows():
        message = str(row["message"])
        truncated = message if len(message) <= 100 else message[:97] + "..."
        print(
            f"- {truncated}\n"
            f"  expected: {row['correct_verdict']}/{row['correct_type']}\n"
            f"  predicted: {row['predicted_verdict']}/{row['predicted_type']}\n"
            f"  confidence: {row['confidence']}\n"
            f"  reason: {row['reason']}"
        )


if __name__ == "__main__":
    main()
