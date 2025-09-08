"""
API module with Flask routes for the application.
"""
from flask import Flask, request, abort, jsonify, Response, stream_with_context
from flask_cors import CORS
import asyncio
import json
import aiohttp
from typing import Dict, Any, Generator
from config import config
from database import db_manager, chat_repository
from metabase import metabase_client
from chat import chat_manager
from sql_generator import sql_generator
import openai
import os


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    CORS(app)
    
    # Configure Flask based on environment
    app.config['DEBUG'] = config.app.debug
    app.config['TESTING'] = config.app.testing
    
    return app


app = create_app()


@app.route("/")
def health_check():
    """Health check endpoint"""
    return "Backend is working!"


@app.route("/api/ask", methods=["POST"])
async def ask():
    """
    Main endpoint for processing natural language queries.
    Generates SQL and creates Metabase cards.
    """
    data = request.get_json()
    
    try:
        question = data.get("question")
        conversation = data.get("conversation", [])
        metabase_url = data.get("metabase_url")
        tenant_id = data.get("tenant_id", "default")
        
        if not all([question, metabase_url]):
            return abort(400, "question and metabase_url are required")
        
        # Get tenant configuration
        tenant_config = config.get_tenant_config(tenant_id)
        db_id = tenant_config["db_id"]
        collection_id = tenant_config["collection_id"]
        
        print(f"Request - Tenant: {tenant_id}, DB: {db_id}, Collection: {collection_id}")
        
        # Extract past questions from conversation
        past_questions = chat_manager.extract_past_questions(conversation)
        
        # Generate SQL from natural language
        sql, metadata = await sql_generator.generate_sql(
            question, past_questions, db_id
        )
        
        if not sql or not metadata:
            return {"url": "fail", "card_id": 0, "x_field": "", "y_field": ""}, 200
        
        # Create Metabase card
        card_id = metabase_client.create_card(
            sql, db_id, collection_id, metadata['title']
        )
        
        # Generate embed URL
        embed_url = metabase_client.generate_embed_url(card_id)
        
        return {
            "url": embed_url,
            "card_id": card_id,
            "x_field": metadata.get('x_axis', []),
            "y_field": metadata.get('y_axis', []),
            "title": metadata.get("title", "Untitled"),
            "visualization_options": metadata.get('visualization_options', []),
            "SQL": sql
        }, 200
        
    except Exception as e:
        print(f"Error in /api/ask: {e}")
        return abort(500, "Internal server error")


@app.route("/api/change_display", methods=["POST"])
def change_display():
    """Update visualization type for a Metabase card"""
    data = request.get_json()
    
    try:
        mode = data.get("mode")
        card_id = data.get("card_id")
        x_field = data.get("x_field", [])
        y_field = data.get("y_field", [])
        visualization_options = data.get("visualization_options", [])
        
        if not all([mode, card_id]):
            return abort(400, "mode and card_id are required")
        
        # Update card visualization
        metabase_client.update_card_visualization(card_id, mode, x_field, y_field)
        
        # Generate new embed URL
        embed_url = metabase_client.generate_embed_url(card_id)
        
        return {
            "url": embed_url,
            "card_id": card_id,
            "x_field": x_field,
            "y_field": y_field,
            "visualization_options": visualization_options
        }, 200
        
    except Exception as e:
        print(f"Error in /api/change_display: {e}")
        return abort(500, "Internal server error")


@app.route("/api/delete", methods=["POST"])
def delete_question():
    """Delete a Metabase card"""
    data = request.get_json()
    
    try:
        card_id = data.get("card_id")
        
        if not card_id:
            return abort(400, "card_id is required")
        
        success = metabase_client.delete_card(card_id)
        return {"success": success}
        
    except Exception as e:
        print(f"Error in /api/delete: {e}")
        return {"success": False}


@app.route("/api/explain_sql", methods=["POST"])
async def explain_sql():
    """Generate a user-friendly explanation for SQL query"""
    data = request.get_json()
    
    try:
        sql = data.get("sql")
        
        if not sql:
            return abort(400, "sql is required")
        
        # Generate explanation using the sql_generator
        explanation = await sql_generator.explain_sql(sql)
        
        return {
            "explanation": explanation
        }, 200
        
    except Exception as e:
        print(f"Error in /api/explain_sql: {e}")
        return {
            "explanation": "This query retrieves and analyzes your data."
        }, 200


# Chat management endpoints

@app.route("/api/chats", methods=["POST"])
def get_chats():
    """Get all chats for a user"""
    data = request.get_json()
    
    try:
        user_id = data.get("user_id")
        tenant_id = data.get("tenant_id", "default")
        
        if not user_id:
            return abort(400, "user_id is required")
        
        chats = chat_manager.get_user_chats(user_id, tenant_id)
        return jsonify(chats), 200
        
    except Exception as e:
        print(f"Error getting chats: {e}")
        return abort(500, "Internal server error")


@app.route("/api/chats/<chat_id>", methods=["POST"])
def get_chat(chat_id):
    """Get a specific chat and validate/recreate cards"""
    data = request.get_json()
    
    try:
        user_id = data.get("user_id")
        
        if not user_id:
            return abort(400, "user_id is required")
        
        chat_data = chat_manager.get_chat_with_card_validation(chat_id, user_id)
        
        if not chat_data:
            return abort(404, "Chat not found")
        
        return jsonify(chat_data), 200
        
    except Exception as e:
        print(f"Error getting chat: {e}")
        return abort(500, "Internal server error")


@app.route("/api/chats/save", methods=["POST"])
def save_chat():
    """Save or update a chat"""
    data = request.get_json()
    
    try:
        user_id = data.get("user_id")
        tenant_id = data.get("tenant_id", "default")
        metabase_url = data.get("metabase_url")
        chat_id = data.get("chat_id")
        title = data.get("title")
        conversation = data.get("conversation")
        
        if not all([user_id, title, conversation]):
            return abort(400, "user_id, title, and conversation are required")
        
        result_chat_id = chat_manager.save_chat(
            user_id, tenant_id, metabase_url, title, conversation, chat_id
        )
        
        return {"chat_id": result_chat_id}, 200
        
    except Exception as e:
        print(f"Error saving chat: {e}")
        return abort(500, "Internal server error")


@app.route("/api/chats/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    """Delete a chat"""
    data = request.get_json()
    
    try:
        user_id = data.get("user_id")
        
        if not user_id:
            return abort(400, "user_id is required")
        
        success = chat_manager.delete_chat(chat_id, user_id)
        
        if not success:
            return abort(404, "Chat not found")
        
        return {"success": True}, 200
        
    except Exception as e:
        print(f"Error deleting chat: {e}")
        return abort(500, "Internal server error")


def run_async(coro):
    """Helper to run async functions in Flask routes"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Wrap async route handlers
original_ask = ask
def ask():
    return run_async(original_ask())
app.view_functions['ask'] = ask

original_explain_sql = explain_sql
def explain_sql():
    return run_async(original_explain_sql())
app.view_functions['explain_sql'] = explain_sql