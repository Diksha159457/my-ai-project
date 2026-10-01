"""HTTP API for the reviewer (deployed on Render)."""

from __future__ import annotations

import os

from flask import Flask, jsonify, request

from ai_reviewer import ReviewError, review_diff
from ai_reviewer.diff import diff_stats

MAX_DIFF_BYTES = int(os.environ.get("MAX_DIFF_BYTES", 200_000))


def create_app(review_fn=review_diff) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_DIFF_BYTES + 10_000

    @app.get("/")
    def home():
        return {"message": "AI Code Review Assistant running", "endpoints": ["/review", "/health"]}

    @app.get("/health")
    def health():
        return {"status": "ok", "llm_configured": bool(os.environ.get("GROQ_API_KEY"))}

    @app.post("/review")
    def review():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Body must be a JSON object"), 400
        diff = data.get("diff")
        if not isinstance(diff, str) or not diff.strip():
            return jsonify(error="Field 'diff' (non-empty string) is required"), 400
        if len(diff.encode()) > MAX_DIFF_BYTES:
            return jsonify(error=f"Diff exceeds {MAX_DIFF_BYTES} bytes"), 413

        language = str(data.get("lang", "auto"))
        try:
            result = review_fn(diff, language=language)
        except ReviewError as e:
            return jsonify(error=str(e)), 502

        stats = diff_stats(diff)
        return jsonify(
            **result.model_dump(mode="json"),
            stats={
                "files": stats.files,
                "additions": stats.additions,
                "deletions": stats.deletions,
            },
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
