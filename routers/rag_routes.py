import os
import json
from fastapi import APIRouter, Depends, HTTPException
from dependencies.auth_deps import get_current_user
from rag_evaluation import RAGEvaluator

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

router = APIRouter(tags=["rag"])


@router.post("/rag/evaluate")
def evaluate_rag(
    current_user=Depends(get_current_user),
):
    """
    Run deterministic RAG evaluation benchmark across all 10 query categories.
    JWT protected and operates strictly within authorized document isolation.
    """
    try:
        evaluator = RAGEvaluator()
        user_ctx = {
            "user_id": current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1),
            "email": current_user.get("email") if isinstance(current_user, dict) else getattr(current_user, "email", "eval_user"),
        }
        report = evaluator.run_evaluation(
            user_context=user_ctx,
            use_optimizer=True,
            generate_answers=False,
        )
        evaluator.save_reports(report)
        return report
    except Exception as e:
        print(f"❌ [RAG EVALUATION ERROR]: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}",
        )


@router.get("/rag/evaluation/latest")
def get_latest_evaluation(
    current_user=Depends(get_current_user),
):
    """Retrieve the latest cached RAG evaluation report (JSON format)."""
    report_path = os.path.join(BASE_DIR, "evaluation_reports", "rag_evaluation_latest.json")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="No evaluation report found. Run POST /rag/evaluate first.")
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)
