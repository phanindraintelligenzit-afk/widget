import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dpi_ls.dataset_loader import DatasetLoader
from dpi_ls.integrations import run_ragas, run_deepeval_metrics, push_quality_results_to_backend, push_deepeval_results_to_backend
from contract.settings import Settings

def evaluate_dataset():
    # Use environment variable or fallback to loading from Settings in DB
    dataset_path = os.environ.get("GROUND_TRUTH_DATASET_PATH")
    if not dataset_path:
        # In a real run, we would fetch from settings DB table, but here we just fallback
        dataset_path = "ground_truth.jsonl"
        
    loader = DatasetLoader(dataset_path)
    records = loader.load()
    
    if not records:
        print("No records loaded from ground truth dataset. Exiting.")
        return
        
    print(f"Evaluating {len(records)} records from {dataset_path}...")
    
    # Initialize aggregated results
    agg_ragas = {"semantic_accuracy": 0, "faithfulness": 0, "answer_relevancy": 0, "context_precision": 0, "context_recall": 0}
    agg_deepeval = {"answer_relevancy": 0, "faithfulness": 0, "hallucination": 0, "correctness": 0}
    
    valid_ragas_count = 0
    valid_deepeval_count = 0
    
    for idx, row in enumerate(records):
        question = row.get("question", "")
        agent_answer = row.get("expected_answer", "")
        context = [row.get("context", "")] if row.get("context") else []
        
        print(f"\n--- Evaluating Row {idx+1}/{len(records)} ---")
        
        ragas_res = run_ragas(question, agent_answer, context)
        if ragas_res:
            valid_ragas_count += 1
            for k in agg_ragas:
                agg_ragas[k] += ragas_res.get(k, 0)
                
        deepeval_res = run_deepeval_metrics(question, agent_answer, context)
        if deepeval_res:
            valid_deepeval_count += 1
            for k in agg_deepeval:
                agg_deepeval[k] += deepeval_res.get(k, 0)
                
    if valid_ragas_count > 0:
        for k in agg_ragas:
            agg_ragas[k] = round(agg_ragas[k] / valid_ragas_count, 3)
        print(f"\n[Ragas Aggregated] {agg_ragas}")
        push_quality_results_to_backend({}, agg_ragas, {}, "127.0.0.1", 8000)
        
    if valid_deepeval_count > 0:
        for k in agg_deepeval:
            agg_deepeval[k] = round(agg_deepeval[k] / valid_deepeval_count, 3)
        print(f"[DeepEval Aggregated] {agg_deepeval}")
        push_deepeval_results_to_backend(agg_deepeval, "127.0.0.1", 8000)
        
    print("\nDataset evaluation complete.")

if __name__ == '__main__':
    evaluate_dataset()
