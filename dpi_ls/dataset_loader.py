import os
import csv
import json

class DatasetLoader:
    def __init__(self, path: str | None):
        self.path = path

    def load(self) -> list[dict]:
        dpi_env = os.environ.get("DPI_ENV", "development")
        
        if not self.path:
            if dpi_env == "production":
                raise RuntimeError("DPI_ENV=production but no ground_truth_dataset_path configured.")
            print("[DatasetLoader] No dataset path provided. Returning empty dataset.")
            return []
            
        if not os.path.exists(self.path):
            if dpi_env == "production":
                raise RuntimeError(f"Configured ground_truth_dataset_path does not exist: {self.path}")
            print(f"[DatasetLoader] Dataset not found at {self.path}. Returning empty dataset.")
            return []
            
        records = []
        ext = os.path.splitext(self.path)[1].lower()
        
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                if ext == '.csv':
                    reader = csv.DictReader(f)
                    for row in reader:
                        records.append({
                            "question": row.get("question", ""),
                            "expected_answer": row.get("expected_answer", ""),
                            "context": row.get("context", ""),
                            "kra": row.get("kra", "Unassigned")
                        })
                elif ext == '.jsonl':
                    for line in f:
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        records.append({
                            "question": row.get("question", ""),
                            "expected_answer": row.get("expected_answer", ""),
                            "context": row.get("context", ""),
                            "kra": row.get("kra", "Unassigned")
                        })
                else:
                    raise ValueError(f"Unsupported dataset extension: {ext}. Use .csv or .jsonl")
        except Exception as e:
            raise RuntimeError(f"Failed to load dataset at {self.path}: {e}")
            
        return records
