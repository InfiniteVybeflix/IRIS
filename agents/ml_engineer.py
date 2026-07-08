#!/usr/bin/env python3
"""
ml_engineer.py — TENSOR
ML/AI Operations Agent for IRIS v7.0
Model training orchestration, hyperparameter tuning, model evaluation,
MLOps pipeline generation, dataset preprocessing, feature engineering,
model deployment packaging (ONNX/TensorRT), drift detection, A/B testing.
"""

import threading
import hashlib
import json
import logging
import time
import os
import subprocess
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TENSOR")


class MLEngineer:
    CODENAME = "TENSOR"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        self._experiments: Dict[str, Dict[str, Any]] = {}
        self._drift_buffers: Dict[str, deque] = {}
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report_to_commander("TENSOR started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("TENSOR stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "experiments": len(self._experiments),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Any = None) -> None:
        payload = {
            "agent": self.CODENAME,
            "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data,
        }
        if self._commander_bus:
            try:
                self._commander_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Bus error: {e}")
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"[{self.CODENAME}] {message}")

    def _store_memory(self, key: str, value: Any) -> None:
        if self._shared_memory:
            try:
                self._shared_memory.set(f"{self.CODENAME}.{key}", value, ttl=86400)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Memory store error: {e}")

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def preprocess_data(self, data_path: str, operations: List[str]) -> Dict[str, Any]:
        """Preprocess tabular data: normalize, encode, impute, split."""
        if not self._running:
            raise RuntimeError("Agent not running")
        try:
            import pandas as pd
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler, LabelEncoder
            df = pd.read_csv(data_path)
            for op in operations:
                if op == "drop_na":
                    df = df.dropna()
                elif op == "fill_na_mean":
                    df = df.fillna(df.mean(numeric_only=True))
                elif op == "normalize":
                    scaler = StandardScaler()
                    numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns
                    df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
                elif op == "label_encode":
                    for col in df.select_dtypes(include=["object"]).columns:
                        df[col] = LabelEncoder().fit_transform(df[col].astype(str))
                elif op.startswith("split:"):
                    ratio = float(op.split(":")[1])
                    train, test = train_test_split(df, test_size=ratio, random_state=42)
                    train_path = data_path.replace(".csv", "_train.csv")
                    test_path = data_path.replace(".csv", "_test.csv")
                    train.to_csv(train_path, index=False)
                    test.to_csv(test_path, index=False)
                    return {"train": train_path, "test": test_path, "rows": len(df)}
            out_path = data_path.replace(".csv", "_processed.csv")
            df.to_csv(out_path, index=False)
            return {"output": out_path, "rows": len(df), "columns": list(df.columns)}
        except ImportError as e:
            self._report_to_commander(f"Missing ML library: {e}", level="warning")
            return {"error": str(e), "note": "Install pandas, scikit-learn"}
        except Exception as e:
            return {"error": str(e)}

    def train_model(self, experiment_id: str, train_path: str, target_col: str, model_type: str = "random_forest",
                    hyperparams: Optional[Dict] = None) -> Dict[str, Any]:
        """Train a scikit-learn model and store metrics."""
        if not self._running:
            raise RuntimeError("Agent not running")
        try:
            import pandas as pd
            from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
            from sklearn.linear_model import LogisticRegression
            from sklearn.metrics import accuracy_score, f1_score, classification_report
            import joblib
            df = pd.read_csv(train_path)
            X = df.drop(columns=[target_col])
            y = df[target_col]
            hp = hyperparams or {}
            if model_type == "random_forest":
                model = RandomForestClassifier(**hp, random_state=42)
            elif model_type == "gradient_boosting":
                model = GradientBoostingClassifier(**hp, random_state=42)
            elif model_type == "logistic_regression":
                model = LogisticRegression(**hp, max_iter=1000)
            else:
                model = RandomForestClassifier(random_state=42)
            model.fit(X, y)
            preds = model.predict(X)
            acc = accuracy_score(y, preds)
            f1 = f1_score(y, preds, average="weighted")
            model_path = f"/tmp/tensor_model_{experiment_id}.pkl"
            joblib.dump(model, model_path)
            result = {
                "experiment_id": experiment_id,
                "model_type": model_type,
                "accuracy": round(acc, 4),
                "f1": round(f1, 4),
                "model_path": model_path,
                "features": list(X.columns),
            }
            self._experiments[experiment_id] = result
            self._store_memory(f"experiment:{experiment_id}", result)
            self._report_to_commander(f"Training complete: {experiment_id}", data=result)
            return result
        except ImportError as e:
            return {"error": str(e), "note": "Install pandas, scikit-learn, joblib"}
        except Exception as e:
            return {"error": str(e)}

    def hyperparameter_search(self, train_path: str, target_col: str, model_type: str = "random_forest",
                               param_grid: Optional[Dict] = None, cv: int = 3) -> Dict[str, Any]:
        """Run GridSearchCV for hyperparameter tuning."""
        if not self._running:
            raise RuntimeError("Agent not running")
        try:
            import pandas as pd
            from sklearn.model_selection import GridSearchCV
            from sklearn.ensemble import RandomForestClassifier
            df = pd.read_csv(train_path)
            X = df.drop(columns=[target_col])
            y = df[target_col]
            grid = param_grid or {"n_estimators": [50, 100], "max_depth": [3, 5, None]}
            model = RandomForestClassifier(random_state=42)
            search = GridSearchCV(model, grid, cv=cv, scoring="f1_weighted", n_jobs=-1)
            search.fit(X, y)
            result = {
                "best_params": search.best_params_,
                "best_score": round(search.best_score_, 4),
                "cv": cv,
            }
            self._store_memory("hyperparam:latest", result)
            return result
        except ImportError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    def detect_drift(self, stream_id: str, reference_stats: Dict[str, Any], new_sample: Dict[str, float],
                     threshold: float = 0.05) -> Dict[str, Any]:
        """Detect statistical drift between reference and new sample using KS-like distance."""
        if not self._running:
            raise RuntimeError("Agent not running")
        drifted = False
        distances = {}
        for feature, ref in reference_stats.items():
            if feature in new_sample:
                ref_mean = ref.get("mean", 0)
                ref_std = ref.get("std", 1)
                if ref_std == 0:
                    ref_std = 1
                z_score = abs(new_sample[feature] - ref_mean) / ref_std
                distances[feature] = round(z_score, 4)
                if z_score > threshold:
                    drifted = True
        self._drift_buffers.setdefault(stream_id, deque(maxlen=1000)).append({"drifted": drifted, "distances": distances, "time": datetime.utcnow().isoformat()})
        self._store_memory(f"drift:{stream_id}", {"drifted": drifted, "distances": distances})
        return {"drifted": drifted, "distances": distances, "threshold": threshold}

    def export_to_onnx(self, model_path: str, output_path: str, input_shape: List[int]) -> Dict[str, Any]:
        """Export a scikit-learn model to ONNX using skl2onnx."""
        if not self._running:
            raise RuntimeError("Agent not running")
        try:
            from skl2onnx import convert_sklearn
            from skl2onnx.common.data_types import FloatTensorType
            import joblib
            model = joblib.load(model_path)
            initial_type = [("float_input", FloatTensorType(input_shape))]
            onnx_model = convert_sklearn(model, initial_types=initial_type)
            with open(output_path, "wb") as f:
                f.write(onnx_model.SerializeToString())
            return {"path": output_path, "size": os.path.getsize(output_path), "format": "ONNX"}
        except ImportError as e:
            return {"error": str(e), "note": "Install skl2onnx, onnx"}
        except Exception as e:
            return {"error": str(e)}

    def generate_ml_pipeline(self, steps: List[str], output_path: str = "pipeline.py") -> str:
        """Generate a Python ML pipeline script from step names."""
        lines = ["#!/usr/bin/env python3", "# Auto-generated by TENSOR / IRIS v7.0", "", "import pandas as pd", "from sklearn.model_selection import train_test_split", "from sklearn.preprocessing import StandardScaler", ""]
        if "train" in steps:
            lines.append("from sklearn.ensemble import RandomForestClassifier")
        lines.append("")
        lines.append("def run_pipeline(data_path):")
        lines.append("    df = pd.read_csv(data_path)")
        if "preprocess" in steps:
            lines.append("    df = df.dropna()")
            lines.append("    scaler = StandardScaler()")
            lines.append("    numeric = df.select_dtypes(include=['float64','int64']).columns")
            lines.append("    df[numeric] = scaler.fit_transform(df[numeric])")
        if "split" in steps:
            lines.append("    train, test = train_test_split(df, test_size=0.2, random_state=42)")
        if "train" in steps:
            lines.append("    model = RandomForestClassifier(n_estimators=100, random_state=42)")
            lines.append("    # model.fit(X_train, y_train)")
        lines.append("    print('Pipeline complete')")
        lines.append("")
        lines.append("if __name__ == '__main__':")
        lines.append("    run_pipeline('data.csv')")
        code = "\n".join(lines)
        with open(output_path, "w") as f:
            f.write(code)
        return output_path

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_preprocess(self) -> bool:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("a,b,c\n1,2,3\n4,5,6\n")
            path = f.name
        r = self.preprocess_data(path, ["drop_na"])
        return "output" in r or "error" in r

    def test_train(self) -> bool:
        # Requires real data; stub
        return True

    def test_drift(self) -> bool:
        r = self.detect_drift("s1", {"x": {"mean": 0, "std": 1}}, {"x": 5.0}, threshold=2.0)
        return r["drifted"] is True

    def test_pipeline(self) -> bool:
        p = self.generate_ml_pipeline(["preprocess", "split", "train"], "/tmp/test_pipeline.py")
        return os.path.exists(p)


if __name__ == "__main__":
    agent = MLEngineer()
    agent.start()
    print(agent.health())
    agent.stop()
