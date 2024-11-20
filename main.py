import json
import os
import time
from flask import Flask, request, jsonify
import openai
from openai import OpenAI
from dotenv import load_dotenv
from functions import solar
from functions import calendar_service
from functions.assistant import create_assistants

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)

# JSON-Encoding auf UTF-8
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = "application/json; charset=utf-8"


def detect_message_type(message: str, thread_id: str) -> str:
    """Erkennt den Nachrichtentyp basierend auf Schlüsselwörtern und Thread-Historie"""
    calendar_keywords = [
        'termin',
        'beratungstermin',
        'beratungsgespräch',
        'treffen',
        'kalender',
        'uhrzeit',
        'vereinbaren',
        'buchen'
    ]

    # Prüfe Thread-Historie
    try:
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        thread_context = ' '.join([msg.content[0].text.value.lower() for msg in messages.data])

        # Prüfe aktuelle Nachricht und Kontext
        message_lower = message.lower()
        for keyword in calendar_keywords:
            if keyword in message_lower or keyword in thread_context:
                print(f"Kalenderschlüsselwort gefunden: {keyword}")
                return 'calendar'
    except Exception as e:
        print(f"Fehler beim Prüfen der Thread-Historie: {e}")

    return 'solar'


@app.after_request
def add_utf8_header(response):
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Create or load assistant
solar_assistant_id, calendar_assistant_id = create_assistants(client)


@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "endpoints": {
            "start": "/start",
            "chat": "/chat"
        },
        "version": "1.0",
        "description": "Solar Bot API mit Termin-Buchung"
    })


@app.route('/start', methods=['GET'])
def start_conversation():
    print("Starting a new conversation...")
    thread = client.beta.threads.create()
    print(f"New thread created with ID: {thread.id}")
    return jsonify({"thread_id": thread.id})


@app.route('/chat', methods=['POST'])
def chat():
    calendar_event_created = False

    data = request.json
    thread_id = data.get('thread_id')
    user_input = data.get('message', '')
    msg_type = data.get('type') or detect_message_type(user_input, thread_id)

    print(f"Detected message type: {msg_type} for message: {user_input}")

    if not thread_id:
        print("Error: Missing thread_id")
        return jsonify({"error": "Missing thread_id"}), 400

    print(f"Received message: {user_input} for thread ID: {thread_id}")

    try:
        # Add message to thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )

        # Wähle den richtigen Assistenten
        assistant_id = solar_assistant_id if msg_type == 'solar' else calendar_assistant_id

        if not assistant_id:
            return jsonify({"error": f"No assistant found for type: {msg_type}"}), 400

        print(f"Using assistant: {assistant_id} for type: {msg_type}")

        # Run the Assistant
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

            if run_status.status == 'completed':
                break
            elif run_status.status == 'requires_action':
                tool_outputs = []
                for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    output = None
                    print(f"Executing function: {function_name}")
                    try:
                        if function_name == "solar_panel_calculations":
                            output = solar.solar_panel_calculations(
                                arguments["address"],
                                arguments["monthly_bill"]
                            )
                        elif function_name == "check_availability":
                            output = calendar_service.check_availability(
                                arguments["start_time"],
                                arguments["end_time"]
                            )
                        elif function_name == "create_appointment":
                            output = calendar_service.create_appointment(
                                arguments["summary"],
                                arguments["description"],
                                arguments["start_time"],
                                arguments["end_time"],
                                arguments["email"]
                            )
                            calendar_event_created = True
                            print("Kalendereintrag erfolgreich erstellt")

                        if output:
                            tool_outputs.append({
                                "tool_call_id": tool_call.id,
                                "output": json.dumps(output)
                            })

                    except Exception as func_error:
                        print(f"Error in function {function_name}: {str(func_error)}")
                        if calendar_event_created:
                            return jsonify({
                                "response": "Der Termin wurde erfolgreich erstellt. Bitte prüfen Sie Ihre E-Mail für die Details.",
                                "status": "success",
                                "calendar_event": "created"
                            })
                        raise func_error

                if tool_outputs:
                    try:
                        client.beta.threads.runs.submit_tool_outputs(
                            thread_id=thread_id,
                            run_id=run.id,
                            tool_outputs=tool_outputs
                        )
                    except Exception as submit_error:
                        print(f"Error submitting tool outputs: {str(submit_error)}")
                        if calendar_event_created:
                            return jsonify({
                                "response": "Der Termin wurde erfolgreich erstellt. Bitte prüfen Sie Ihre E-Mail für die Details.",
                                "status": "success",
                                "calendar_event": "created"
                            })
                        raise submit_error

            elif run_status.status == 'failed':
                if calendar_event_created:
                    return jsonify({
                        "response": "Der Termin wurde erfolgreich erstellt. Bitte prüfen Sie Ihre E-Mail für die Details.",
                        "status": "success",
                        "calendar_event": "created"
                    })
                return jsonify({"error": "Assistant run failed"}), 500

            time.sleep(1)

        # Get response
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        response = messages.data[0].content[0].text.value

        return jsonify({
            "response": response,
            "status": "success",
            "calendar_event": "created" if calendar_event_created else "none"
        })

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        if calendar_event_created:
            return jsonify({
                "response": "Der Termin wurde erfolgreich erstellt. Bitte prüfen Sie Ihre E-Mail für die Details.",
                "status": "success",
                "calendar_event": "created"
            })
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)