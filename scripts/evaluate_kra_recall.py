import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dpi_ls.dataset_loader import DatasetLoader
from dpi_ls.integrations import run_ragas

def evaluate_kra_recall():
    print("=== DPI-LS KRA Recall Measurement Harness ===")
    
    dataset_path = os.environ.get("GROUND_TRUTH_DATASET_PATH")
    
    if dataset_path and os.path.exists(dataset_path):
        print(f"Ground Truth: Real Regeneron data (loaded from {dataset_path})")
    else:
        print("Ground Truth: Synthetic (falling back to mock/seeded datasets)")
        dataset_path = "ground_truth.jsonl"
        # We will create a small synthetic dataset for testing if it doesn't exist
        if not os.path.exists(dataset_path):
            with open(dataset_path, "w", encoding="utf-8") as f:
                f.write('{"question": "How do I reset my password?", "expected_answer": "Click forgot password", "context": "Reset password guide", "kra": "CSAT"}\n')
                f.write('{"question": "What is the VPN address?", "expected_answer": "vpn.regeneron.com", "context": "VPN guide", "kra": "Throughput"}\n')
                f.write('{"question": "How to order a laptop?", "expected_answer": "Use ServiceNow portal", "context": "Hardware guide", "kra": "CSAT"}\n')
        
    loader = DatasetLoader(dataset_path)
    records = loader.load()
    
    if not records:
        print("No records to evaluate.")
        return
        
    print(f"\nEvaluating {len(records)} queries for Recall...")
    
    # Track context_recall per KRA
    # kra -> {"total_recall": float, "count": int}
    kra_stats = defaultdict(lambda: {"total_recall": 0.0, "count": 0})
    
    for idx, row in enumerate(records):
        kra = row.get("kra", "Unassigned")
        question = row.get("question", "")
        agent_answer = row.get("expected_answer", "")
        context = [row.get("context", "")] if row.get("context") else []
        
        # run_ragas internally calculates context_recall along with other Ragas metrics
        res = run_ragas(question, agent_answer, context)
        
        if res and "context_recall" in res:
            recall_val = res["context_recall"]
            kra_stats[kra]["total_recall"] += recall_val
            kra_stats[kra]["count"] += 1
            print(f"  - [{kra}] Query {idx+1}: Recall = {recall_val:.3f}")
        else:
            print(f"  - [{kra}] Query {idx+1}: Evaluation failed or skipped.")
            
    print("\n--- Recall by KRA ---")
    if not kra_stats:
        print("No successful evaluations.")
        return
        
    for kra, stats in kra_stats.items():
        if stats["count"] > 0:
            avg_recall = stats["total_recall"] / stats["count"]
            print(f"{kra}: {avg_recall:.3f} (over {stats['count']} queries)")
            
    print("\nRecall Measurement Complete.")

if __name__ == '__main__':
    evaluate_kra_recall()
