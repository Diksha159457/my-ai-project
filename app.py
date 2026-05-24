from flask import Flask, request, jsonify
from review import review_code

app = Flask(__name__)

@app.route("/")
def home():
    return {
        "message": "AI Code Review Assistant Running"
    }

@app.route("/review", methods=["POST"])
def review():
    data = request.get_json()

    diff = data.get("diff", "")

    if not diff:
        return jsonify({
            "error": "No diff provided"
        }), 400

    try:
        result = review_code(diff)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)