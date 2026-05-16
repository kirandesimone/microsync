from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv
 
load_dotenv()
 
app = Flask(__name__)
CORS(app)
 
# Connect to MongoDB Atlas
client = MongoClient(os.getenv("MONGO_URI"))
db = client["microsync_db"]
data_collection = db["positions"]
 
 
def format_entry(entry):
    """Convert MongoDB document to JSON-friendly format."""
    entry["id"] = str(entry["_id"])
    del entry["_id"]
    return entry
 
 
# POST /positions/<areaId>

# Save a new data entry for a specific area
# Path param: areaId — identifies the geographic area (e.g. "portland", "area01")
# Body param: positionData — any JSON object your app wants to save
# clientId — identifies which app is sending the data (e.g. "wildlife_app", "stealth_game")
#
# Example from wildlife app:
#   POST /positions/portland
#   { "clientId": "wildlife_app", "animal_name": "Hawk", "lat": 45.5, "lng": -122.6, "public": true }
#
# Example from Josh's stealth game:
#   POST /positions/area01
#   { "clientId": "stealth_game", "player": "Josh", "x": 10, "y": 25, "public": true }
@app.route("/positions/<areaId>", methods=["POST"])
def publish_position(areaId):
    data = request.json
 
    if not data:
        return jsonify({"error": "No data provided"}), 400
 
    # Add server-side metadata
    data["areaId"] = areaId
    data["timestamp"] = datetime.utcnow().isoformat()
 
    # Default public to True if not provided
    if "public" not in data:
        data["public"] = True
 
    result = data_collection.insert_one(data)
    return jsonify({"status": "saved", "id": str(result.inserted_id)}), 201
 
 
# getting positions/<areaId>
# Get all public entries for a specific area
# Path param: areaId — the area to query
# Example calls:
#   GET /positions/portland
#   GET /positions/portland?since=2026-05-14T15:30:00.000Z
@app.route("/positions/<areaId>", methods=["GET"])
def get_client_positions(areaId):
    query = {"areaId": areaId, "public": True}
 
    # Optional: only return entries after a certain time
    since = request.args.get("since")
    if since:
        query["timestamp"] = {"$gt": since}
 
    results = data_collection.find(query)
    entries = [format_entry(e) for e in results]
    return jsonify(entries), 200
 
 
# get positions/area id
# get user posts for a specific area, optionally filtered by timestamp
# This is the "sync user posts data" endpoint from the group plan
# Path param: areaId — the area to query

#   GET /positions/portland/posts?since=2026-05-14T15:30:00.000Z
@app.route("/positions/<areaId>/posts", methods=["GET"])
def get_user_posts(areaId):
    query = {"areaId": areaId, "public": True}
 
    since = request.args.get("since")
    if since:
        query["timestamp"] = {"$gt": since}
 
    results = data_collection.find(query)
    entries = [format_entry(e) for e in results]
    return jsonify(entries), 200
 
 
# delete positions/area id
# Delete a specific entry by ID within an area
# Path params: areaId, id
#
# Example call:
#   DELETE /positions/portland/6a062da30dcd4a1844a57428
@app.route("/positions/<areaId>/<id>", methods=["DELETE"])
def delete_position(areaId, id):
    try:
        result = data_collection.delete_one({
            "_id": ObjectId(id),
            "areaId": areaId
        })
        if result.deleted_count == 0:
            return jsonify({"error": "Entry not found"}), 404
        return jsonify({"status": "deleted", "id": id}), 200
    except Exception:
        return jsonify({"error": "Invalid ID format"}), 400
 
 
if __name__ == "__main__":
    print("Microsync running on http://localhost:5000")
    print("Endpoints:")
    print("  POST   /positions/<areaId>         - save a new entry")
    print("  GET    /positions/<areaId>          - get all public entries for area")
    print("  GET    /positions/<areaId>/posts    - get user posts for area")
    print("  DELETE /positions/<areaId>/<id>     - delete an entry")
    app.run(port=5000, debug=True)
