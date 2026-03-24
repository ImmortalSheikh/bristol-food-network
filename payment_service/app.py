from flask import Flask, request, jsonify
import uuid
import random

app = Flask(__name__)

@app.route('/pay', methods=['POST'])
def pay():
    data = request.json

    amount = data.get('amount')

    # Fake success/failure
    success = random.choice([True, True, True, False])  # 75% success

    if success:
        return jsonify({
            "status": "success",
            "transaction_id": str(uuid.uuid4())
        })
    else:
        return jsonify({
            "status": "failed"
        }), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)