from flask import Flask, request, jsonify
import os
import stripe

app = Flask(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@app.route("/pay", methods=["POST"])
def pay():
    data = request.get_json() or {}

    amount = data.get("amount")
    currency = data.get("currency", "gbp")
    payment_method = data.get("payment_method", "pm_card_visa")

    print(f"\n{'='*50}")
    print(f"[STRIPE] Incoming payment request")
    print(f"[STRIPE] Amount:         £{amount}")
    print(f"[STRIPE] Currency:       {currency.upper()}")
    print(f"[STRIPE] Payment method: {payment_method}")
    print(f"[STRIPE] Customer ID:    {data.get('customer_id', 'N/A')}")
    print(f"{'='*50}")

    if amount is None:
        print("[STRIPE] ERROR: Missing amount — request rejected")
        return jsonify({
            "status": "failed",
            "message": "Missing amount"
        }), 400

    try:
        amount_in_pence = int(float(amount) * 100)
        print(f"[STRIPE] Sending to Stripe: {amount_in_pence}p ({currency.upper()})")

        intent = stripe.PaymentIntent.create(
            amount=amount_in_pence,
            currency=currency,
            payment_method=payment_method,
            confirm=True,
            automatic_payment_methods={"enabled": False},
            payment_method_types=["card"],
        )

        print(f"[STRIPE] ✓ Payment SUCCESS")
        print(f"[STRIPE] Transaction ID: {intent.id}")
        print(f"[STRIPE] Stripe status:  {intent.status}")
        print(f"{'='*50}\n")

        return jsonify({
            "status": "success",
            "transaction_id": intent.id,
            "stripe_status": intent.status
        }), 200

    except stripe.error.CardError as e:
        print(f"[STRIPE] ✗ Card error: {e.user_message}")
        print(f"{'='*50}\n")
        return jsonify({
            "status": "failed",
            "message": str(e.user_message or "Card was declined")
        }), 400

    except Exception as e:
        print(f"[STRIPE] ✗ Unexpected error: {str(e)}")
        print(f"{'='*50}\n")
        return jsonify({
            "status": "failed",
            "message": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)