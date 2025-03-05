from flask import Flask, jsonify
from flask_cors import CORS
from api.routes import api  # Import the API blueprint

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all domains

# Register the API blueprint
app.register_blueprint(api, url_prefix='/api')

# Basic error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# Basic health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(debug=True) 