from flask import Flask, request, send_file, jsonify
import pandas as pd

app = Flask(__name__)

# Store email open statuses
opened_emails = {}

@app.route('/track/<email>', methods=['GET'])
def track_email(email):
    # Log that the email was opened
    opened_emails[email] = "Yes"
    # Serve a transparent tracking pixel
    return send_file("pixel.png", mimetype="image/png")  # Ensure you have a 1x1 transparent pixel image

@app.route('/opened-status', methods=['GET'])
def get_opened_status():
    # Return the opened status as JSON
    return jsonify(opened_emails)

@app.route('/reset-status', methods=['POST'])
def reset_status():
    # Reset all open statuses to 'No' for testing purposes
    global opened_emails
    opened_emails = {email: "No" for email in opened_emails}
    return jsonify({"message": "All email statuses have been reset to 'No'."})

if __name__ == "__main__":
    app.run(port=5001)
