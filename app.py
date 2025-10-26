"""
Simple Text2SQL API
A single-file FastAPI application for converting natural language to SQL queries.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import uvicorn
from pathlib import Path
import httpx


# Request and Response Models
class QueryRequest(BaseModel):
    """Request model for text2sql query."""
    query: str = Field(..., description="Natural language query")
    max_num_result: int = Field(..., ge=1, description="Maximum number of results to return")


class ProductResult(BaseModel):
    """Individual product result."""
    product_id: str = Field(..., description="Product ID")
    reason: str = Field(..., description="Reason why this product matches the query")


class QueryResponse(BaseModel):
    """Response model containing list of products."""
    results: List[ProductResult]


class EvaluationResult(BaseModel):
    """Result for a single test case evaluation."""
    query: str
    predicted_products: List[str]
    ground_truth_products: List[str]
    precision: float
    recall: float
    f1_score: float


class EvaluationResponse(BaseModel):
    """Overall evaluation response."""
    total_queries: int
    avg_precision: float
    avg_recall: float
    avg_f1_score: float
    results: List[EvaluationResult]


# Helper Functions
def load_test_queries(file_path: str = "data/rubicon_tc.txt") -> List[str]:
    """Load test queries from file."""
    queries = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(line)
    return queries


def load_ground_truth(file_path: str = "data/rubicon_answer.txt") -> List[List[str]]:
    """Load ground truth product IDs from file."""
    ground_truths = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                # Split by comma to get list of product IDs
                product_ids = [pid.strip() for pid in line.split(',')]
                ground_truths.append(product_ids)
            else:
                # Empty line means no products
                ground_truths.append([])
    return ground_truths


def calculate_f1_score(predicted: List[str], ground_truth: List[str]) -> Dict[str, float]:
    """
    Calculate precision, recall, and F1-score.

    Args:
        predicted: List of predicted product IDs
        ground_truth: List of ground truth product IDs

    Returns:
        Dictionary with precision, recall, and f1_score
    """
    if not predicted and not ground_truth:
        return {"precision": 1.0, "recall": 1.0, "f1_score": 1.0}

    if not predicted:
        return {"precision": 0.0, "recall": 0.0, "f1_score": 0.0}

    if not ground_truth:
        return {"precision": 0.0, "recall": 0.0, "f1_score": 0.0}

    # Convert to sets for intersection
    predicted_set = set(predicted)
    ground_truth_set = set(ground_truth)

    # Calculate metrics
    true_positives = len(predicted_set & ground_truth_set)

    precision = true_positives / len(predicted_set) if predicted_set else 0.0
    recall = true_positives / len(ground_truth_set) if ground_truth_set else 0.0

    if precision + recall > 0:
        f1_score = 2 * (precision * recall) / (precision + recall)
    else:
        f1_score = 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score
    }


# Initialize FastAPI app
app = FastAPI(
    title="Text2SQL API",
    description="Convert natural language queries to SQL and return product results",
    version="0.1.0"
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Text2SQL API is running",
        "version": "0.1.0"
    }


@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process a natural language query and return matching products.

    Args:
        request: QueryRequest containing query and max_num_result

    Returns:
        QueryResponse with list of products and reasons
    """
    try:
        # TODO: Implement actual text2sql logic here
        # For now, return mock data

        # Simulate processing
        results = []
        for i in range(min(request.max_num_result, 3)):
            results.append(
                ProductResult(
                    product_id=f"PROD_{i+1:03d}",
                    reason=f"Mock result {i+1} for query: '{request.query}'"
                )
            )

        return QueryResponse(results=results)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "database": "not_connected",  # TODO: Add actual DB health check
        "llm": "not_connected"  # TODO: Add actual LLM health check
    }


@app.get("/eval/tc", response_model=EvaluationResponse)
async def evaluate_test_cases():
    """
    Evaluate the model on test cases.

    Reads queries from data/rubicon_tc.txt, calls the /query endpoint for each,
    and compares results against ground truth from data/rubicon_answer.txt.

    Returns:
        EvaluationResponse with overall metrics and per-query results
    """
    try:
        # Load test data
        queries = load_test_queries()
        ground_truths = load_ground_truth()

        if len(queries) != len(ground_truths):
            raise HTTPException(
                status_code=500,
                detail=f"Mismatch: {len(queries)} queries but {len(ground_truths)} ground truths"
            )

        # Evaluate each query
        results = []
        total_precision = 0.0
        total_recall = 0.0
        total_f1 = 0.0

        async with httpx.AsyncClient() as client:
            for i, (query, ground_truth) in enumerate(zip(queries, ground_truths)):
                # Call the query endpoint
                response = await client.post(
                    "http://localhost:8000/query",
                    json={"query": query, "max_num_result": 5}
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Query failed for: {query}"
                    )

                # Extract predicted product IDs
                response_data = response.json()
                predicted_products = [
                    result["product_id"] for result in response_data["results"]
                ]

                # Calculate metrics
                metrics = calculate_f1_score(predicted_products, ground_truth)

                # Store result
                results.append(
                    EvaluationResult(
                        query=query,
                        predicted_products=predicted_products,
                        ground_truth_products=ground_truth,
                        precision=metrics["precision"],
                        recall=metrics["recall"],
                        f1_score=metrics["f1_score"]
                    )
                )

                total_precision += metrics["precision"]
                total_recall += metrics["recall"]
                total_f1 += metrics["f1_score"]

        # Calculate averages
        num_queries = len(queries)
        avg_precision = total_precision / num_queries if num_queries > 0 else 0.0
        avg_recall = total_recall / num_queries if num_queries > 0 else 0.0
        avg_f1 = total_f1 / num_queries if num_queries > 0 else 0.0

        return EvaluationResponse(
            total_queries=num_queries,
            avg_precision=avg_precision,
            avg_recall=avg_recall,
            avg_f1_score=avg_f1,
            results=results
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Test file not found: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during evaluation: {str(e)}"
        )


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
